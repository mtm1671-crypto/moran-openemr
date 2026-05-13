"""Authorized bounded web-surface scanner for non-Co-Pilot targets."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse

import httpx

from .config import Settings
from .models import (
    AuthorizedScope,
    Severity,
    SiteScanFinding,
    SiteScanMode,
    SiteScanRun,
    SiteScanStatus,
)


SEVERITY_RANK = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}

LOW_PRIV_DEFAULT_PATHS = (
    "/admin",
    "/admin/",
    "/dashboard",
    "/debug",
    "/debug/vars",
    "/actuator/health",
    "/actuator/env",
    "/server-status",
    "/phpinfo.php",
    "/openapi.json",
    "/swagger.json",
    "/api-docs",
    "/.env",
    "/.git/HEAD",
    "/.git/config",
    "/backup.zip",
    "/db.sql",
    "/dump.sql",
)

SECRET_KEY_RE = re.compile(
    r"(?im)^\s*([A-Z0-9_-]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|"
    r"CLIENT[_-]?SECRET|DATABASE[_-]?URL)[A-Z0-9_-]*)\s*[:=]"
)


class _URLCollector(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"a", "script", "link"}:
            return
        attr_names = {"a": "href", "script": "src", "link": "href"}
        target_attr = attr_names[tag]
        for name, value in attrs:
            if name.lower() == target_attr and value:
                self.urls.append(urljoin(self.base_url, value))


class PassiveSiteScanner:
    """Run bounded checks against an explicitly allowlisted URL."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client

    def scan(
        self,
        target_url: str,
        authorization_note: str = "Operator attests this target is owned or explicitly authorized.",
        mode: SiteScanMode = SiteScanMode.PASSIVE_HTTP,
        scope: AuthorizedScope | None = None,
    ) -> tuple[SiteScanRun, list[SiteScanFinding]]:
        self.settings.validate_target_allowed(target_url)
        if scope is not None:
            scope.assert_allows(target_url, mode)
        authenticated = mode == SiteScanMode.LOW_PRIV_AUTHENTICATED
        if authenticated and not self.settings.has_site_scan_low_priv_auth:
            raise ValueError(
                "low-priv authenticated scans require ADVERSARIAL_SITE_SCAN_BEARER_TOKEN "
                "or ADVERSARIAL_SITE_SCAN_COOKIE"
            )

        started_at = datetime.now(UTC)
        scan = SiteScanRun(
            target_url=target_url,
            client_id=scope.client_id if scope else None,
            project_id=scope.project_id if scope else None,
            scope_id=scope.scope_id if scope else None,
            scan_mode=mode,
            started_at=started_at,
            authorization_note=authorization_note,
        )
        findings: list[SiteScanFinding] = []
        responses: list[httpx.Response] = []

        try:
            response = self._get(target_url, authenticated=authenticated)
            responses.append(response)
        except httpx.HTTPError as exc:
            scan.status = SiteScanStatus.FAILED
            scan.completed_at = datetime.now(UTC)
            findings.append(
                self._finding(
                    scan.scan_id,
                    "target.unreachable",
                    "Target could not be reached",
                    Severity.HIGH,
                    "The scanner could not complete a bounded passive request to the target.",
                    type(exc).__name__,
                    "Verify the target URL, network access, TLS configuration, and allowlist entry.",
                )
            )
            scan.request_count = 1
            scan.finding_count = len(findings)
            scan.highest_severity = _highest_severity(findings)
            return scan, findings

        parsed = urlparse(str(response.url))
        headers = response.headers
        scan.completed_at = datetime.now(UTC)
        scan.target_metadata = {
            "final_url": str(response.url),
            "status_code": response.status_code,
            "content_type": headers.get("content-type"),
            "redirected": str(response.url) != target_url,
            "scan_mode": mode,
            "low_priv_auth_configured": authenticated,
            "scope_id": scope.scope_id if scope else None,
        }

        findings.extend(self._transport_findings(scan.scan_id, parsed, response))
        findings.extend(self._header_findings(scan.scan_id, parsed, response))
        findings.extend(self._cookie_findings(scan.scan_id, response))
        findings.extend(self._content_findings(scan.scan_id, parsed, response, authenticated))

        if authenticated:
            max_urls = scope.max_urls if scope else self.settings.site_scan_max_urls
            for candidate_url in self._candidate_urls(target_url, response, scope):
                if len(responses) >= max_urls:
                    break
                try:
                    self.settings.validate_target_allowed(candidate_url)
                    if scope is not None:
                        scope.assert_allows(candidate_url, mode)
                    candidate = self._get(candidate_url, authenticated=True)
                except (ValueError, httpx.HTTPError):
                    continue
                if not _same_origin(target_url, str(candidate.url)):
                    continue
                responses.append(candidate)
                candidate_parsed = urlparse(str(candidate.url))
                findings.extend(
                    self._content_findings(
                        scan.scan_id,
                        candidate_parsed,
                        candidate,
                        authenticated,
                    )
                )

        scan.request_count = len(responses)
        scan.finding_count = len(findings)
        scan.highest_severity = _highest_severity(findings)
        scan.target_metadata["requested_url_count"] = len(responses)
        scan.target_metadata["requested_paths"] = [
            urlparse(str(scanned.url)).path or "/" for scanned in responses
        ]
        return scan, findings

    def _get(self, target_url: str, authenticated: bool = False) -> httpx.Response:
        headers = self._request_headers(authenticated)
        if self.client is not None:
            return self.client.get(target_url, follow_redirects=True, headers=headers)
        with httpx.Client(timeout=12.0) as client:
            return client.get(target_url, follow_redirects=True, headers=headers)

    def _request_headers(self, authenticated: bool) -> dict[str, str]:
        if not authenticated:
            return {}
        headers: dict[str, str] = {}
        if self.settings.site_scan_bearer_token is not None:
            token = self.settings.site_scan_bearer_token.get_secret_value()
            headers["Authorization"] = f"Bearer {token}"
        if self.settings.site_scan_cookie is not None:
            headers["Cookie"] = self.settings.site_scan_cookie.get_secret_value()
        return headers

    def _candidate_urls(
        self,
        target_url: str,
        response: httpx.Response,
        scope: AuthorizedScope | None = None,
    ) -> list[str]:
        base_url = _origin_base(target_url)
        candidates: list[str] = []
        for path in self.settings.site_scan_extra_paths:
            candidates.append(urljoin(base_url, path))

        preview = _response_preview(response)
        if "text/html" in response.headers.get("content-type", "").lower() or "<html" in preview.lower():
            collector = _URLCollector(str(response.url))
            collector.feed(preview)
            for discovered in collector.urls:
                if _same_origin(target_url, discovered):
                    clean = _strip_fragment(discovered)
                    candidates.append(clean)
                    if urlparse(clean).path.endswith(".js"):
                        candidates.append(f"{clean}.map")

        for path in LOW_PRIV_DEFAULT_PATHS:
            candidates.append(urljoin(base_url, path))

        return _unique_urls(
            [
                url
                for url in candidates
                if _same_origin(target_url, url)
                and (scope is None or not _scope_excludes_url(scope, url))
            ]
        )

    def _transport_findings(
        self,
        scan_id: str,
        parsed_url: ParseResult,
        response: httpx.Response,
    ) -> list[SiteScanFinding]:
        findings: list[SiteScanFinding] = []
        if parsed_url.scheme != "https":
            findings.append(
                self._finding(
                    scan_id,
                    "transport.plain_http",
                    "Target is not using HTTPS",
                    Severity.HIGH,
                    "The target resolved to a non-HTTPS URL.",
                    str(response.url),
                    "Serve the site over HTTPS and redirect HTTP traffic to HTTPS.",
                    "https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html",
                )
            )
        if response.status_code >= 500:
            findings.append(
                self._finding(
                    scan_id,
                    "http.server_error",
                    "Target returned a server error",
                    Severity.MEDIUM,
                    "The passive request received a 5xx response.",
                    f"HTTP {response.status_code}",
                    "Review server logs and add monitoring for repeated scanner-visible 5xx responses.",
                )
            )
        elif response.status_code >= 400:
            findings.append(
                self._finding(
                    scan_id,
                    "http.client_error",
                    "Target returned a client error",
                    Severity.LOW,
                    "The passive request did not reach a normal page response.",
                    f"HTTP {response.status_code}",
                    "Confirm the target URL is the intended entry point for scanning.",
                )
            )
        return findings

    def _header_findings(
        self,
        scan_id: str,
        parsed_url: ParseResult,
        response: httpx.Response,
    ) -> list[SiteScanFinding]:
        findings: list[SiteScanFinding] = []
        headers = response.headers
        csp = headers.get("content-security-policy", "")
        if parsed_url.scheme == "https" and not headers.get("strict-transport-security"):
            findings.append(
                self._finding(
                    scan_id,
                    "header.hsts.missing",
                    "Strict-Transport-Security header is missing",
                    Severity.MEDIUM,
                    "HTTPS responses should ask browsers to require HTTPS for future visits.",
                    "Missing Strict-Transport-Security",
                    "Add an HSTS header after confirming all subdomains are HTTPS-ready.",
                    "https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html",
                )
            )
        if not csp:
            findings.append(
                self._finding(
                    scan_id,
                    "header.csp.missing",
                    "Content-Security-Policy header is missing",
                    Severity.MEDIUM,
                    "No CSP header was observed on the entry response.",
                    "Missing Content-Security-Policy",
                    "Add a least-privilege CSP and monitor violations before tightening enforcement.",
                    "https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html",
                )
            )
        if not headers.get("x-content-type-options"):
            findings.append(
                self._finding(
                    scan_id,
                    "header.x_content_type_options.missing",
                    "X-Content-Type-Options header is missing",
                    Severity.LOW,
                    "Browsers may MIME-sniff responses without this header.",
                    "Missing X-Content-Type-Options",
                    "Set X-Content-Type-Options: nosniff.",
                    "https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html",
                )
            )
        if not headers.get("referrer-policy"):
            findings.append(
                self._finding(
                    scan_id,
                    "header.referrer_policy.missing",
                    "Referrer-Policy header is missing",
                    Severity.LOW,
                    "Navigation may leak more referrer data than intended.",
                    "Missing Referrer-Policy",
                    "Set a restrictive Referrer-Policy such as strict-origin-when-cross-origin.",
                )
            )
        if not headers.get("x-frame-options") and "frame-ancestors" not in csp.lower():
            findings.append(
                self._finding(
                    scan_id,
                    "header.frame_protection.missing",
                    "Clickjacking protection is missing",
                    Severity.MEDIUM,
                    "No X-Frame-Options or CSP frame-ancestors directive was observed.",
                    "Missing frame protection",
                    "Add CSP frame-ancestors or X-Frame-Options where compatible.",
                )
            )
        if headers.get("access-control-allow-origin") == "*":
            findings.append(
                self._finding(
                    scan_id,
                    "header.cors_wildcard",
                    "CORS allows any origin",
                    Severity.MEDIUM,
                    "The response includes Access-Control-Allow-Origin: *.",
                    "Access-Control-Allow-Origin: *",
                    "Restrict CORS origins to trusted frontends unless the resource is intentionally public.",
                )
            )
        server = headers.get("server")
        if server:
            findings.append(
                self._finding(
                    scan_id,
                    "header.server_disclosure",
                    "Server header discloses implementation detail",
                    Severity.INFO,
                    "The entry response exposes a Server header.",
                    f"Server: {server}",
                    "Reduce version/detail disclosure where your platform supports it.",
                )
            )
        return findings

    def _cookie_findings(self, scan_id: str, response: httpx.Response) -> list[SiteScanFinding]:
        findings: list[SiteScanFinding] = []
        for index, cookie in enumerate(response.headers.get_list("set-cookie"), start=1):
            lowered = cookie.lower()
            evidence = cookie.split(";", 1)[0]
            if "secure" not in lowered:
                findings.append(
                    self._finding(
                        scan_id,
                        f"cookie.{index}.secure_missing",
                        "Cookie is missing Secure",
                        Severity.MEDIUM,
                        "A cookie was set without the Secure attribute.",
                        evidence,
                        "Add Secure to cookies that should only be sent over HTTPS.",
                    )
                )
            if "httponly" not in lowered:
                findings.append(
                    self._finding(
                        scan_id,
                        f"cookie.{index}.httponly_missing",
                        "Cookie is missing HttpOnly",
                        Severity.MEDIUM,
                        "A cookie was set without the HttpOnly attribute.",
                        evidence,
                        "Add HttpOnly to cookies that do not need JavaScript access.",
                    )
                )
            if "samesite=" not in lowered:
                findings.append(
                    self._finding(
                        scan_id,
                        f"cookie.{index}.samesite_missing",
                        "Cookie is missing SameSite",
                        Severity.LOW,
                        "A cookie was set without an explicit SameSite attribute.",
                        evidence,
                        "Set SameSite=Lax or SameSite=Strict where compatible.",
                    )
                )
        return findings

    def _content_findings(
        self,
        scan_id: str,
        parsed_url: ParseResult,
        response: httpx.Response,
        authenticated: bool,
    ) -> list[SiteScanFinding]:
        if response.status_code >= 400:
            return []
        path = parsed_url.path or "/"
        preview = _response_preview(response)
        lowered = preview.lower()
        findings: list[SiteScanFinding] = []

        if path in {"/.env", "/.env.local", "/.env.production"}:
            keys = _secret_key_names(preview)
            evidence = f"{path} returned HTTP {response.status_code}"
            if keys:
                evidence += f"; secret-like keys observed: {', '.join(keys[:5])}"
            findings.append(
                self._finding(
                    scan_id,
                    "exposure.env_file",
                    "Environment file appears exposed",
                    Severity.HIGH,
                    "A route commonly used for environment variables returned a non-deny response.",
                    evidence,
                    "Block dotfile access at the web server and rotate any exposed credentials.",
                )
            )

        if path.startswith("/.git/"):
            findings.append(
                self._finding(
                    scan_id,
                    "exposure.git_metadata",
                    "Git metadata appears exposed",
                    Severity.HIGH,
                    "A route under /.git returned a non-deny response.",
                    f"{path} returned HTTP {response.status_code}",
                    "Block VCS metadata from public web roots and rotate secrets if history was exposed.",
                )
            )

        if path.endswith(".map"):
            findings.append(
                self._finding(
                    scan_id,
                    "exposure.source_map",
                    "Frontend source map is accessible",
                    Severity.LOW,
                    "A JavaScript source map returned a non-deny response.",
                    f"{path} returned HTTP {response.status_code}",
                    "Disable production source maps or ensure they do not contain sensitive source details.",
                )
            )

        if path in {"/openapi.json", "/swagger.json", "/api-docs"}:
            findings.append(
                self._finding(
                    scan_id,
                    "exposure.api_schema",
                    "API schema is accessible",
                    Severity.LOW,
                    "API documentation or schema returned a non-deny response.",
                    f"{path} returned HTTP {response.status_code}",
                    "Confirm the schema is intended for this audience and hides internal-only operations.",
                )
            )

        if path in {"/backup.zip", "/db.sql", "/dump.sql"}:
            findings.append(
                self._finding(
                    scan_id,
                    "exposure.backup_artifact",
                    "Backup or database artifact may be exposed",
                    Severity.HIGH,
                    "A route commonly used for backups or database dumps returned a non-deny response.",
                    f"{path} returned HTTP {response.status_code}",
                    "Remove backup artifacts from the web root and rotate secrets if contents were exposed.",
                )
            )

        if path in {"/debug", "/debug/vars", "/actuator/env", "/server-status", "/phpinfo.php"}:
            severity = Severity.HIGH if "phpinfo" in lowered or "environment" in lowered else Severity.MEDIUM
            findings.append(
                self._finding(
                    scan_id,
                    "exposure.debug_endpoint",
                    "Debug or runtime endpoint is accessible",
                    severity,
                    "A route commonly associated with runtime diagnostics returned a non-deny response.",
                    f"{path} returned HTTP {response.status_code}",
                    "Remove the endpoint from production or restrict it to trusted operators.",
                )
            )

        if authenticated and path in {"/admin", "/admin/", "/dashboard"} and not _looks_like_login(preview):
            findings.append(
                self._finding(
                    scan_id,
                    "authz.low_priv_route_access",
                    "Privileged route responded to low-privileged user",
                    Severity.MEDIUM,
                    "A route commonly associated with privileged access returned a non-deny response.",
                    f"{path} returned HTTP {response.status_code} in low-privileged mode",
                    "Verify object and function-level authorization for this route.",
                )
            )

        keys = _secret_key_names(preview)
        if keys and path not in {"/.env", "/.env.local", "/.env.production"}:
            findings.append(
                self._finding(
                    scan_id,
                    "exposure.secret_like_content",
                    "Secret-like content appears in response",
                    Severity.HIGH,
                    "The response body contained variable names commonly associated with secrets.",
                    f"{path} returned secret-like keys: {', '.join(keys[:5])}",
                    "Remove secrets from rendered responses and rotate any affected credentials.",
                )
            )

        return findings

    def _finding(
        self,
        scan_id: str,
        check_id: str,
        title: str,
        severity: Severity,
        description: str,
        evidence: str,
        remediation: str,
        reference_url: str | None = None,
    ) -> SiteScanFinding:
        return SiteScanFinding(
            scan_id=scan_id,
            check_id=check_id,
            title=title,
            severity=severity,
            description=description,
            evidence=evidence,
            remediation=remediation,
            reference_url=reference_url,
        )


def _response_preview(response: httpx.Response) -> str:
    try:
        return response.text[:4096]
    except UnicodeDecodeError:
        return ""


def _secret_key_names(text: str) -> list[str]:
    names = [match.group(1) for match in SECRET_KEY_RE.finditer(text)]
    return sorted(set(names))


def _looks_like_login(text: str) -> bool:
    lowered = text.lower()
    return "password" in lowered and any(marker in lowered for marker in ["login", "sign in", "signin"])


def _origin_base(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def _same_origin(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)
    return (
        candidate.scheme in {"http", "https"}
        and base.scheme == candidate.scheme
        and base.hostname == candidate.hostname
        and (base.port or _default_port(base.scheme)) == (candidate.port or _default_port(candidate.scheme))
    )


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))


def _unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _scope_excludes_url(scope: AuthorizedScope, url: str) -> bool:
    path = urlparse(url).path or "/"
    return any(
        path == excluded or path.startswith(f"{excluded.rstrip('/')}/")
        for excluded in scope.excluded_paths
    )


def _highest_severity(findings: list[SiteScanFinding]) -> Severity:
    if not findings:
        return Severity.INFO
    return max((finding.severity for finding in findings), key=lambda severity: SEVERITY_RANK[severity])
