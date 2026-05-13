"""Reporting rollups shared by UI and exports."""

from __future__ import annotations

from typing import Any

from .costing import observation_cost_summary
from .models import Verdict


def latest_verdict_by_case(
    verdicts: list[dict[str, Any]],
    runs: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    run_rank = {str(run["run_id"]): index for index, run in enumerate(runs)}
    latest: dict[str, dict[str, Any]] = {}
    for verdict in sorted(verdicts, key=lambda item: run_rank.get(str(item.get("run_id", "")), 10_000)):
        case_id = str(verdict.get("case_id", ""))
        if case_id and case_id not in latest:
            latest[case_id] = verdict
    return latest


def category_rollups(
    cases: list[dict[str, Any]],
    latest_verdicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    verdict_by_case = {str(verdict.get("case_id", "")): verdict for verdict in latest_verdicts}
    rollups: dict[str, dict[str, Any]] = {}
    for case in cases:
        category = str(case.get("category", "unknown"))
        rollup = rollups.setdefault(
            category,
            {
                "category": category,
                "cases": 0,
                "tested": 0,
                "pass": 0,
                "fail": 0,
                "partial": 0,
                "inconclusive": 0,
                "untested": 0,
                "latest_reason": "",
                "latest_run_id": "",
            },
        )
        rollup["cases"] += 1
        verdict = verdict_by_case.get(str(case.get("case_id", "")))
        if not verdict:
            rollup["untested"] += 1
            continue
        rollup["tested"] += 1
        verdict_name = str(verdict.get("verdict", ""))
        if verdict_name in {verdict.value for verdict in Verdict}:
            rollup[verdict_name] += 1
        rollup["latest_reason"] = str(verdict.get("reason_code", ""))
        rollup["latest_run_id"] = str(verdict.get("run_id", ""))
    return [rollups[key] for key in sorted(rollups)]


def current_reports(
    reports: list[dict[str, Any]],
    latest_verdicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failing_run_ids = {
        str(verdict["run_id"])
        for verdict in latest_verdicts
        if verdict.get("verdict") == Verdict.FAIL.value
    }
    return [report for report in reports if str(report.get("source_run_id", "")) in failing_run_ids]


def dashboard_summary(
    *,
    cases: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_verdicts = list(latest_verdict_by_case(verdicts, runs).values())
    rollups = category_rollups(cases, latest_verdicts)
    return {
        "latest_verdicts": latest_verdicts,
        "current_reports": current_reports(reports, latest_verdicts),
        "category_rollups": rollups,
        "untested_categories": [rollup for rollup in rollups if rollup["untested"]],
        "inconclusive_categories": [rollup for rollup in rollups if rollup["inconclusive"]],
        "cost_summary": observation_cost_summary(observations),
        "latest_snapshot": snapshots[0] if snapshots else None,
    }
