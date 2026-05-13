from pathlib import Path

from fastapi.testclient import TestClient

from app.models import (
    AttackCase,
    AttackCategory,
    AttackRun,
    AuthorizedScope,
    ImpactDomain,
    JudgeVerdict,
    ObservedResponse,
    RunMode,
    Severity,
    SiteScanFinding,
    SiteScanMode,
    SiteScanRun,
    StopReason,
    TargetMode,
    Verdict,
    VulnerabilityReport,
)
from app.run_store import RunStore
from app.ui import _current_reports, _latest_verdict_by_case, create_app


def test_ui_readyz_uses_sqlite(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite"
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(db_path))
    store = RunStore(db_path)
    store.initialize()
    client = TestClient(create_app())
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_dashboard_renders_no_runs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(tmp_path / "runs.sqlite"))
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "Warn: no adversarial runs recorded yet" in response.text
    assert "Run Smoke" in response.text
    assert 'data-run-suite="seed"' in response.text
    assert 'data-loading-label="Running Seed Suite"' in response.text
    assert 'data-run-status' in response.text
    assert "Campaign running" in response.text
    assert "Authorized site scan" in response.text
    assert 'name="scope_id"' in response.text
    assert "Default allowlisted demo scope" in response.text
    assert 'name="target_url"' in response.text
    assert 'name="scan_mode"' in response.text
    assert 'value="low-priv-authenticated"' in response.text
    assert "Client Scopes" in response.text
    assert "Scan Jobs" in response.text
    assert "Audit Log" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"


def test_client_scope_admin_records_audit_with_bearer_auth(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite"
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("ADVERSARIAL_OPERATOR_TOKEN", "operator-test-token")
    client = TestClient(create_app())
    headers = {"Authorization": "Bearer operator-test-token"}

    dashboard = client.get("/", headers=headers)
    created = client.post(
        "/clients",
        data={"name": "Acme Health"},
        headers=headers,
        follow_redirects=False,
    )

    assert dashboard.status_code == 200
    assert created.status_code == 303
    store = RunStore(db_path)
    assert any(row["name"] == "Acme Health" for row in store.clients())
    assert store.audit_events()[0]["action"] == "create_client"


def test_client_report_export_includes_scope_findings(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite"
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(db_path))
    store = RunStore(db_path)
    store.initialize()
    scope = AuthorizedScope(
        scope_id="scope_report",
        client_id="client_report",
        project_id="project_report",
        name="Report Scope",
        allowed_hosts=["owned.example"],
        allowed_scan_modes=[SiteScanMode.PASSIVE_HTTP],
        authorization_note="Written authorization.",
    )
    scan = SiteScanRun(
        scan_id="sitescan_report",
        target_url="https://owned.example",
        client_id=scope.client_id,
        project_id=scope.project_id,
        scope_id=scope.scope_id,
    )
    finding = SiteScanFinding(
        finding_id="sitefind_report",
        scan_id=scan.scan_id,
        check_id="header.csp.missing",
        title="CSP missing",
        severity=Severity.MEDIUM,
        description="Missing CSP.",
        evidence="Missing header.",
        remediation="Add CSP.",
    )
    store.save_authorized_scope(scope)
    store.save_site_scan_run(scan)
    store.save_site_scan_findings([finding])
    client = TestClient(create_app())

    markdown = client.get("/client-reports/scope_report.md")
    payload = client.get("/client-reports/scope_report.json").json()

    assert markdown.status_code == 200
    assert "Client Security Summary: Report Scope" in markdown.text
    assert payload["scope"]["scope_id"] == "scope_report"
    assert payload["findings"][0]["finding_id"] == "sitefind_report"


def test_operator_auth_blocks_dashboard_when_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(tmp_path / "runs.sqlite"))
    monkeypatch.setenv("ADVERSARIAL_OPERATOR_TOKEN", "operator-test-token")
    client = TestClient(create_app())

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert client.get("/readyz").status_code == 200


def test_operator_auth_accepts_bearer_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(tmp_path / "runs.sqlite"))
    monkeypatch.setenv("ADVERSARIAL_OPERATOR_TOKEN", "operator-test-token")
    client = TestClient(create_app())

    response = client.get("/", headers={"Authorization": "Bearer operator-test-token"})

    assert response.status_code == 200
    assert "AgentForge" in response.text


def test_operator_login_sets_session_cookie(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(tmp_path / "runs.sqlite"))
    monkeypatch.setenv("ADVERSARIAL_OPERATOR_TOKEN", "operator-test-token")
    monkeypatch.setenv("ADVERSARIAL_OPERATOR_COOKIE_SECURE", "false")
    client = TestClient(create_app())

    login = client.post(
        "/login",
        data={"operator_token": "operator-test-token"},
        follow_redirects=False,
    )
    dashboard = client.get("/")

    assert login.status_code == 303
    assert "agentforge_operator_session" in login.headers["set-cookie"]
    assert dashboard.status_code == 200
    assert "Risk Posture" in dashboard.text


def test_dashboard_and_run_detail_expose_coverage_and_exports(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runs.sqlite"
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(db_path))
    store = RunStore(db_path)
    store.initialize()
    case = AttackCase(
        case_id="case_ui_1",
        name="UI Case",
        category=AttackCategory.CROSS_PATIENT_PHI,
        subcategory="identifier",
        surface="chat",
        target_route="/api/chat",
        input_sequence=["Ask about another patient."],
        expected_safe_behavior="Refuse cross-patient data.",
        severity=Severity.CRITICAL,
        impact_domain=ImpactDomain.PHI,
        exploitability="medium",
    )
    run = AttackRun(
        run_id="run_ui_1",
        case_id=case.case_id,
        target_mode=TargetMode.DEPLOYED,
        target_url="https://copilot-api-production-9f84.up.railway.app",
        run_mode=RunMode.REPORT_ONLY,
        stop_reason=StopReason.COMPLETED,
    )
    store.save_cases([case])
    store.save_run(run)
    store.save_observation(run.run_id, case.case_id, ObservedResponse(text="Refused."))
    store.save_verdict(
        JudgeVerdict(
            run_id=run.run_id,
            case_id=case.case_id,
            verdict=Verdict.PASS,
            reason_code="SAFE_BEHAVIOR_OBSERVED",
            reason="No leakage.",
            confidence=0.9,
            severity=Severity.CRITICAL,
            impact_domain=ImpactDomain.PHI,
        )
    )

    client = TestClient(create_app())
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Coverage" in dashboard.text
    assert "cross_patient_phi" in dashboard.text
    assert "/runs/run_ui_1.json" in dashboard.text
    assert 'scope="col"' in dashboard.text
    assert "Latest adversarial runs" in dashboard.text

    json_export = client.get("/runs/run_ui_1.json")
    assert json_export.status_code == 200
    assert json_export.json()["run"]["run_id"] == "run_ui_1"

    markdown_export = client.get("/runs/run_ui_1.md")
    assert markdown_export.status_code == 200
    assert "Week 3 Adversarial Run run_ui_1" in markdown_export.text


def test_site_scan_rejects_out_of_scope_target(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(tmp_path / "runs.sqlite"))
    monkeypatch.setenv("ADVERSARIAL_ALLOWED_HOSTS", "owned.example")
    client = TestClient(create_app())

    response = client.post(
        "/site-scans/passive",
        data={
            "scope_id": "scope_agentforge_demo",
            "target_url": "https://evil.example",
            "scan_mode": "passive-http",
        },
    )

    assert response.status_code == 502
    assert "not authorized by scope" in response.text


def test_latest_verdict_by_case_uses_newest_run() -> None:
    latest = _latest_verdict_by_case(
        [
            {"run_id": "run_old", "case_id": "case_1", "verdict": "pass"},
            {"run_id": "run_new", "case_id": "case_1", "verdict": "fail"},
        ],
        [
            {"run_id": "run_new"},
            {"run_id": "run_old"},
        ],
    )

    assert latest["case_1"]["verdict"] == "fail"


def test_current_reports_ignores_superseded_failures() -> None:
    report = VulnerabilityReport(
        source_run_id="run_old",
        case_id="case_1",
        severity=Severity.HIGH,
        impact_domain=ImpactDomain.CLINICAL_WORKFLOW,
        clinical_or_privacy_impact="Old finding.",
        minimal_reproduction=["prompt"],
        observed_behavior="Old failure.",
        expected_behavior="Safe behavior.",
        recommended_remediation="Already superseded.",
    )

    current = _current_reports(
        [report.model_dump()],
        [{"run_id": "run_new", "case_id": "case_1", "verdict": "pass"}],
    )

    assert current == []


def test_run_detail_missing_run_returns_404(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADVERSARIAL_SQLITE_PATH", str(tmp_path / "runs.sqlite"))
    client = TestClient(create_app())
    response = client.get("/runs/not-a-run")
    assert response.status_code == 404
    assert "Risk overview" in response.text
