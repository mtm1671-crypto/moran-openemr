"""Regression promotion and replay helpers."""

from __future__ import annotations

import argparse
from typing import Any

from .config import Settings
from .models import (
    AttackCase,
    RegressionCase,
    RegressionStatus,
    ReportStatus,
    VulnerabilityReport,
)
from .run_store import RunStore


def candidate_from_failure(
    *,
    report: VulnerabilityReport,
    case: AttackCase,
    promotion_reason: str,
) -> RegressionCase:
    replay_case = case.model_copy(
        update={
            "case_id": f"reg_{case.case_id}",
            "parent_case_id": case.case_id,
            "mutation_rationale": "Regression replay generated from a non-pass verdict.",
        }
    )
    return RegressionCase(
        source_report_id=report.vulnerability_id,
        source_run_id=report.source_run_id,
        case_id=case.case_id,
        status=RegressionStatus.CANDIDATE,
        replay_case=replay_case,
        promotion_reason=promotion_reason,
    )


def promote_confirmed_report(store: RunStore, vulnerability_id: str) -> RegressionCase:
    report_payload = _find_by_key(store.reports(), "vulnerability_id", vulnerability_id)
    if report_payload is None:
        raise ValueError(f"report not found: {vulnerability_id}")
    report = VulnerabilityReport.model_validate(report_payload)
    if report.status != ReportStatus.CONFIRMED:
        raise ValueError("only confirmed reports can be promoted to regression cases")
    case_payload = _find_by_key(store.cases(), "case_id", report.case_id)
    if case_payload is None:
        raise ValueError(f"case not found for report: {report.case_id}")
    regression = candidate_from_failure(
        report=report,
        case=AttackCase.model_validate(case_payload),
        promotion_reason="Confirmed vulnerability promoted for replay.",
    ).model_copy(update={"status": RegressionStatus.PROMOTED})
    store.save_regression_case(regression)
    return regression


def _find_by_key(
    rows: list[dict[str, Any]],
    key: str,
    value: str,
) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get(key, "")) == value:
            return row
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    promote = subparsers.add_parser("promote")
    promote.add_argument("--report-id", required=True)
    promote.add_argument("--db", default=None)
    args = parser.parse_args()

    settings = Settings()
    if args.db:
        settings.sqlite_path = args.db
    store = RunStore(settings.sqlite_path, private_path=settings.private_sqlite_path)
    if args.command == "promote":
        regression = promote_confirmed_report(store, args.report_id)
        print(regression.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
