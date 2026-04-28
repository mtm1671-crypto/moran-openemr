from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    public_base_url: str = "http://localhost:3000"
    database_url: SecretStr | None = None
    encryption_key: SecretStr | None = None

    openemr_base_url: AnyHttpUrl | None = None
    openemr_site: str = "default"
    openemr_fhir_base_url: AnyHttpUrl | None = None
    openemr_oauth_token_url: AnyHttpUrl | None = None
    openemr_jwks_url: AnyHttpUrl | None = None
    openemr_client_id: str | None = None
    openemr_client_secret: SecretStr | None = None
    openemr_tls_verify: bool = True
    openemr_dev_password_grant: bool = False
    openemr_dev_username: str | None = None
    openemr_dev_password: SecretStr | None = None
    openemr_dev_scopes: str = (
        "openid offline_access api:oemr api:fhir "
        "user/Patient.read user/Practitioner.read user/Observation.read user/Condition.read"
    )

    llm_provider: str = "mock"
    allow_phi_to_anthropic: bool = False
    allow_phi_to_openrouter: bool = False
    allow_phi_to_local: bool = True

    conversation_retention_days: int = 30
    reindex_idempotency_seconds: int = 120
    dev_auth_bypass: bool = Field(default=True, description="Only for local scaffold work.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
