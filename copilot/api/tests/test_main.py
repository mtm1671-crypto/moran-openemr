import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.config import get_settings
from app.main import _local_cors_origin_regex, app

TEST_FERNET_KEY = "PAAhZkguTNgLSk3R268DyJ-Lu6c_M4_87k7s2Prrt_8="


def test_local_cors_origin_regex_allows_localhost_dev_ports_only_in_local_env() -> None:
    assert _local_cors_origin_regex("local") == r"https?://(localhost|127\.0\.0\.1):\d+"
    assert _local_cors_origin_regex("production") is None


def test_production_config_rejects_dev_shortcuts_and_insecure_urls() -> None:
    settings = Settings(
        app_env="production",
        openemr_base_url="http://openemr.test",
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
        openemr_oauth_token_url="http://openemr.test/oauth2/default/token",
        openemr_jwks_url="http://openemr.test/oauth2/default/jwks",
        openemr_jwt_issuer="https://openemr.test",
        openemr_dev_password_grant=True,
        openemr_tls_verify=False,
    )

    errors = settings.runtime_config_errors()

    assert "DEV_AUTH_BYPASS must be false when PHI controls are required" in errors
    assert "OPENEMR_DEV_PASSWORD_GRANT must be false when PHI controls are required" in errors
    assert "OPENEMR_TLS_VERIFY must be true when PHI controls are required" in errors
    assert "DATABASE_URL is required when PHI controls are required" in errors
    assert "ENCRYPTION_KEY is required when PHI controls are required" in errors
    assert "OPENEMR_API_LOG_OPTION must be 1 when PHI controls are required" in errors
    assert "ALLOW_PHI_TO_LOCAL must be false for the initial PHI-ready mock deployment" in errors
    assert "OPENEMR_JWT_AUDIENCE is required when PHI controls are required" in errors
    assert "PUBLIC_BASE_URL must use https when PHI controls are required" in errors
    assert "OPENEMR_FHIR_BASE_URL must use https when PHI controls are required" in errors
    with pytest.raises(RuntimeError):
        settings.assert_runtime_config()


def test_production_config_accepts_smart_jwt_settings() -> None:
    settings = _phi_ready_settings()

    assert settings.runtime_config_errors() == []


def test_production_config_accepts_hash_vector_search_with_phi_storage() -> None:
    settings = _phi_ready_settings(vector_search_enabled=True, vector_embedding_provider="hash")

    assert settings.runtime_config_errors() == []


def test_production_config_accepts_pgvector_backend_with_phi_storage() -> None:
    settings = _phi_ready_settings(
        vector_search_enabled=True,
        vector_embedding_provider="hash",
        vector_index_backend="pgvector",
    )

    assert settings.runtime_config_errors() == []


def test_nightly_reindex_requires_service_account() -> None:
    settings = _phi_ready_settings(nightly_reindex_enabled=True)

    assert "OPENEMR_SERVICE_ACCOUNT_ENABLED must be true when nightly reindex is enabled" in (
        settings.runtime_config_errors()
    )


def test_service_account_requires_backend_credentials() -> None:
    settings = _phi_ready_settings(openemr_service_account_enabled=True)

    assert any(
        error.startswith("OpenEMR service account requires")
        for error in settings.runtime_config_errors()
    )


def test_service_account_accepts_static_backend_token() -> None:
    settings = _phi_ready_settings(
        openemr_service_account_enabled=True,
        openemr_service_bearer_token="service-token",
        nightly_reindex_enabled=True,
    )

    assert settings.runtime_config_errors() == []


def test_vector_search_requires_database_and_encryption_key() -> None:
    settings = Settings(
        app_env="local",
        vector_search_enabled=True,
        database_url=None,
        encryption_key=None,
    )

    errors = settings.runtime_config_errors()

    assert "DATABASE_URL is required when vector search is enabled" in errors
    assert "ENCRYPTION_KEY is required when vector search is enabled" in errors


def test_evidence_cache_requires_database_and_encryption_key() -> None:
    settings = Settings(
        app_env="local",
        evidence_cache_enabled=True,
        database_url=None,
        encryption_key=None,
    )

    errors = settings.runtime_config_errors()

    assert "DATABASE_URL is required when evidence cache is enabled" in errors
    assert "ENCRYPTION_KEY is required when evidence cache is enabled" in errors


def test_production_config_rejects_openai_without_api_key() -> None:
    settings = _phi_ready_settings(
        llm_provider="openai",
        allow_phi_to_openai=True,
        openai_baa_confirmed=True,
        openai_data_policy_confirmed=True,
    )

    assert "OPENAI_API_KEY is required when OpenAI models are enabled" in (
        settings.runtime_config_errors()
    )


def test_production_config_rejects_openai_without_phi_approvals() -> None:
    settings = _phi_ready_settings(
        llm_provider="openai",
        embedding_provider="openai",
        openai_api_key="test-key",
    )

    errors = settings.runtime_config_errors()

    assert "ALLOW_PHI_TO_OPENAI must be true before PHI can be sent to OpenAI" in errors
    assert "OPENAI_BAA_CONFIRMED must be true before PHI can be sent to OpenAI" in errors
    assert "OPENAI_DATA_POLICY_CONFIRMED must be true before PHI can be sent to OpenAI" in errors


def test_production_config_rejects_openrouter_without_api_key() -> None:
    settings = _phi_ready_settings(
        llm_provider="openrouter",
        openrouter_demo_data_only=True,
    )

    assert "OPENROUTER_API_KEY is required when OpenRouter is enabled" in (
        settings.runtime_config_errors()
    )


def test_production_config_rejects_openrouter_without_demo_or_phi_approval() -> None:
    settings = _phi_ready_settings(
        llm_provider="openrouter",
        openrouter_api_key="test-key",
    )

    assert any(
        error.startswith("OPENROUTER_DEMO_DATA_ONLY must be true")
        for error in settings.runtime_config_errors()
    )


def test_production_config_accepts_openrouter_for_synthetic_demo_data() -> None:
    settings = _phi_ready_settings(
        llm_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_demo_data_only=True,
    )

    assert settings.runtime_config_errors() == []


def test_production_config_accepts_explicit_openai_phi_path() -> None:
    settings = _phi_ready_settings(
        llm_provider="openai",
        embedding_provider="openai",
        openai_api_key="test-key",
        allow_phi_to_openai=True,
        openai_baa_confirmed=True,
        openai_data_policy_confirmed=True,
    )

    assert settings.runtime_config_errors() == []


def test_phi_mode_applies_hard_gates_outside_production_name() -> None:
    settings = Settings(
        app_env="local",
        phi_mode=True,
        public_base_url="https://copilot.example.test",
        dev_auth_bypass=False,
        database_url="postgresql://copilot:secret@db.example.test:5432/copilot",
        encryption_key=TEST_FERNET_KEY,
        openemr_base_url="https://openemr.example.test",
        openemr_fhir_base_url="https://openemr.example.test/apis/default/fhir",
        openemr_oauth_token_url="https://openemr.example.test/oauth2/default/token",
        openemr_jwks_url="https://openemr.example.test/oauth2/default/jwks",
        openemr_jwt_issuer="https://openemr.example.test",
        openemr_jwt_audience="clinical-copilot",
        openemr_api_log_option=1,
        allow_phi_to_local=False,
    )

    assert settings.runtime_config_errors() == []


def test_phi_mode_rejects_invalid_encryption_key() -> None:
    settings = Settings(
        app_env="production",
        public_base_url="https://copilot.example.test",
        database_url="postgresql://copilot:secret@db.example.test:5432/copilot",
        encryption_key="not-a-fernet-key",
        dev_auth_bypass=False,
        openemr_base_url="https://openemr.example.test",
        openemr_fhir_base_url="https://openemr.example.test/apis/default/fhir",
        openemr_oauth_token_url="https://openemr.example.test/oauth2/default/token",
        openemr_jwks_url="https://openemr.example.test/oauth2/default/jwks",
        openemr_jwt_issuer="https://openemr.example.test",
        openemr_jwt_audience="clinical-copilot",
        openemr_api_log_option=1,
        allow_phi_to_local=False,
    )

    assert "ENCRYPTION_KEY must be a valid Fernet key" in settings.runtime_config_errors()


def test_readyz_reports_runtime_checks() -> None:
    response = TestClient(app).get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["checks"]["runtime_config"] is True


def test_capabilities_expose_llm_callable_tool_schemas() -> None:
    response = TestClient(app).get("/api/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["tools"]) == set(payload["tool_schemas"])
    assert payload["tools"]
    for name in payload["tools"]:
        contract = payload["tool_schemas"][name]
        assert contract["name"] == name
        assert contract["description"]
        assert contract["input_schema"]["type"] == "object"
        assert contract["output_schema"]["type"] == "object"

    notes_schema = payload["tool_schemas"]["get_recent_notes"]["input_schema"]
    assert notes_schema["required"] == ["patient_id"]
    assert notes_schema["properties"]["patient_id"]["minLength"] == 1
    search_schema = payload["tool_schemas"]["search_patient_evidence"]["input_schema"]
    assert search_schema["required"] == ["patient_id", "query"]
    assert search_schema["properties"]["query"]["minLength"] == 2
    assert "evidence_cache_enabled" in payload["providers"]


def test_vector_status_reports_default_disabled_state() -> None:
    response = TestClient(app).get("/api/vector/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["ready"] is True
    assert payload["embedding_provider"] == "hash"


def test_readyz_fails_phi_mode_when_database_is_unreachable() -> None:
    settings = Settings(
        app_env="local",
        phi_mode=True,
        public_base_url="https://copilot.example.test",
        dev_auth_bypass=False,
        database_url="postgresql://copilot:secret@127.0.0.1:1/copilot",
        encryption_key=TEST_FERNET_KEY,
        openemr_base_url="https://openemr.example.test",
        openemr_fhir_base_url="https://openemr.example.test/apis/default/fhir",
        openemr_oauth_token_url="https://openemr.example.test/oauth2/default/token",
        openemr_jwks_url="https://openemr.example.test/oauth2/default/jwks",
        openemr_jwt_issuer="https://openemr.example.test",
        openemr_jwt_audience="clinical-copilot",
        openemr_api_log_option=1,
        allow_phi_to_local=False,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = TestClient(app).get("/readyz")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["checks"]["database"] is False


def _phi_ready_settings(**overrides: object) -> Settings:
    values = {
        "app_env": "production",
        "public_base_url": "https://copilot.example.test",
        "database_url": "postgresql://copilot:secret@db.example.test:5432/copilot",
        "encryption_key": TEST_FERNET_KEY,
        "dev_auth_bypass": False,
        "openemr_base_url": "https://openemr.example.test",
        "openemr_fhir_base_url": "https://openemr.example.test/apis/default/fhir",
        "openemr_oauth_token_url": "https://openemr.example.test/oauth2/default/token",
        "openemr_jwks_url": "https://openemr.example.test/oauth2/default/jwks",
        "openemr_jwt_issuer": "https://openemr.example.test",
        "openemr_jwt_audience": "clinical-copilot",
        "openemr_api_log_option": 1,
        "allow_phi_to_local": False,
    }
    values.update(overrides)
    return Settings(**values)
