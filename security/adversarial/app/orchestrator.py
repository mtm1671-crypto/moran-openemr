"""Case prioritization for adaptive adversarial suites."""

from __future__ import annotations

from typing import Any

from .models import AttackCase, AttackCategory, CampaignPriority, ReportStatus, Severity, Verdict
from .reporting import category_rollups, latest_verdict_by_case

CLOSED_REPORT_STATUSES = {
    ReportStatus.FALSE_POSITIVE.value,
    ReportStatus.RESOLVED.value,
    ReportStatus.RISK_ACCEPTED.value,
}

SEVERITY_SCORES = {
    Severity.CRITICAL.value: 5.0,
    Severity.HIGH.value: 4.0,
    Severity.MEDIUM.value: 3.0,
    Severity.LOW.value: 2.0,
    Severity.INFO.value: 1.0,
}


def prioritize_cases(
    cases: list[AttackCase],
    *,
    persisted_cases: list[dict[str, Any]],
    latest_runs: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    reports: list[dict[str, Any]] | None = None,
) -> list[AttackCase]:
    """Sort cases by open failure severity, category coverage gaps, then case risk."""

    if not cases:
        return []
    latest_by_case = latest_verdict_by_case(verdicts, latest_runs)
    closed_run_ids = _closed_report_run_ids(reports or [])
    priorities = {
        priority.category.value: priority
        for priority in campaign_priorities(
            cases,
            persisted_cases=persisted_cases,
            latest_runs=latest_runs,
            verdicts=verdicts,
            reports=reports,
        )
    }

    def sort_key(indexed_case: tuple[int, AttackCase]) -> tuple[float, float, float, int]:
        index, case = indexed_case
        priority = priorities.get(case.category.value)
        category_score = priority.total_priority_score if priority else 0.0
        exact_open_failure = _open_failure_weight(
            latest_by_case.get(case.case_id),
            closed_run_ids,
        )
        case_risk = SEVERITY_SCORES[case.severity.value]
        return (exact_open_failure, category_score, case_risk, -index)

    return [case for _, case in sorted(enumerate(cases), key=sort_key, reverse=True)]


def campaign_priorities(
    cases: list[AttackCase],
    *,
    persisted_cases: list[dict[str, Any]],
    latest_runs: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    reports: list[dict[str, Any]] | None = None,
) -> list[CampaignPriority]:
    """Build category-level priority records from coverage and open failures."""

    case_payloads = _merged_case_payloads(cases, persisted_cases)
    latest_by_case = latest_verdict_by_case(verdicts, latest_runs)
    rollups = {
        str(rollup["category"]): rollup
        for rollup in category_rollups(case_payloads, list(latest_by_case.values()))
    }
    category_by_case = {
        str(case_payload["case_id"]): str(case_payload["category"])
        for case_payload in case_payloads
    }
    closed_run_ids = _closed_report_run_ids(reports or [])
    open_failure_by_category: dict[str, float] = {}
    for case_id, verdict in latest_by_case.items():
        if not _is_open_failure(verdict, closed_run_ids):
            continue
        category = category_by_case.get(case_id)
        if not category:
            continue
        open_failure_by_category[category] = max(
            open_failure_by_category.get(category, 0.0),
            _severity_score(verdict.get("severity")),
        )

    max_severity_by_category: dict[str, float] = {}
    regression_by_category: dict[str, bool] = {}
    for case_payload in case_payloads:
        category = str(case_payload["category"])
        max_severity_by_category[category] = max(
            max_severity_by_category.get(category, 0.0),
            _severity_score(case_payload.get("severity")),
        )
        if bool(case_payload.get("regression_candidate", False)):
            regression_by_category[category] = True

    priorities: list[CampaignPriority] = []
    for category, rollup in rollups.items():
        try:
            category_model = AttackCategory(category)
        except ValueError:
            continue
        total_cases = max(int(rollup.get("cases", 0)), 1)
        coverage_gap_score = float(rollup.get("untested", 0)) / total_cases
        inconclusive_score = float(rollup.get("inconclusive", 0)) / total_cases
        recent_failure_score = open_failure_by_category.get(category, 0.0) / 5.0
        severity_weight = max_severity_by_category.get(category, 0.0) / 5.0
        regression_weight = 0.2 if regression_by_category.get(category, False) else 0.0
        total_priority_score = (
            recent_failure_score * 5.0
            + coverage_gap_score * 3.0
            + inconclusive_score
            + severity_weight
            + regression_weight
        )
        priorities.append(
            CampaignPriority(
                category=category_model,
                coverage_gap_score=coverage_gap_score,
                severity_weight=severity_weight,
                recent_failure_score=recent_failure_score,
                inconclusive_score=inconclusive_score,
                regression_weight=regression_weight,
                total_priority_score=total_priority_score,
                selection_reason=_selection_reason(
                    coverage_gap_score,
                    recent_failure_score,
                    inconclusive_score,
                ),
            )
        )
    return sorted(priorities, key=lambda priority: priority.total_priority_score, reverse=True)


def _merged_case_payloads(
    cases: list[AttackCase],
    persisted_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_case_id = {str(case.get("case_id", "")): case for case in persisted_cases}
    by_case_id.update({case.case_id: case.model_dump(mode="json") for case in cases})
    return [case for case_id, case in by_case_id.items() if case_id]


def _closed_report_run_ids(reports: list[dict[str, Any]]) -> set[str]:
    return {
        str(report.get("source_run_id", ""))
        for report in reports
        if str(report.get("status", "")) in CLOSED_REPORT_STATUSES
    }


def _is_open_failure(verdict: dict[str, Any] | None, closed_run_ids: set[str]) -> bool:
    if not verdict or verdict.get("verdict") != Verdict.FAIL.value:
        return False
    return str(verdict.get("run_id", "")) not in closed_run_ids


def _open_failure_weight(verdict: dict[str, Any] | None, closed_run_ids: set[str]) -> float:
    if not _is_open_failure(verdict, closed_run_ids):
        return 0.0
    assert verdict is not None
    return _severity_score(verdict.get("severity"))


def _severity_score(value: object) -> float:
    return SEVERITY_SCORES.get(str(value), 0.0)


def _selection_reason(
    coverage_gap_score: float,
    recent_failure_score: float,
    inconclusive_score: float,
) -> str:
    reasons: list[str] = []
    if recent_failure_score:
        reasons.append("open failure queue")
    if coverage_gap_score:
        reasons.append("coverage gap")
    if inconclusive_score:
        reasons.append("inconclusive verdicts")
    return ", ".join(reasons) or "baseline severity ordering"
