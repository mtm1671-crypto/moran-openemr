"""SQLite persistence for adversarial runs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from .models import (
    AgentTraceEvent,
    AttackCase,
    AttackRun,
    AuthorizedScope,
    AuditEvent,
    Client,
    FindingStatus,
    JudgeVerdict,
    ObservedResponse,
    Project,
    RegressionCase,
    ReportStatus,
    ResilienceSnapshot,
    ScanJob,
    ScanJobStatus,
    SiteScanFinding,
    SiteScanRun,
    SuiteSummary,
    VulnerabilityReport,
    utc_now,
)
from .sensitive_findings import (
    SensitiveFindingStore,
    public_report_view,
    public_site_scan_finding_view,
)

SCHEMA_VERSION = 8
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
    def __init__(
        self,
        path: Path,
        private_path: Path | None = None,
        evidence_retention_days: int = 180,
    ) -> None:
        self.path = path
        self.private_store = SensitiveFindingStore(private_path) if private_path else None
        self.evidence_retention_days = evidence_retention_days

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(_schema_sql())
            self._ensure_site_scan_scope_columns(conn)
            self._ensure_site_scan_finding_columns(conn)
            self._redact_existing_public_reports(conn)
            self._redact_existing_site_scan_findings(conn)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def _ensure_site_scan_scope_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(site_scan_runs)").fetchall()
        existing = {str(row["name"]) for row in rows}
        columns = {
            "client_id": "TEXT",
            "project_id": "TEXT",
            "scope_id": "TEXT",
        }
        for column_name, column_type in columns.items():
            if column_name not in existing:
                conn.execute(f"ALTER TABLE site_scan_runs ADD COLUMN {column_name} {column_type}")

    def _ensure_site_scan_finding_columns(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(site_scan_findings)").fetchall()
        existing = {str(row["name"]) for row in rows}
        columns = {
            "status": "TEXT",
        }
        for column_name, column_type in columns.items():
            if column_name not in existing:
                conn.execute(f"ALTER TABLE site_scan_findings ADD COLUMN {column_name} {column_type}")

    def _apply_report_retention(self, report: VulnerabilityReport) -> VulnerabilityReport:
        if report.retention_expires_at is not None:
            return report
        return report.model_copy(
            update={
                "retention_expires_at": utc_now() + timedelta(days=self.evidence_retention_days),
            }
        )

    def _apply_finding_retention(self, finding: SiteScanFinding) -> SiteScanFinding:
        if finding.retention_expires_at is not None:
            return finding
        return finding.model_copy(
            update={
                "retention_expires_at": utc_now() + timedelta(days=self.evidence_retention_days),
            }
        )

    def _redact_existing_public_reports(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT vulnerability_id, payload_json FROM vulnerability_reports"
        ).fetchall()
        for row in rows:
            report = VulnerabilityReport.model_validate(_from_json(row["payload_json"]))
            if report.sensitive_details_redacted:
                continue
            if self.private_store is not None:
                self.private_store.save_report(report)
            public_report = public_report_view(report)
            conn.execute(
                """
                UPDATE vulnerability_reports
                SET payload_json = ?
                WHERE vulnerability_id = ?
                """,
                (_to_json(public_report), row["vulnerability_id"]),
            )

    def _redact_existing_site_scan_findings(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("SELECT finding_id, payload_json FROM site_scan_findings").fetchall()
        for row in rows:
            finding = SiteScanFinding.model_validate(_from_json(row["payload_json"]))
            if finding.sensitive_details_redacted:
                continue
            if self.private_store is not None:
                self.private_store.save_site_scan_finding(finding)
            public_finding = public_site_scan_finding_view(finding)
            conn.execute(
                """
                UPDATE site_scan_findings
                SET payload_json = ?
                WHERE finding_id = ?
                """,
                (_to_json(public_finding), row["finding_id"]),
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
        report = self._apply_report_retention(report)
        if self.private_store is not None:
            self.private_store.save_report(report)
        public_report = public_report_view(report)
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
                    _to_json(public_report),
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

    def save_client(self, client: Client) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO clients
                (client_id, name, active, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    client.client_id,
                    client.name,
                    int(client.active),
                    client.created_at.isoformat(),
                    _to_json(client),
                ),
            )

    def save_project(self, project: Project) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO projects
                (project_id, client_id, name, active, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.client_id,
                    project.name,
                    int(project.active),
                    project.created_at.isoformat(),
                    _to_json(project),
                ),
            )

    def save_authorized_scope(self, scope: AuthorizedScope) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO authorized_scopes
                (scope_id, client_id, project_id, name, active, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    scope.client_id,
                    scope.project_id,
                    scope.name,
                    int(scope.active),
                    _to_json(scope),
                ),
            )

    def save_site_scan_run(self, scan: SiteScanRun) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO site_scan_runs
                (scan_id, target_url, client_id, project_id, scope_id,
                 scan_mode, status, started_at, completed_at,
                 finding_count, highest_severity, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan.scan_id,
                    scan.target_url,
                    scan.client_id,
                    scan.project_id,
                    scan.scope_id,
                    scan.scan_mode,
                    scan.status,
                    scan.started_at.isoformat(),
                    scan.completed_at.isoformat() if scan.completed_at else None,
                    scan.finding_count,
                    scan.highest_severity,
                    _to_json(scan),
                ),
            )

    def save_site_scan_findings(self, findings: Iterable[SiteScanFinding]) -> None:
        with self.connect() as conn:
            for finding in findings:
                finding = self._apply_finding_retention(finding)
                if self.private_store is not None:
                    self.private_store.save_site_scan_finding(finding)
                public_finding = public_site_scan_finding_view(finding)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO site_scan_findings
                    (finding_id, scan_id, check_id, severity, title, status, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        finding.finding_id,
                        finding.scan_id,
                        finding.check_id,
                        finding.severity,
                        finding.title,
                        finding.status,
                        _to_json(public_finding),
                    ),
                )

    def save_scan_job(self, job: ScanJob) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scan_jobs
                (job_id, scope_id, client_id, project_id, target_url, scan_mode,
                 status, created_at, completed_at, scan_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.scope_id,
                    job.client_id,
                    job.project_id,
                    job.target_url,
                    job.scan_mode,
                    job.status,
                    job.created_at.isoformat(),
                    job.completed_at.isoformat() if job.completed_at else None,
                    job.scan_id,
                    _to_json(job),
                ),
            )

    def save_audit_event(self, event: AuditEvent) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_events
                (audit_id, action, actor_role, target_type, target_id, created_at, success, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.audit_id,
                    event.action,
                    event.actor_role,
                    event.target_type,
                    event.target_id,
                    event.created_at.isoformat(),
                    int(event.success),
                    _to_json(event),
                ),
            )

    def update_report_status(
        self,
        vulnerability_id: str,
        status: ReportStatus,
        status_note: str = "",
    ) -> VulnerabilityReport:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM vulnerability_reports WHERE vulnerability_id = ?",
                (vulnerability_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"vulnerability report not found: {vulnerability_id}")
            report = VulnerabilityReport.model_validate(_from_json(row["payload_json"]))
            updated = report.model_copy(
                update={
                    "status": status,
                    "status_note": status_note,
                    "last_status_change_at": utc_now(),
                }
            )
            conn.execute(
                """
                UPDATE vulnerability_reports
                SET status = ?, payload_json = ?
                WHERE vulnerability_id = ?
                """,
                (updated.status, _to_json(updated), vulnerability_id),
            )
        if self.private_store is not None:
            self.private_store.update_report_status(vulnerability_id, updated.status, status_note)
        return updated

    def update_site_scan_finding_status(
        self,
        finding_id: str,
        status: FindingStatus,
        status_note: str = "",
        retest_scan_id: str | None = None,
    ) -> SiteScanFinding:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM site_scan_findings WHERE finding_id = ?",
                (finding_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"site scan finding not found: {finding_id}")
            finding = SiteScanFinding.model_validate(_from_json(row["payload_json"]))
            retest_scan_ids = list(finding.retest_scan_ids)
            if retest_scan_id and retest_scan_id not in retest_scan_ids:
                retest_scan_ids.append(retest_scan_id)
            updated = finding.model_copy(
                update={
                    "status": status,
                    "status_note": status_note,
                    "retest_scan_ids": retest_scan_ids,
                    "last_status_change_at": utc_now(),
                }
            )
            conn.execute(
                """
                UPDATE site_scan_findings
                SET status = ?, payload_json = ?
                WHERE finding_id = ?
                """,
                (updated.status, _to_json(updated), finding_id),
            )
        if self.private_store is not None:
            self.private_store.update_site_scan_finding_status(
                finding_id,
                updated.status,
                status_note,
                retest_scan_id,
            )
        return updated

    def deactivate_scope(self, scope_id: str) -> AuthorizedScope:
        scope = self.authorized_scope(scope_id)
        if scope is None:
            raise ValueError(f"authorized scope not found: {scope_id}")
        updated = scope.model_copy(update={"active": False, "updated_at": utc_now()})
        self.save_authorized_scope(updated)
        return updated

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

    def scan_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM scan_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def scan_job(self, job_id: str) -> ScanJob | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM scan_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return ScanJob.model_validate(_from_json(row["payload_json"]))

    def cancel_scan_job(self, job_id: str) -> ScanJob:
        job = self.scan_job(job_id)
        if job is None:
            raise ValueError(f"scan job not found: {job_id}")
        if job.status == ScanJobStatus.QUEUED:
            updated = job.model_copy(
                update={
                    "status": ScanJobStatus.CANCELLED,
                    "cancellation_requested": True,
                    "completed_at": utc_now(),
                }
            )
        elif job.status == ScanJobStatus.RUNNING:
            updated = job.model_copy(update={"cancellation_requested": True})
        else:
            updated = job
        self.save_scan_job(updated)
        return updated

    def clients(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT payload_json FROM clients ORDER BY name").fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def projects(self, client_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if client_id:
                rows = conn.execute(
                    "SELECT payload_json FROM projects WHERE client_id = ? ORDER BY name",
                    (client_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT payload_json FROM projects ORDER BY name").fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def authorized_scopes(self, active_only: bool = True) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT payload_json FROM authorized_scopes WHERE active = 1 ORDER BY name"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload_json FROM authorized_scopes ORDER BY name"
                ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def authorized_scope(self, scope_id: str) -> AuthorizedScope | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM authorized_scopes WHERE scope_id = ?",
                (scope_id,),
            ).fetchone()
        if row is None:
            return None
        return AuthorizedScope.model_validate(_from_json(row["payload_json"]))

    def site_scan_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM site_scan_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def site_scan_findings(self, scan_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if scan_id:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM site_scan_findings
                    WHERE scan_id = ?
                    ORDER BY severity, check_id
                    """,
                    (scan_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT payload_json FROM site_scan_findings").fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def audit_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM audit_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
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
