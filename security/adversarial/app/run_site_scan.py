"""CLI for authorized passive scans of allowlisted web targets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import Settings
from .models import SiteScanMode
from .run_store import RunStore
from .scope_registry import resolve_scope_for_scan
from .site_scanner import PassiveSiteScanner


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
    store.initialize()
    scope = resolve_scope_for_scan(
        store=store,
        settings=settings,
        scope_id=scope_id,
        target_url=target_url,
        mode=mode,
    )
    scan, findings = PassiveSiteScanner(settings).scan(
        target_url=target_url,
        authorization_note=authorization_note,
        mode=mode,
        scope=scope,
    )
    store.save_site_scan_run(scan)
    store.save_site_scan_findings(findings)
    return {
        "scan": scan.model_dump(mode="json"),
        "findings": store.site_scan_findings(scan.scan_id),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an authorized passive scan against an allowlisted target URL."
    )
    parser.add_argument("--target-url", required=True)
    parser.add_argument(
        "--mode",
        choices=[SiteScanMode.PASSIVE_HTTP, SiteScanMode.LOW_PRIV_AUTHENTICATED],
        default=SiteScanMode.PASSIVE_HTTP,
        help="Use low-priv-authenticated only with owned test-user credentials in env.",
    )
    parser.add_argument(
        "--authorization-note",
        default="Operator attests this target is owned or explicitly authorized.",
    )
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--scope-id", default=None)
    args = parser.parse_args()

    settings = Settings()
    if args.db is not None:
        settings.sqlite_path = args.db
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
