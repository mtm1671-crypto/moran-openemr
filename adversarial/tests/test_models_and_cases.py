from pathlib import Path

import pytest
from pydantic import ValidationError

from app.case_loader import load_cases
from app.models import AttackCase, AttackCategory, ImpactDomain, InjectionLayer, Severity, Verdict


def test_seed_cases_cover_hospital_director_suite() -> None:
    case_root = Path(__file__).resolve().parents[1] / "evals" / "week3" / "cases"
    cases = load_cases(case_root)
    categories = {case.category for case in cases}
    assert AttackCategory.CROSS_PATIENT_PHI in categories
    assert AttackCategory.AUTHORIZATION_SESSION in categories
    assert AttackCategory.CLINICAL_RECOMMENDATION in categories
    assert AttackCategory.DIRECT_PROMPT_INJECTION in categories
    assert AttackCategory.INDIRECT_INJECTION in categories
    assert AttackCategory.MULTI_TURN_MANIPULATION in categories
    assert AttackCategory.TOOL_MISUSE in categories
    assert AttackCategory.COST_AMPLIFICATION in categories
    assert AttackCategory.CITATION_MANIPULATION in categories
    assert AttackCategory.STATE_CORRUPTION in categories
    assert AttackCategory.IDENTITY_HIJACKING in categories
    injection_layers = {case.injection_layer for case in cases}
    assert InjectionLayer.PROMPT_SIMULATION in injection_layers
    assert InjectionLayer.UPLOADED_DOCUMENT in injection_layers
    assert InjectionLayer.SEEDED_NOTE in injection_layers


def test_case_schema_rejects_empty_input_sequence() -> None:
    with pytest.raises(ValidationError):
        AttackCase(
            case_id="bad",
            name="Bad",
            category=AttackCategory.CROSS_PATIENT_PHI,
            subcategory="bad",
            surface="chat",
            target_route="/api/chat",
            input_sequence=[],
            expected_safe_behavior="Refuse.",
            severity=Severity.CRITICAL,
            impact_domain=ImpactDomain.PHI,
            exploitability="low",
        )


def test_enums_lock_expected_values() -> None:
    assert Severity.CRITICAL == "Critical"
    assert ImpactDomain.AUTHORIZATION == "Authorization"
    assert InjectionLayer.PROMPT_SIMULATION == "prompt_simulation"
    assert Verdict.INCONCLUSIVE == "inconclusive"
