"""Private storage for sensitive finding details.

The public operator database keeps only triage metadata. Reproduction steps,
raw evidence, and remediation details live in this separate store so a dashboard
or export leak does not hand an attacker a ready-made playbook.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from .models import (
    FindingStatus,
    ObservedResponse,
    ReportStatus,
    SiteScanFinding,
    VulnerabilityReport,
)

PRIVATE_SCHEMA_VERSION = "4"

PRIVATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensitive_vulnerability_reports (
    vulnerability_id TEXT PRIMARY KEY,
    source_run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensitive_site_scan_findings (
    finding_id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,
    check_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensitive_observed_responses (
    run_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);
"""


class SensitiveFindingStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(PRIVATE_SCHEMA_SQL)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
                (PRIVATE_SCHEMA_VERSION,),
            )

    def save_report(self, report: VulnerabilityReport) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sensitive_vulnerability_reports
                (vulnerability_id, source_run_id, case_id, status, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    report.vulnerability_id,
                    report.source_run_id,
                    report.case_id,
                    report.status,
                    report.model_dump_json(),
                ),
            )

    def save_site_scan_finding(self, finding: SiteScanFinding) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sensitive_site_scan_findings
                (finding_id, scan_id, check_id, severity, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    finding.finding_id,
                    finding.scan_id,
                    finding.check_id,
                    finding.severity,
                    finding.model_dump_json(),
                ),
            )

    def save_observation(
        self,
        run_id: str,
        case_id: str,
        observed: ObservedResponse,
    ) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sensitive_observed_responses
                (run_id, case_id, status_code, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    case_id,
                    observed.status_code,
                    observed.model_dump_json(),
                ),
            )

    def reports(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM sensitive_vulnerability_reports"
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def site_scan_findings(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM sensitive_site_scan_findings"
            ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def observations(self, run_id: str | None = None) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            if run_id:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM sensitive_observed_responses
                    WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload_json FROM sensitive_observed_responses"
                ).fetchall()
        return [_from_json(row["payload_json"]) for row in rows]

    def update_report_status(
        self,
        vulnerability_id: str,
        status: ReportStatus,
        status_note: str = "",
    ) -> None:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM sensitive_vulnerability_reports
                WHERE vulnerability_id = ?
                """,
                (vulnerability_id,),
            ).fetchone()
            if row is None:
                return
            report = VulnerabilityReport.model_validate(_from_json(row["payload_json"]))
            updated = report.model_copy(
                update={
                    "status": status,
                    "status_note": status_note,
                }
            )
            conn.execute(
                """
                UPDATE sensitive_vulnerability_reports
                SET status = ?, payload_json = ?
                WHERE vulnerability_id = ?
                """,
                (updated.status, updated.model_dump_json(), vulnerability_id),
            )

    def update_site_scan_finding_status(
        self,
        finding_id: str,
        status: FindingStatus,
        status_note: str = "",
        retest_scan_id: str | None = None,
    ) -> None:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM sensitive_site_scan_findings
                WHERE finding_id = ?
                """,
                (finding_id,),
            ).fetchone()
            if row is None:
                return
            finding = SiteScanFinding.model_validate(_from_json(row["payload_json"]))
            retest_scan_ids = list(finding.retest_scan_ids)
            if retest_scan_id and retest_scan_id not in retest_scan_ids:
                retest_scan_ids.append(retest_scan_id)
            updated = finding.model_copy(
                update={
                    "status": status,
                    "status_note": status_note,
                    "retest_scan_ids": retest_scan_ids,
                }
            )
            conn.execute(
                """
                UPDATE sensitive_site_scan_findings
                SET payload_json = ?
                WHERE finding_id = ?
                """,
                (updated.model_dump_json(), finding_id),
            )


def public_report_view(report: VulnerabilityReport) -> VulnerabilityReport:
    """Return a dashboard/export-safe copy of a sensitive report."""

    return report.model_copy(
        update={
            "clinical_or_privacy_impact": (
                f"{report.severity} / {report.impact_domain} draft finding. "
                "Sensitive details are stored in the private findings vault."
            ),
            "minimal_reproduction": ["Redacted from public operator storage."],
            "observed_behavior": "Redacted from public operator storage.",
            "expected_behavior": "Stored in private findings vault.",
            "recommended_remediation": "Stored in private findings vault.",
            "evidence": [],
            "sensitive_details_redacted": True,
            "private_storage_ref": f"private://vulnerability_reports/{report.vulnerability_id}",
        }
    )


def public_site_scan_finding_view(finding: SiteScanFinding) -> SiteScanFinding:
    """Return a dashboard-safe copy of a passive scan finding."""

    return finding.model_copy(
        update={
            "description": (
                f"{finding.severity} passive scan finding. "
                "Sensitive details are stored in the private findings vault."
            ),
            "evidence": "Redacted from public operator storage.",
            "remediation": "Stored in private findings vault.",
            "sensitive_details_redacted": True,
            "private_storage_ref": f"private://site_scan_findings/{finding.finding_id}",
        }
    )


def public_observation_view(observed: ObservedResponse) -> ObservedResponse:
    """Return a dashboard/export-safe copy of raw target output."""

    return observed.model_copy(
        update={
            "text": "Redacted from public operator storage.",
            "citations": [],
            "tool_outcome": (
                "Redacted from public operator storage."
                if observed.tool_outcome is not None
                else None
            ),
            "black_box_metadata": {
                "sensitive_details_redacted": True,
                "private_storage_ref": "private://observed_responses/by-run",
            },
        }
    )


def _from_json(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("stored payload JSON must be an object")
    return cast(dict[str, Any], payload)
