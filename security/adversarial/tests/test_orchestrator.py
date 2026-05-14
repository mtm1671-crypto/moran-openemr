from app.models import (
    AttackCase,
    AttackCategory,
    ImpactDomain,
    JudgeVerdict,
    Severity,
    Verdict,
)
from app.orchestrator import campaign_priorities, prioritize_cases


def _case(
    case_id: str,
    category: AttackCategory,
    severity: Severity = Severity.HIGH,
) -> AttackCase:
    return AttackCase(
        case_id=case_id,
        name=f"Case {case_id}",
        category=category,
        subcategory="mvp",
        surface="chat",
        target_route="/api/chat",
        input_sequence=["Probe the target."],
        expected_safe_behavior="Refuse unsafe behavior.",
        severity=severity,
        impact_domain=ImpactDomain.PHI,
        exploitability="medium",
    )


def test_prioritize_cases_promotes_open_failure_category() -> None:
    phi_case = _case("case_phi", AttackCategory.CROSS_PATIENT_PHI, Severity.CRITICAL)
    clinical_case = _case(
        "case_clinical",
        AttackCategory.CLINICAL_RECOMMENDATION,
        Severity.HIGH,
    )
    verdict = JudgeVerdict(
        run_id="run_fail_phi",
        case_id=phi_case.case_id,
        verdict=Verdict.FAIL,
        reason_code="PATIENT_SCOPE_LEAK",
        reason="Wrong-patient detail disclosed.",
        confidence=1.0,
        severity=Severity.CRITICAL,
        impact_domain=ImpactDomain.PHI,
    )

    ordered = prioritize_cases(
        [clinical_case, phi_case],
        persisted_cases=[
            phi_case.model_dump(mode="json"),
            clinical_case.model_dump(mode="json"),
        ],
        latest_runs=[{"run_id": "run_fail_phi"}],
        verdicts=[verdict.model_dump(mode="json")],
    )

    assert ordered[0].case_id == phi_case.case_id


def test_campaign_priorities_surface_coverage_gaps() -> None:
    phi_case = _case("case_phi", AttackCategory.CROSS_PATIENT_PHI, Severity.CRITICAL)
    clinical_case = _case(
        "case_clinical",
        AttackCategory.CLINICAL_RECOMMENDATION,
        Severity.HIGH,
    )
    verdict = JudgeVerdict(
        run_id="run_pass_clinical",
        case_id=clinical_case.case_id,
        verdict=Verdict.PASS,
        reason_code="SAFE_BEHAVIOR_OBSERVED",
        reason="Safe response.",
        confidence=1.0,
        severity=Severity.HIGH,
        impact_domain=ImpactDomain.PATIENT_SAFETY,
    )

    priorities = campaign_priorities(
        [clinical_case, phi_case],
        persisted_cases=[],
        latest_runs=[{"run_id": "run_pass_clinical"}],
        verdicts=[verdict.model_dump(mode="json")],
    )

    assert priorities[0].category == AttackCategory.CROSS_PATIENT_PHI
    assert "coverage gap" in priorities[0].selection_reason
