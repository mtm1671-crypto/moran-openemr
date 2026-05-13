"""Authorized passive web-surface scanner for non-Co-Pilot targets."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import ParseResult, urlparse

import httpx

from .config import Settings
from .models import Severity, SiteScanFinding, SiteScanRun, SiteScanStatus


SEVERITY_RANK = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}


class PassiveSiteScanner:
    """Run bounded passive checks against an explicitly allowlisted URL."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client

    def scan(
        self,
        target_url: str,
        authorization_note: str = "Operator attests this target is owned or explicitly authorized.",
    ) -> tuple[SiteScanRun, list[SiteScanFinding]]:
        self.settings.validate_target_allowed(target_url)
        started_at = datetime.now(UTC)
        scan = SiteScanRun(
            target_url=target_url,
            started_at=started_at,
            authorization_note=authorization_note,
        )
        findings: list[SiteScanFinding] = []
        try:
            response = self._get(target_url)
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
            scan.finding_count = len(findings)
            scan.highest_severity = _highest_severity(findings)
            return scan, findings

        parsed = urlparse(str(response.url))
        headers = response.headers
        scan.completed_at = datetime.now(UTC)
        scan.request_count = 1
        scan.target_metadata = {
            "final_url": str(response.url),
            "status_code": response.status_code,
            "content_type": headers.get("content-type"),
            "redirected": str(response.url) != target_url,
        }

        findings.extend(self._transport_findings(scan.scan_id, parsed, response))
        findings.extend(self._header_findings(scan.scan_id, parsed, response))
        findings.extend(self._cookie_findings(scan.scan_id, response))

        scan.finding_count = len(findings)
        scan.highest_severity = _highest_severity(findings)
        return scan, findings

    def _get(self, target_url: str) -> httpx.Response:
        if self.client is not None:
            return self.client.get(target_url, follow_redirects=True)
        with httpx.Client(timeout=12.0) as client:
            return client.get(target_url, follow_redirects=True)

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


def _highest_severity(findings: list[SiteScanFinding]) -> Severity:
    if not findings:
        return Severity.INFO
    return max((finding.severity for finding in findings), key=lambda severity: SEVERITY_RANK[severity])
