from pathlib import Path

import pytest

from app.config import Settings
from app.models import (
    AttackCase,
    AttackCategory,
    ImpactDomain,
    Severity,
    SiteScanFinding,
    VulnerabilityReport,
)
from app.run_store import RunStore
from app.sensitive_findings import SensitiveFindingStore


def test_allowlist_rejects_unknown_host() -> None:
    settings = Settings(allowed_hosts=["localhost"], local_target_url="https://evil.example")
    with pytest.raises(ValueError, match="not allowlisted"):
        settings.validate_target_allowed()


def test_deployed_requires_synthetic_clinician_token() -> None:
    settings = Settings(target_mode="deployed", synthetic_clinician_token=None)
    with pytest.raises(ValueError, match="deployed runs require"):
        settings.validate_ready_for_run()


def test_deployed_accepts_synthetic_password_grant_settings() -> None:
    settings = Settings(
        target_mode="deployed",
        synthetic_clinician_token_url="https://openemr-production-f5ed.up.railway.app/oauth2/default/token",
        synthetic_clinician_client_id="client-id",
        synthetic_clinician_username="admin",
        synthetic_clinician_password="secret",
    )
    settings.validate_ready_for_run()
    assert settings.has_synthetic_clinician_auth is True


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
