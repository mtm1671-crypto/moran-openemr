import os
from typing import Any

import httpx

COPILOT_API_BASE_URL = os.getenv(
    "LIVE_COPILOT_API_BASE_URL",
    "https://copilot-api-production-9f84.up.railway.app",
).rstrip("/")
COPILOT_WEB_BASE_URL = os.getenv(
    "LIVE_COPILOT_WEB_BASE_URL",
    "https://copilot-web-production.up.railway.app",
).rstrip("/")
OPENEMR_BASE_URL = os.getenv(
    "LIVE_OPENEMR_BASE_URL",
    "https://openemr-production-f5ed.up.railway.app",
).rstrip("/")


def test_deployed_copilot_api_readyz_is_hardened() -> None:
    payload = _get_json(f"{COPILOT_API_BASE_URL}/readyz")

    assert payload["ok"] is True
    assert payload["environment"] == "production"
    checks = payload["checks"]
    assert checks["runtime_config"] is True
    assert checks["phi_controls"] is True
    assert checks["demo_auth_bypass"] is False
    assert checks["llm_egress_disabled"] is True
    assert checks["openai_configured"] is False
    assert checks["openrouter_configured"] is False
    assert checks["openemr_fhir_configured"] is True
    assert payload["errors"] == []


def test_deployed_web_ready_proxy_matches_hardened_api() -> None:
    payload = _get_json(f"{COPILOT_WEB_BASE_URL}/api/readyz")

    assert payload["ok"] is True
    checks = payload["checks"]
    assert checks["demo_auth_bypass"] is False
    assert checks["llm_egress_disabled"] is True
    assert checks["openai_configured"] is False
    assert checks["openrouter_configured"] is False


def test_deployed_model_status_has_no_external_phi_egress() -> None:
    payload = _get_json(f"{COPILOT_API_BASE_URL}/api/models/status")

    assert payload["phi_controls_required"] is True
    assert payload["llm_provider"] == "mock"
    assert payload["embedding_provider"] == "none"
    assert payload["ocr_provider"] == "none"
    assert payload["external_model_egress"] is False
    assert payload["openrouter_demo_data_only"] is False
    assert payload["openai_configured"] is False
    assert payload["openrouter_configured"] is False


def test_deployed_patient_and_demo_routes_are_not_public() -> None:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        patient_response = client.get(f"{COPILOT_API_BASE_URL}/api/patients")
        demo_source_response = client.get(f"{COPILOT_API_BASE_URL}/api/source/demo-lab-a1c")

    assert patient_response.status_code == 401
    assert demo_source_response.status_code == 404


def test_deployed_openemr_metadata_supports_observation_create() -> None:
    payload = _get_json(f"{OPENEMR_BASE_URL}/apis/default/fhir/metadata", timeout=30)
    resources = payload["rest"][0]["resource"]
    observation = next(resource for resource in resources if resource["type"] == "Observation")
    interactions = {interaction["code"] for interaction in observation["interaction"]}

    assert payload["resourceType"] == "CapabilityStatement"
    assert {"search-type", "read", "create"} <= interactions


def _get_json(url: str, *, timeout: float = 20) -> dict[str, Any]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return payload
