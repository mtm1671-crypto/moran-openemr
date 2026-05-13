from pathlib import Path

import httpx
import pytest
from pytest import MonkeyPatch

from app.config import Settings
from app.models import AuthorizedScope, Severity, SiteScanFinding, SiteScanMode, SiteScanRun
from app.run_site_scan import run_passive_site_scan
from app.run_store import RunStore
from app.sensitive_findings import SensitiveFindingStore
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


def test_low_priv_site_scanner_requires_configured_test_credential() -> None:
    settings = Settings(allowed_hosts=["owned.example"])
    scanner = PassiveSiteScanner(settings, client=httpx.Client())

    with pytest.raises(ValueError, match="low-priv authenticated scans require"):
        scanner.scan("https://owned.example", mode=SiteScanMode.LOW_PRIV_AUTHENTICATED)


def test_low_priv_site_scanner_checks_exposure_paths_without_leaking_secret_values() -> None:
    seen_auth_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth_headers.append(request.headers.get("authorization"))
        if request.url.path == "/":
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/html"},
                text='<html><script src="/assets/app.js"></script></html>',
            )
        if request.url.path == "/.env":
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/plain"},
                text="API_KEY=super-secret-value",
            )
        if request.url.path == "/admin":
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/html"},
                text="<html>Admin console</html>",
            )
        if request.url.path == "/assets/app.js":
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "application/javascript"},
                text="console.log('ok');",
            )
        if request.url.path == "/assets/app.js.map":
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "application/json"},
                text='{"version":3,"sources":["src/app.ts"]}',
            )
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    settings = Settings(
        allowed_hosts=["owned.example"],
        site_scan_bearer_token="low-priv-token",
        site_scan_extra_paths=["/.env", "/admin"],
        site_scan_max_urls=8,
    )
    scan, findings = PassiveSiteScanner(settings, client=client).scan(
        "https://owned.example",
        mode=SiteScanMode.LOW_PRIV_AUTHENTICATED,
    )

    check_ids = {finding.check_id for finding in findings}
    assert scan.scan_mode == SiteScanMode.LOW_PRIV_AUTHENTICATED
    assert scan.request_count >= 4
    assert all(header == "Bearer low-priv-token" for header in seen_auth_headers)
    assert "exposure.env_file" in check_ids
    assert "authz.low_priv_route_access" in check_ids
    assert "exposure.source_map" in check_ids
    assert "super-secret-value" not in str(findings)


def test_low_priv_site_scanner_honors_scope_limits_and_excluded_paths() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "text/html"},
            text='<html><script src="/assets/app.js"></script></html>',
        )

    settings = Settings(
        allowed_hosts=["owned.example"],
        site_scan_bearer_token="low-priv-token",
        site_scan_extra_paths=["/robots.txt", "/admin"],
    )
    scope = AuthorizedScope(
        scope_id="scope_limited",
        client_id="client_limited",
        project_id="project_limited",
        name="Limited scope",
        allowed_hosts=["owned.example"],
        allowed_scan_modes=[SiteScanMode.LOW_PRIV_AUTHENTICATED],
        excluded_paths=["/admin"],
        max_urls=2,
        authorization_note="Owned target.",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    scan, _findings = PassiveSiteScanner(settings, client=client).scan(
        "https://owned.example",
        mode=SiteScanMode.LOW_PRIV_AUTHENTICATED,
        scope=scope,
    )

    assert scan.scope_id == "scope_limited"
    assert scan.request_count == 2
    assert "/admin" not in requested_paths


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
            mode: SiteScanMode = SiteScanMode.PASSIVE_HTTP,
            scope: AuthorizedScope | None = None,
        ) -> tuple[SiteScanRun, list[SiteScanFinding]]:
            scan = SiteScanRun(
                target_url=target_url,
                authorization_note=authorization_note,
                scan_mode=mode,
                client_id=scope.client_id if scope else None,
                project_id=scope.project_id if scope else None,
                scope_id=scope.scope_id if scope else None,
            )
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
        private_sqlite_path=tmp_path / "private.sqlite",
    )
    result = run_passive_site_scan(
        settings=settings,
        target_url="https://owned.example",
        authorization_note="Owned test target.",
        mode=SiteScanMode.PASSIVE_HTTP,
    )

    store = RunStore(settings.sqlite_path)
    assert store.site_scan_runs()[0]["scan_id"] == result["scan"]["scan_id"]
    assert store.site_scan_runs()[0]["scope_id"] == "scope_agentforge_demo"
    public_finding = store.site_scan_findings(result["scan"]["scan_id"])[0]
    assert public_finding["evidence"] == "Redacted from public operator storage."
    private_finding = SensitiveFindingStore(settings.private_sqlite_path).site_scan_findings()[0]
    assert private_finding["evidence"] == "missing"
