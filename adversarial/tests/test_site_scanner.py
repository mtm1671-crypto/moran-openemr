from pathlib import Path

import httpx
import pytest
from pytest import MonkeyPatch

from app.config import Settings
from app.models import Severity, SiteScanFinding, SiteScanRun
from app.run_site_scan import run_passive_site_scan
from app.run_store import RunStore
from app.site_scanner import PassiveSiteScanner


def test_passive_site_scanner_requires_allowlisted_target() -> None:
    settings = Settings(allowed_hosts=["owned.example"])
    scanner = PassiveSiteScanner(settings, client=httpx.Client())
    with pytest.raises(ValueError, match="not allowlisted"):
        scanner.scan("https://evil.example")


def test_passive_site_scanner_flags_missing_headers_and_cookie_attributes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={
                "content-type": "text/html",
                "set-cookie": "session=abc123; Path=/",
            },
            text="<html><title>Owned</title></html>",
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    settings = Settings(allowed_hosts=["owned.example"])
    scan, findings = PassiveSiteScanner(settings, client=client).scan("https://owned.example")

    check_ids = {finding.check_id for finding in findings}
    assert scan.finding_count == len(findings)
    assert scan.highest_severity == "Medium"
    assert "header.hsts.missing" in check_ids
    assert "header.csp.missing" in check_ids
    assert "cookie.1.secure_missing" in check_ids
    assert "cookie.1.httponly_missing" in check_ids
    assert "cookie.1.samesite_missing" in check_ids


def test_run_site_scan_persists_scan_and_findings(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeScanner:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

        def scan(
            self,
            target_url: str,
            authorization_note: str,
        ) -> tuple[SiteScanRun, list[SiteScanFinding]]:
            scan = SiteScanRun(target_url=target_url, authorization_note=authorization_note)
            finding = SiteScanFinding(
                scan_id=scan.scan_id,
                check_id="header.csp.missing",
                title="Missing CSP",
                severity=Severity.MEDIUM,
                description="No CSP.",
                evidence="missing",
                remediation="Add CSP.",
            )
            scan.finding_count = 1
            scan.highest_severity = Severity.MEDIUM
            return scan, [finding]

    monkeypatch.setattr("app.run_site_scan.PassiveSiteScanner", FakeScanner)
    settings = Settings(
        allowed_hosts=["owned.example"],
        sqlite_path=tmp_path / "runs.sqlite",
    )
    result = run_passive_site_scan(
        settings=settings,
        target_url="https://owned.example",
        authorization_note="Owned test target.",
    )

    store = RunStore(settings.sqlite_path)
    assert store.site_scan_runs()[0]["scan_id"] == result["scan"]["scan_id"]
    assert store.site_scan_findings(result["scan"]["scan_id"])
