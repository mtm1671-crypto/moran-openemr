from pathlib import Path

import pytest

from app.config import Settings
from app.models import AttackCase, AttackCategory, ImpactDomain, Severity
from app.run_store import RunStore


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
