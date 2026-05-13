"""Runtime settings and target allowlist checks."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import RunMode, TargetMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADVERSARIAL_", env_file=".env", extra="ignore")

    target_mode: TargetMode = TargetMode.LOCAL
    run_mode: RunMode = RunMode.REPORT_ONLY
    local_target_url: str = "http://127.0.0.1:8001"
    deployed_target_url: str = "https://copilot-api-production-9f84.up.railway.app"
    allowed_hosts: list[str] = Field(
        default_factory=lambda: [
            "127.0.0.1",
            "localhost",
            "copilot-web-production.up.railway.app",
            "copilot-api-production-9f84.up.railway.app",
            "openemr-production-f5ed.up.railway.app",
        ]
    )
    sqlite_path: Path = Path(".data/week3_runs.sqlite")
    private_sqlite_path: Path = Path(".data/private_findings.sqlite")
    synthetic_clinician_token: str | None = None
    synthetic_clinician_token_url: str | None = None
    synthetic_clinician_client_id: str | None = None
    synthetic_clinician_client_secret: SecretStr | None = None
    synthetic_clinician_username: str | None = None
    synthetic_clinician_password: SecretStr | None = None
    synthetic_clinician_scopes: str = (
        "openid offline_access api:fhir user/Patient.read user/Practitioner.read "
        "user/Observation.read user/Condition.read user/MedicationRequest.read "
        "user/AllergyIntolerance.read user/DocumentReference.read"
    )
    service_account_token: str | None = None
    max_requests_per_case: int = 8
    max_latency_ms_per_case: int = 30_000
    max_token_estimate_per_case: int = 8_000
    max_provider_cost_usd_per_case: float = 0.25
    max_retries_per_case: int = 2
    max_loop_depth: int = 3
    max_variants_per_case: int = 3
    max_wall_clock_seconds: int = 300
    site_scan_bearer_token: SecretStr | None = None
    site_scan_cookie: SecretStr | None = None
    site_scan_max_urls: int = Field(default=12, ge=1, le=50)
    site_scan_extra_paths: list[str] = Field(
        default_factory=lambda: [
            "/.well-known/security.txt",
            "/robots.txt",
            "/sitemap.xml",
        ]
    )

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("site_scan_extra_paths", mode="before")
    @classmethod
    def parse_site_scan_extra_paths(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def target_url(self) -> str:
        if self.target_mode == TargetMode.DEPLOYED:
            return self.deployed_target_url
        return self.local_target_url

    def validate_target_allowed(self, url: str | None = None) -> None:
        target = url or self.target_url
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"target URL must use http or https: {target}")
        host = parsed.hostname
        if not host or host not in set(self.allowed_hosts):
            raise ValueError(f"target host is not allowlisted: {host or target}")

    def validate_ready_for_run(self) -> None:
        self.validate_target_allowed()
        if self.synthetic_clinician_token_url is not None:
            self.validate_target_allowed(self.synthetic_clinician_token_url)
        if self.target_mode == TargetMode.DEPLOYED and not self.has_synthetic_clinician_auth:
            raise ValueError(
                "deployed runs require ADVERSARIAL_SYNTHETIC_CLINICIAN_TOKEN or "
                "synthetic clinician OAuth password-grant settings"
            )

    @property
    def has_synthetic_clinician_auth(self) -> bool:
        if self.synthetic_clinician_token:
            return True
        return all(
            [
                self.synthetic_clinician_token_url,
                self.synthetic_clinician_client_id,
                self.synthetic_clinician_username,
                self.synthetic_clinician_password,
            ]
        )

    @property
    def has_site_scan_low_priv_auth(self) -> bool:
        return self.site_scan_bearer_token is not None or self.site_scan_cookie is not None


def load_settings() -> Settings:
    settings = Settings()
    settings.validate_ready_for_run()
    return settings
