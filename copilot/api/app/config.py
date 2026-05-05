import base64
import binascii
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models import Role

_PRODUCTION_ENV_NAMES = {"production", "prod"}
_PHI_ENV_NAMES = {"production", "prod", "phi", "secure"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def __init__(self, **values: Any) -> None:
        super().__init__(**values)

    app_env: str = "local"
    phi_mode: bool = False
    public_base_url: str = "http://localhost:3000"
    database_url: SecretStr | None = None
    encryption_key: SecretStr | None = None
    encryption_key_id: str = "primary"

    openemr_base_url: AnyHttpUrl | None = None
    openemr_site: str = "default"
    openemr_fhir_base_url: AnyHttpUrl | None = None
    openemr_oauth_token_url: AnyHttpUrl | None = None
    openemr_jwks_url: AnyHttpUrl | None = None
    openemr_jwt_issuer: str | None = None
    openemr_jwt_audience: str | None = None
    openemr_role_claim: str = "role"
    openemr_default_role: Role | None = None
    openemr_client_id: str | None = None
    openemr_client_secret: SecretStr | None = None
    openemr_tls_verify: bool = True
    openemr_dev_password_grant: bool = False
    openemr_dev_username: str | None = None
    openemr_dev_password: SecretStr | None = None
    openemr_api_log_option: int | None = None
    openemr_request_timeout_seconds: float = 15.0
    openemr_retry_attempts: int = 3
    openemr_retry_backoff_seconds: float = 0.25
    openemr_dev_scopes: str = (
        "openid offline_access api:oemr api:fhir "
        "user/Patient.read user/Practitioner.read user/Observation.read user/Condition.read "
        "user/MedicationRequest.read user/AllergyIntolerance.read user/DocumentReference.read"
    )

    llm_provider: str = "mock"
    embedding_provider: str = "none"
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_llm_model: str = "gpt-5.5"
    openai_embedding_model: str = "text-embedding-3-large"
    openai_timeout_seconds: float = 45.0
    model_retry_attempts: int = 2
    model_retry_backoff_seconds: float = 0.5
    openai_max_output_tokens: int = 900
    openai_reasoning_effort: str = "low"
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_llm_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    openrouter_timeout_seconds: float = 60.0
    openrouter_max_tokens: int = 900
    openrouter_site_url: str | None = None
    openrouter_app_name: str = "AgentForge Clinical Co-Pilot"
    openrouter_demo_data_only: bool = False
    openrouter_baa_confirmed: bool = False
    openrouter_data_policy_confirmed: bool = False
    model_evidence_limit: int = 12
    ocr_provider: str = "none"
    openai_ocr_model: str = "gpt-4.1-mini"
    openai_ocr_detail: str = "high"
    openai_ocr_max_output_tokens: int = 2500
    openrouter_ocr_model: str = "baidu/qianfan-ocr-fast:free"
    openrouter_ocr_max_tokens: int = 2500
    vector_search_enabled: bool = False
    vector_embedding_provider: str = "hash"
    vector_embedding_dimensions: int = 256
    vector_search_limit: int = 6
    vector_candidate_limit: int = 200
    vector_min_score: float = 0.05
    vector_index_ttl_days: int = 30
    vector_index_backend: str = "json"
    evidence_cache_enabled: bool = False
    evidence_cache_ttl_seconds: int = 300
    agent_loop_max_steps: int = 6
    nightly_maintenance_enabled: bool = False
    nightly_maintenance_hour_utc: int = 8
    nightly_reindex_enabled: bool = False
    nightly_reindex_patient_count: int = 100
    openemr_service_account_enabled: bool = False
    openemr_service_token_url: AnyHttpUrl | None = None
    openemr_service_client_id: str | None = None
    openemr_service_client_secret: SecretStr | None = None
    openemr_service_bearer_token: SecretStr | None = None
    openemr_service_scopes: str = (
        "openid offline_access api:oemr api:fhir "
        "user/Patient.read user/Practitioner.read user/Observation.read user/Condition.read "
        "user/MedicationRequest.read user/AllergyIntolerance.read user/DocumentReference.read"
    )
    structured_logging_enabled: bool = True
    audit_persistence_required: bool = True
    conversation_persistence_enabled: bool = True
    job_status_retention_days: int = 30
    allow_phi_to_openai: bool = False
    openai_baa_confirmed: bool = False
    openai_data_policy_confirmed: bool = False
    allow_phi_to_anthropic: bool = False
    allow_phi_to_openrouter: bool = False
    allow_phi_to_local: bool = True

    conversation_retention_days: int = 30
    reindex_idempotency_seconds: int = 120
    dev_auth_bypass: bool = Field(default=True, description="Only for local scaffold work.")

    def is_production(self) -> bool:
        return self.app_env.lower() in _PRODUCTION_ENV_NAMES

    def requires_phi_controls(self) -> bool:
        return self.phi_mode or self.app_env.lower() in _PHI_ENV_NAMES

    def uses_openai_models(self) -> bool:
        return (
            self.llm_provider == "openai"
            or self.embedding_provider == "openai"
            or self.ocr_provider == "openai"
            or (self.vector_search_enabled and self.vector_embedding_provider == "openai")
        )

    def uses_openrouter_models(self) -> bool:
        return self.llm_provider == "openrouter" or self.ocr_provider == "openrouter"

    def ocr_model_configured(self) -> bool:
        if self.ocr_provider == "none":
            return True
        if self.ocr_provider == "openai":
            return bool(self.openai_ocr_model.strip())
        if self.ocr_provider == "openrouter":
            return bool(self.openrouter_ocr_model.strip())
        return False

    def runtime_config_errors(self) -> list[str]:
        errors: list[str] = []
        if self.llm_provider not in {"mock", "openai", "openrouter"}:
            errors.append("LLM_PROVIDER must be one of: mock, openai, openrouter")
        if self.embedding_provider not in {"none", "openai"}:
            errors.append("EMBEDDING_PROVIDER must be one of: none, openai")
        if self.openai_timeout_seconds <= 0:
            errors.append("OPENAI_TIMEOUT_SECONDS must be greater than 0")
        if self.model_retry_attempts <= 0:
            errors.append("MODEL_RETRY_ATTEMPTS must be greater than 0")
        if self.model_retry_backoff_seconds < 0:
            errors.append("MODEL_RETRY_BACKOFF_SECONDS must be greater than or equal to 0")
        if self.openai_max_output_tokens <= 0:
            errors.append("OPENAI_MAX_OUTPUT_TOKENS must be greater than 0")
        if self.openrouter_timeout_seconds <= 0:
            errors.append("OPENROUTER_TIMEOUT_SECONDS must be greater than 0")
        if self.openrouter_max_tokens <= 0:
            errors.append("OPENROUTER_MAX_TOKENS must be greater than 0")
        if not self.openai_llm_model.strip():
            errors.append("OPENAI_LLM_MODEL must not be blank")
        if not self.openai_embedding_model.strip():
            errors.append("OPENAI_EMBEDDING_MODEL must not be blank")
        if not self.openrouter_llm_model.strip():
            errors.append("OPENROUTER_LLM_MODEL must not be blank")
        if self.ocr_provider not in {"none", "openai", "openrouter"}:
            errors.append("OCR_PROVIDER must be one of: none, openai, openrouter")
        if self.openai_ocr_detail not in {"auto", "high", "low"}:
            errors.append("OPENAI_OCR_DETAIL must be one of: auto, high, low")
        if self.openai_ocr_max_output_tokens <= 0:
            errors.append("OPENAI_OCR_MAX_OUTPUT_TOKENS must be greater than 0")
        if self.openrouter_ocr_max_tokens <= 0:
            errors.append("OPENROUTER_OCR_MAX_TOKENS must be greater than 0")
        if self.ocr_provider == "openai" and not self.openai_ocr_model.strip():
            errors.append("OPENAI_OCR_MODEL must not be blank when OCR_PROVIDER=openai")
        if self.ocr_provider == "openrouter":
            if not self.openrouter_ocr_model.strip():
                errors.append("OPENROUTER_OCR_MODEL must not be blank when OCR_PROVIDER=openrouter")
            if self.openrouter_ocr_model.strip() == "openrouter/free" and self.requires_phi_controls():
                errors.append(
                    "OPENROUTER_OCR_MODEL must name a concrete OCR/vision model for PHI-mode OCR"
                )
        if self.openemr_request_timeout_seconds <= 0:
            errors.append("OPENEMR_REQUEST_TIMEOUT_SECONDS must be greater than 0")
        if self.openemr_retry_attempts <= 0:
            errors.append("OPENEMR_RETRY_ATTEMPTS must be greater than 0")
        if self.openemr_retry_backoff_seconds < 0:
            errors.append("OPENEMR_RETRY_BACKOFF_SECONDS must be greater than or equal to 0")
        if self.model_evidence_limit <= 0:
            errors.append("MODEL_EVIDENCE_LIMIT must be greater than 0")
        if self.openai_reasoning_effort not in {"none", "low", "medium", "high", "xhigh"}:
            errors.append("OPENAI_REASONING_EFFORT must be one of: none, low, medium, high, xhigh")
        if self.vector_embedding_provider not in {"hash", "openai"}:
            errors.append("VECTOR_EMBEDDING_PROVIDER must be one of: hash, openai")
        if self.vector_index_backend not in {"json", "pgvector"}:
            errors.append("VECTOR_INDEX_BACKEND must be one of: json, pgvector")
        if self.vector_embedding_dimensions <= 0:
            errors.append("VECTOR_EMBEDDING_DIMENSIONS must be greater than 0")
        if self.vector_search_limit <= 0:
            errors.append("VECTOR_SEARCH_LIMIT must be greater than 0")
        if self.vector_candidate_limit < self.vector_search_limit:
            errors.append("VECTOR_CANDIDATE_LIMIT must be greater than or equal to VECTOR_SEARCH_LIMIT")
        if self.vector_min_score < -1 or self.vector_min_score > 1:
            errors.append("VECTOR_MIN_SCORE must be between -1 and 1")
        if self.vector_index_ttl_days <= 0:
            errors.append("VECTOR_INDEX_TTL_DAYS must be greater than 0")
        if self.evidence_cache_ttl_seconds <= 0:
            errors.append("EVIDENCE_CACHE_TTL_SECONDS must be greater than 0")
        if self.agent_loop_max_steps <= 0:
            errors.append("AGENT_LOOP_MAX_STEPS must be greater than 0")
        if self.nightly_maintenance_hour_utc < 0 or self.nightly_maintenance_hour_utc > 23:
            errors.append("NIGHTLY_MAINTENANCE_HOUR_UTC must be between 0 and 23")
        if self.nightly_reindex_patient_count <= 0:
            errors.append("NIGHTLY_REINDEX_PATIENT_COUNT must be greater than 0")
        if self.job_status_retention_days <= 0:
            errors.append("JOB_STATUS_RETENTION_DAYS must be greater than 0")
        if self.openemr_service_account_enabled:
            has_static_bearer = self.openemr_service_bearer_token is not None
            has_client_credentials = (
                self.openemr_service_client_id is not None
                and self.openemr_service_client_secret is not None
                and (
                    self.openemr_service_token_url is not None
                    or self.openemr_oauth_token_url is not None
                )
            )
            if not has_static_bearer and not has_client_credentials:
                errors.append(
                    "OpenEMR service account requires OPENEMR_SERVICE_BEARER_TOKEN or "
                    "OPENEMR_SERVICE_CLIENT_ID, OPENEMR_SERVICE_CLIENT_SECRET, and a token URL"
                )
        if self.nightly_reindex_enabled and not self.openemr_service_account_enabled:
            errors.append("OPENEMR_SERVICE_ACCOUNT_ENABLED must be true when nightly reindex is enabled")

        uses_openai = self.uses_openai_models()
        if uses_openai and self.openai_api_key is None:
            errors.append("OPENAI_API_KEY is required when OpenAI models are enabled")
        if uses_openai:
            _require_https("OPENAI_BASE_URL", self.openai_base_url, errors)
        uses_openrouter = self.uses_openrouter_models()
        if uses_openrouter and self.openrouter_api_key is None:
            errors.append("OPENROUTER_API_KEY is required when OpenRouter is enabled")
        if uses_openrouter:
            _require_https("OPENROUTER_BASE_URL", self.openrouter_base_url, errors)
        if self.openemr_service_account_enabled and self.openemr_service_token_url is not None:
            _require_https("OPENEMR_SERVICE_TOKEN_URL", self.openemr_service_token_url, errors)

        if not self.requires_phi_controls():
            if self.vector_search_enabled and self.database_url is None:
                errors.append("DATABASE_URL is required when vector search is enabled")
            if self.vector_search_enabled and self.encryption_key is None:
                errors.append("ENCRYPTION_KEY is required when vector search is enabled")
            if self.evidence_cache_enabled and self.database_url is None:
                errors.append("DATABASE_URL is required when evidence cache is enabled")
            if self.evidence_cache_enabled and self.encryption_key is None:
                errors.append("ENCRYPTION_KEY is required when evidence cache is enabled")
            return errors

        if self.dev_auth_bypass:
            errors.append("DEV_AUTH_BYPASS must be false when PHI controls are required")
        if self.openemr_dev_password_grant:
            errors.append("OPENEMR_DEV_PASSWORD_GRANT must be false when PHI controls are required")
        if not self.openemr_tls_verify:
            errors.append("OPENEMR_TLS_VERIFY must be true when PHI controls are required")
        if self.database_url is None:
            errors.append("DATABASE_URL is required when PHI controls are required")
        if self.encryption_key is None:
            errors.append("ENCRYPTION_KEY is required when PHI controls are required")
        elif not _is_valid_fernet_key(self.encryption_key.get_secret_value()):
            errors.append("ENCRYPTION_KEY must be a valid Fernet key")
        if self.vector_search_enabled and self.database_url is None:
            errors.append("DATABASE_URL is required when vector search is enabled")
        if self.vector_search_enabled and self.encryption_key is None:
            errors.append("ENCRYPTION_KEY is required when vector search is enabled")
        if self.evidence_cache_enabled and self.database_url is None:
            errors.append("DATABASE_URL is required when evidence cache is enabled")
        if self.evidence_cache_enabled and self.encryption_key is None:
            errors.append("ENCRYPTION_KEY is required when evidence cache is enabled")
        if self.openemr_api_log_option != 1:
            errors.append("OPENEMR_API_LOG_OPTION must be 1 when PHI controls are required")
        if uses_openai:
            if not self.allow_phi_to_openai:
                errors.append(
                    "ALLOW_PHI_TO_OPENAI must be true before PHI can be sent to OpenAI"
                )
            if not self.openai_baa_confirmed:
                errors.append("OPENAI_BAA_CONFIRMED must be true before PHI can be sent to OpenAI")
            if not self.openai_data_policy_confirmed:
                errors.append(
                    "OPENAI_DATA_POLICY_CONFIRMED must be true before PHI can be sent to OpenAI"
                )
        elif self.allow_phi_to_openai:
            errors.append("ALLOW_PHI_TO_OPENAI must be false unless OpenAI models are enabled")
        if self.allow_phi_to_anthropic:
            errors.append("ALLOW_PHI_TO_ANTHROPIC must be false until a signed BAA path is approved")
        if uses_openrouter:
            has_phi_openrouter_path = (
                self.allow_phi_to_openrouter
                and self.openrouter_baa_confirmed
                and self.openrouter_data_policy_confirmed
            )
            if not self.openrouter_demo_data_only and not has_phi_openrouter_path:
                errors.append(
                    "OPENROUTER_DEMO_DATA_ONLY must be true for synthetic data, or "
                    "ALLOW_PHI_TO_OPENROUTER, OPENROUTER_BAA_CONFIRMED, and "
                    "OPENROUTER_DATA_POLICY_CONFIRMED must all be true before PHI can be sent "
                    "to OpenRouter"
                )
        elif self.allow_phi_to_openrouter:
            errors.append("ALLOW_PHI_TO_OPENROUTER must be false unless OpenRouter is enabled")
        if self.allow_phi_to_local:
            errors.append("ALLOW_PHI_TO_LOCAL must be false for the initial PHI-ready mock deployment")

        if self.openemr_fhir_base_url is None:
            errors.append("OPENEMR_FHIR_BASE_URL is required when PHI controls are required")
        if self.openemr_jwks_url is None:
            errors.append("OPENEMR_JWKS_URL is required when PHI controls are required")
        if self.openemr_jwt_issuer is None:
            errors.append("OPENEMR_JWT_ISSUER is required when PHI controls are required")
        if self.openemr_jwt_audience is None:
            errors.append("OPENEMR_JWT_AUDIENCE is required when PHI controls are required")

        _require_https("PUBLIC_BASE_URL", self.public_base_url, errors)
        _require_https("OPENEMR_BASE_URL", self.openemr_base_url, errors)
        _require_https("OPENEMR_FHIR_BASE_URL", self.openemr_fhir_base_url, errors)
        _require_https("OPENEMR_OAUTH_TOKEN_URL", self.openemr_oauth_token_url, errors)
        _require_https("OPENEMR_JWKS_URL", self.openemr_jwks_url, errors)
        if self.openemr_service_account_enabled and self.openemr_service_token_url is not None:
            _require_https("OPENEMR_SERVICE_TOKEN_URL", self.openemr_service_token_url, errors)
        return errors

    def assert_runtime_config(self) -> None:
        errors = self.runtime_config_errors()
        if errors:
            raise RuntimeError("Unsafe Clinical Co-Pilot configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _require_https(name: str, value: AnyHttpUrl | str | None, errors: list[str]) -> None:
    if value is None:
        return
    parsed = urlparse(str(value))
    if parsed.scheme != "https":
        errors.append(f"{name} must use https when PHI controls are required")


def _is_valid_fernet_key(value: str) -> bool:
    try:
        return len(base64.urlsafe_b64decode(value.encode("ascii"))) == 32
    except (binascii.Error, UnicodeEncodeError, ValueError):
        return False
