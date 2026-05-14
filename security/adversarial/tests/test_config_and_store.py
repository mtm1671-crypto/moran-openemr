from pathlib import Path

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.models import (
    AttackCase,
    AttackCategory,
    AuditAction,
    AuditEvent,
    AuthorizedScope,
    Citation,
    Client,
    FindingStatus,
    ImpactDomain,
    ObservedResponse,
    Project,
    ReportStatus,
    ScanJob,
    ScanJobStatus,
    Severity,
    SiteScanFinding,
    SiteScanMode,
    SiteScanRun,
    TargetMode,
    VulnerabilityReport,
)
from app.run_store import RunStore
from app.scope_registry import ensure_default_scope, resolve_scope_for_scan
from app.sensitive_findings import SensitiveFindingStore


def test_allowlist_rejects_unknown_host() -> None:
    settings = Settings(allowed_hosts=["localhost"], local_target_url="https://evil.example")
    with pytest.raises(ValueError, match="not allowlisted"):
        settings.validate_target_allowed()


def test_expected_denied_paths_parse_from_env_string() -> None:
    settings = Settings.model_validate(
        {"site_scan_expected_denied_paths": "/api/a,/billing/private"}
    )
    assert settings.site_scan_expected_denied_paths == ["/api/a", "/billing/private"]


def test_deployed_requires_synthetic_clinician_token() -> None:
    settings = Settings(target_mode=TargetMode.DEPLOYED, synthetic_clinician_token=None)
    with pytest.raises(ValueError, match="deployed runs require"):
        settings.validate_ready_for_run()


def test_deployed_accepts_synthetic_password_grant_settings() -> None:
    settings = Settings(
        target_mode=TargetMode.DEPLOYED,
        synthetic_clinician_token_url="https://openemr-production-f5ed.up.railway.app/oauth2/default/token",
        synthetic_clinician_client_id="client-id",
        synthetic_clinician_username="admin",
        synthetic_clinician_password=SecretStr("secret"),
    )
    settings.validate_ready_for_run()
    assert settings.has_synthetic_clinician_auth is True


def test_deployed_operator_service_requires_operator_token() -> None:
    settings = Settings(target_mode=TargetMode.DEPLOYED, operator_token=None)
    with pytest.raises(ValueError, match="ADVERSARIAL_OPERATOR_TOKEN"):
        settings.validate_operator_auth_ready()


def test_deployed_operator_service_accepts_operator_token() -> None:
    settings = Settings(
        target_mode=TargetMode.DEPLOYED,
        operator_token=SecretStr("operator-test-token"),
    )
    settings.validate_operator_auth_ready()


def test_run_store_initializes_and_saves_case(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.sqlite")
    ready, message = store.readiness()
    assert ready, message
    case = AttackCase(
        case_id="case_1",
        name="Case",
        category=AttackCategory.CROSS_PATIENT_PHI,
        subcategory="identifier",
        surface="chat",
        target_route="/api/chat",
        input_sequence=["prompt"],
        expected_safe_behavior="refuse",
        severity=Severity.CRITICAL,
        impact_domain=ImpactDomain.PHI,
        exploitability="medium",
    )
    store.save_cases([case])
    assert store.cases()[0]["case_id"] == "case_1"


def test_run_store_persists_client_project_scope_and_scan_scope(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.sqlite")
    store.initialize()
    client = Client(client_id="client_test", name="Client Test")
    project = Project(project_id="project_test", client_id=client.client_id, name="Project Test")
    scope = AuthorizedScope(
        scope_id="scope_test",
        client_id=client.client_id,
        project_id=project.project_id,
        name="Owned site scope",
        allowed_hosts=["owned.example"],
        allowed_scan_modes=[SiteScanMode.PASSIVE_HTTP],
        excluded_paths=["/billing"],
        max_urls=3,
        authorization_note="Written authorization recorded.",
    )
    scan = SiteScanRun(
        scan_id="sitescan_scope_test",
        target_url="https://owned.example",
        client_id=client.client_id,
        project_id=project.project_id,
        scope_id=scope.scope_id,
    )

    store.save_client(client)
    store.save_project(project)
    store.save_authorized_scope(scope)
    store.save_site_scan_run(scan)

    assert store.clients()[0]["client_id"] == "client_test"
    assert store.projects(client.client_id)[0]["project_id"] == "project_test"
    assert store.authorized_scope(scope.scope_id) == scope
    assert store.site_scan_runs()[0]["scope_id"] == "scope_test"


def test_default_scope_is_seeded_and_enforced(tmp_path: Path) -> None:
    settings = Settings(
        allowed_hosts=["owned.example"],
        sqlite_path=tmp_path / "runs.sqlite",
    )
    store = RunStore(settings.sqlite_path)
    store.initialize()

    scope = ensure_default_scope(store, settings)

    assert scope.allowed_hosts == ["owned.example"]
    assert scope.scope_id in {stored["scope_id"] for stored in store.authorized_scopes()}
    resolved = resolve_scope_for_scan(
        store=store,
        settings=settings,
        scope_id=scope.scope_id,
        target_url="https://owned.example",
        mode=SiteScanMode.PASSIVE_HTTP,
    )
    assert resolved.scope_id == scope.scope_id
    with pytest.raises(ValueError, match="not authorized by scope"):
        resolve_scope_for_scan(
            store=store,
            settings=settings,
            scope_id=scope.scope_id,
            target_url="https://evil.example",
            mode=SiteScanMode.PASSIVE_HTTP,
        )


def test_public_reports_are_redacted_and_private_store_keeps_details(tmp_path: Path) -> None:
    public_db = tmp_path / "runs.sqlite"
    private_db = tmp_path / "private.sqlite"
    store = RunStore(public_db, private_path=private_db)
    store.initialize()
    report = VulnerabilityReport(
        vulnerability_id="vuln_private_1",
        source_run_id="run_private_1",
        case_id="case_private_1",
        severity=Severity.HIGH,
        impact_domain=ImpactDomain.CLINICAL_WORKFLOW,
        clinical_or_privacy_impact="Sensitive finding impact.",
        minimal_reproduction=["Exploit step that should not be public."],
        observed_behavior="Sensitive observed behavior.",
        expected_behavior="Expected safe behavior.",
        recommended_remediation="Sensitive remediation detail.",
        evidence=["Sensitive evidence."],
    )

    store.save_report(report)

    public_report = store.reports()[0]
    assert public_report["sensitive_details_redacted"] is True
    assert public_report["minimal_reproduction"] == ["Redacted from public operator storage."]
    assert "Exploit step" not in str(public_report)

    private_report = SensitiveFindingStore(private_db).reports()[0]
    assert private_report["minimal_reproduction"] == ["Exploit step that should not be public."]
    assert private_report["evidence"] == ["Sensitive evidence."]


def test_site_scan_findings_are_redacted_and_private_store_keeps_details(
    tmp_path: Path,
) -> None:
    public_db = tmp_path / "runs.sqlite"
    private_db = tmp_path / "private.sqlite"
    store = RunStore(public_db, private_path=private_db)
    store.initialize()
    finding = SiteScanFinding(
        finding_id="sitefind_private_1",
        scan_id="scan_private_1",
        check_id="header.server_disclosure",
        title="Server header discloses implementation detail",
        severity=Severity.INFO,
        description="The entry response exposes a Server header.",
        evidence="Server: Example/1.2.3",
        remediation="Reduce version/detail disclosure.",
    )

    store.save_site_scan_findings([finding])

    public_finding = store.site_scan_findings()[0]
    assert public_finding["sensitive_details_redacted"] is True
    assert public_finding["evidence"] == "Redacted from public operator storage."
    assert "Example/1.2.3" not in str(public_finding)

    private_finding = SensitiveFindingStore(private_db).site_scan_findings()[0]
    assert private_finding["evidence"] == "Server: Example/1.2.3"
    assert private_finding["remediation"] == "Reduce version/detail disclosure."


def test_observations_are_redacted_and_private_store_keeps_raw_details(
    tmp_path: Path,
) -> None:
    public_db = tmp_path / "runs.sqlite"
    private_db = tmp_path / "private.sqlite"
    store = RunStore(public_db, private_path=private_db)
    store.initialize()
    observed = ObservedResponse(
        text="Sensitive wrong-patient response for Margaret Chen.",
        citations=[Citation(source_id="note-1", patient_id="AF-002", quote="Sensitive quote")],
        tool_outcome="Tool returned private detail.",
        black_box_metadata={"raw_body": "Sensitive raw body."},
    )

    store.save_observation("run_private_obs", "case_private_obs", observed)

    public_observation = store.observations()[0]
    assert public_observation["text"] == "Redacted from public operator storage."
    assert public_observation["citations"] == []
    assert public_observation["black_box_metadata"]["sensitive_details_redacted"] is True
    assert "Margaret Chen" not in str(public_observation)

    private_observation = SensitiveFindingStore(private_db).observations()[0]
    assert private_observation["text"] == "Sensitive wrong-patient response for Margaret Chen."
    assert private_observation["citations"][0]["quote"] == "Sensitive quote"


def test_b2b_workflow_records_jobs_audit_and_status_updates(tmp_path: Path) -> None:
    public_db = tmp_path / "runs.sqlite"
    private_db = tmp_path / "private.sqlite"
    store = RunStore(public_db, private_path=private_db, evidence_retention_days=30)
    store.initialize()
    job = ScanJob(
        job_id="scanjob_1",
        scope_id="scope_1",
        client_id="client_1",
        project_id="project_1",
        target_url="https://owned.example",
        status=ScanJobStatus.QUEUED,
    )
    finding = SiteScanFinding(
        finding_id="sitefind_workflow_1",
        scan_id="scan_1",
        check_id="header.csp.missing",
        title="CSP missing",
        severity=Severity.MEDIUM,
        description="No CSP.",
        evidence="Missing header.",
        remediation="Add CSP.",
    )
    report = VulnerabilityReport(
        vulnerability_id="vuln_workflow_1",
        source_run_id="run_1",
        case_id="case_1",
        severity=Severity.HIGH,
        impact_domain=ImpactDomain.CLINICAL_WORKFLOW,
        clinical_or_privacy_impact="Impact.",
        minimal_reproduction=["Step"],
        observed_behavior="Observed.",
        expected_behavior="Expected.",
        recommended_remediation="Fix.",
    )

    store.save_scan_job(job)
    store.save_audit_event(
        AuditEvent(
            action=AuditAction.QUEUE_SITE_SCAN,
            target_type="scan_job",
            target_id=job.job_id,
        )
    )
    store.save_site_scan_findings([finding])
    store.save_report(report)
    updated_finding = store.update_site_scan_finding_status(
        finding.finding_id,
        FindingStatus.RISK_ACCEPTED,
        "Accepted for one release.",
        "scan_retest_1",
    )
    updated_report = store.update_report_status(
        report.vulnerability_id,
        ReportStatus.CONFIRMED,
        "Confirmed by reviewer.",
    )

    assert store.scan_jobs()[0]["job_id"] == "scanjob_1"
    assert store.audit_events()[0]["action"] == AuditAction.QUEUE_SITE_SCAN
    assert updated_finding.status == FindingStatus.RISK_ACCEPTED
    assert updated_finding.retest_scan_ids == ["scan_retest_1"]
    assert updated_report.status == ReportStatus.CONFIRMED
    assert store.site_scan_findings()[0]["retention_expires_at"] is not None
    assert store.reports()[0]["retention_expires_at"] is not None
    private_finding = SensitiveFindingStore(private_db).site_scan_findings()[0]
    assert private_finding["status"] == FindingStatus.RISK_ACCEPTED
