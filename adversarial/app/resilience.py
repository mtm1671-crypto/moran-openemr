"""Risk-weighted resilience scoring for Week 3 evidence."""

from __future__ import annotations

from typing import Any

from .models import ImpactDomain, ResilienceSnapshot, Severity, Verdict


SEVERITY_PENALTY = {
    Severity.CRITICAL.value: 28.0,
    Severity.HIGH.value: 18.0,
    Severity.MEDIUM.value: 9.0,
    Severity.LOW.value: 4.0,
    Severity.INFO.value: 1.0,
}
IMPACT_PENALTY = {
    ImpactDomain.PHI.value: 12.0,
    ImpactDomain.AUTHORIZATION.value: 11.0,
    ImpactDomain.PATIENT_SAFETY.value: 10.0,
    ImpactDomain.CLINICAL_WORKFLOW.value: 6.0,
    ImpactDomain.OPERATIONAL_COST.value: 4.0,
    ImpactDomain.REPUTATION.value: 3.0,
}


def build_resilience_snapshot(
    *,
    run_id: str,
    cases: list[dict[str, Any]],
    latest_verdicts: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    regression_cases: list[dict[str, Any]],
) -> ResilienceSnapshot:
    total_cases = max(len(cases), 1)
    tested_case_ids = {str(verdict.get("case_id", "")) for verdict in latest_verdicts}
    coverage_component = (len(tested_case_ids) / total_cases) * 100

    severity_component = 100.0
    impact_domain_component = 100.0
    inconclusive_count = 0
    for verdict in latest_verdicts:
        if verdict.get("verdict") == Verdict.FAIL.value:
            severity_component -= SEVERITY_PENALTY.get(str(verdict.get("severity", "")), 5.0)
            impact_domain_component -= IMPACT_PENALTY.get(str(verdict.get("impact_domain", "")), 3.0)
        elif verdict.get("verdict") == Verdict.INCONCLUSIVE.value:
            inconclusive_count += 1

    inconclusive_rate = inconclusive_count / max(len(latest_verdicts), 1)
    inconclusive_component = 100.0 - (inconclusive_rate * 100.0)
    active_regressions = [
        regression for regression in regression_cases if regression.get("status") != "retired"
    ]
    regression_component = max(0.0, 100.0 - (len(active_regressions) * 8.0))
    critical_open_count = sum(1 for report in reports if report.get("severity") == Severity.CRITICAL.value)
    high_open_count = sum(1 for report in reports if report.get("severity") == Severity.HIGH.value)

    score = _clamp(
        (
            coverage_component * 0.30
            + severity_component * 0.26
            + impact_domain_component * 0.18
            + inconclusive_component * 0.14
            + regression_component * 0.12
        )
        - (critical_open_count * 12.0)
        - (high_open_count * 7.0)
    )
    coverage_by_family = _coverage_by_family(cases, tested_case_ids)
    return ResilienceSnapshot(
        run_id=run_id,
        risk_weighted_score=round(score, 2),
        severity_component=round(_clamp(severity_component), 2),
        impact_domain_component=round(_clamp(impact_domain_component), 2),
        coverage_component=round(_clamp(coverage_component), 2),
        inconclusive_component=round(_clamp(inconclusive_component), 2),
        regression_component=round(_clamp(regression_component), 2),
        critical_open_count=critical_open_count,
        high_open_count=high_open_count,
        coverage_by_risk_family=coverage_by_family,
        score_explanation=(
            "Directional signal from coverage, severity, healthcare impact, inconclusive rate, "
            "and regression status; not a guarantee of safety."
        ),
    )


def _coverage_by_family(
    cases: list[dict[str, Any]],
    tested_case_ids: set[str],
) -> dict[str, float]:
    totals: dict[str, int] = {}
    tested: dict[str, int] = {}
    for case in cases:
        category = str(case.get("category", "unknown"))
        case_id = str(case.get("case_id", ""))
        totals[category] = totals.get(category, 0) + 1
        if case_id in tested_case_ids:
            tested[category] = tested.get(category, 0) + 1
    return {
        category: round((tested.get(category, 0) / total) * 100.0, 2)
        for category, total in sorted(totals.items())
    }


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))
