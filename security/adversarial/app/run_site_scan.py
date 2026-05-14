"""CLI for authorized passive scans of allowlisted web targets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import Settings
from .models import SiteScanMode
from .run_store import RunStore
from .site_scanner import PassiveSiteScanner
from .site_scan_workflow import SiteScanWorkflow


def run_passive_site_scan(
    settings: Settings,
    target_url: str,
    authorization_note: str,
    mode: SiteScanMode = SiteScanMode.PASSIVE_HTTP,
    scope_id: str | None = None,
) -> dict[str, Any]:
    store = RunStore(
        settings.sqlite_path,
        private_path=settings.private_sqlite_path,
        evidence_retention_days=settings.evidence_retention_days,
    )
    result = SiteScanWorkflow(
        settings=settings,
        store=store,
        scanner_factory=PassiveSiteScanner,
    ).run(
        target_url=target_url,
        authorization_note=authorization_note,
        mode=mode,
        scope_id=scope_id,
    )
    return {
        "scan": result.scan.model_dump(mode="json"),
        "findings": store.site_scan_findings(result.scan.scan_id),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an authorized passive scan against an allowlisted target URL."
    )
    parser.add_argument("--target-url", required=True)
    parser.add_argument(
        "--mode",
        choices=[
            SiteScanMode.PASSIVE_HTTP,
            SiteScanMode.B2B_BASELINE,
            SiteScanMode.LOW_PRIV_AUTHENTICATED,
        ],
        default=SiteScanMode.PASSIVE_HTTP,
        help="Use low-priv-authenticated only with owned test-user credentials in env.",
    )
    parser.add_argument(
        "--authorization-note",
        default="Operator attests this target is owned or explicitly authorized.",
    )
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--scope-id", default=None)
    parser.add_argument(
        "--expected-denied-path",
        action="append",
        default=[],
        help=(
            "Same-origin path that should be denied to the configured low-privileged principal. "
            "May be supplied multiple times."
        ),
    )
    args = parser.parse_args()

    settings = Settings()
    if args.db is not None:
        settings.sqlite_path = args.db
    if args.expected_denied_path:
        settings.site_scan_expected_denied_paths = args.expected_denied_path
    result = run_passive_site_scan(
        settings=settings,
        target_url=args.target_url,
        authorization_note=args.authorization_note,
        mode=SiteScanMode(args.mode),
        scope_id=args.scope_id,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
