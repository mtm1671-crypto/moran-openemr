"""SQLite persistence for adversarial runs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from .models import (
    AgentTraceEvent,
    AttackCase,
    AttackRun,
    JudgeVerdict,
    ObservedResponse,
    RegressionCase,
    ResilienceSnapshot,
    SuiteSummary,
    VulnerabilityReport,
)

SCHEMA_VERSION = 3
MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / "001_initial.sql"


def _schema_sql() -> str:
    if not MIGRATION_PATH.exists():
        raise FileNotFoundError(f"missing SQLite migration: {MIGRATION_PATH}")
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _to_json(model: BaseModel) -> str:
    return model.model_dump_json()


def _from_json(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("stored payload JSON must be an object")
    return cast(dict[str, Any], payload)


class RunStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(_schema_sql())
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def readiness(self) -> tuple[bool, str]:
        try:
            self.initialize()
            with self.connect() as conn:
                row = conn.execute(
                    "SELECT value FROM schema_meta WHERE key = 'schema_version'"
                ).fetchone()
            if not row or row["value"] != str(SCHEMA_VERSION):
                return False, "schema version missing or stale"
        except (OSError, sqlite3.Error) as exc:
            return False, f"sqlite not ready: {exc}"
        return True, "ok"

    def save_cases(self, cases: Iterable[AttackCase]) -> None:
        with self.connect() as conn:
            for case in cases:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO attack_cases
                    (case_id, category, severity, impact_domain, payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        case.case_id,
                        case.category,
                        case.severity,
                        case.impact_domain,
                        _to_json(case),
                    ),
                )

    def save_run(self, run: AttackRun) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO attack_runs
                (run_id, case_id, target_mode, target_url, run_mode, started_at,
                 completed_at, stop_reason, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.case_id,
                    run.target_mode,
                    run.target_url,
                    run.run_mode,
                    run.started_at.isoformat(),
                    run.completed_at.isoformat() if run.completed_at else None,
                    run.stop_reason,
                    _to_json(run),
                ),
            )

    def save_trace(self, event: AgentTraceEvent) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_trace_events
                (trace_id, run_id, agent_name, event_type, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.trace_id,
                    event.run_id,
                    event.agent_name,
                    event.event_type,
                    event.created_at.isoformat(),
                    _to_json(event),
                ),
            )

    def save_observation(self, run_id: str, case_id: str, observed: ObservedResponse) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO observed_responses
                (run_id, case_id, status_code, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    case_id,
                    observed.status_code,
                    _to_json(observed),
                ),
            )

    def save_verdict(self, verdict: JudgeVerdict) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO judge_verdicts
                (run_id, case_id, verdict, severity, impact_domain, requires_human_review, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    verdict.run_id,
                    verdict.case_id,
                    verdict.verdict,
                    verdict.severity,
                    verdict.impact_domain,
                    int(verdict.requires_human_review),
                    _to_json(verdict),
                ),
            )

    def save_report(self, report: VulnerabilityReport) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO vulnerability_reports
                (vulnerability_id, source_run_id, case_id, severity, impact_domain, status, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.vulnerability_id,
                    report.source_run_id,
                    report.case_id,
                    report.severity,
                    report.impact_domain,
                    report.status,
                    _to_json(report),
                ),
            )

    def save_snapshot(self, snapshot: ResilienceSnapshot) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO resilience_snapshots
                (snapshot_id, run_id, created_at, risk_weighted_score, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.run_id,
                    snapshot.created_at.isoformat(),
                    snapshot.risk_weighted_score,
                    _to_json(snapshot),
                ),
            )

    def save_regression_case(self, regression: RegressionCase) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO regression_cases
                (regression_id, source_report_id, source_run_id, case_id, status, created_at,
                 payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    regression.regression_id,
                    regression.source_report_id,
                    regression.source_run_id,
                    regression.case_id,
                    regression.status,
                    regression.created_at.isoformat(),
                    _to_json(regression),
                ),
            )

    def save_suite_summary(self, summary: SuiteSummary) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO suite_summaries
                (summary_id, suite, target_mode, run_mode, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.summary_id,
                    summary.suite,
                    summary.target_mode,
                    summary.run_mode,
                    summary.created_at.isoformat(),
                    _to_json(summary),
                ),
            )

    def latest_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM attack_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def cases(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM attack_cases
                ORDER BY category, severity, case_id
                """
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def verdicts(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT payload_json FROM judge_verdicts").fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def observations(self, run_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if run_id:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM observed_responses
                    WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT payload_json FROM observed_responses").fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def reports(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT payload_json FROM vulnerability_reports").fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def snapshots(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM resilience_snapshots ORDER BY created_at DESC"
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def regression_cases(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM regression_cases ORDER BY created_at DESC"
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def suite_summaries(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM suite_summaries ORDER BY created_at DESC"
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def trace_events(self, run_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if run_id:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM agent_trace_events
                    WHERE run_id = ?
                    ORDER BY created_at
                    """,
                    (run_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload_json FROM agent_trace_events ORDER BY created_at"
                ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]
