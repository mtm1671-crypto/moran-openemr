import os
from typing import Any

import httpx

COPILOT_API_BASE_URL = os.getenv(
    "LIVE_COPILOT_API_BASE_URL",
    "https://copilot-api-production-9f84.up.railway.app",
).rstrip("/")


def test_deployed_ocr_policy_is_fail_closed_without_approved_provider() -> None:
    model_status = _get_json(f"{COPILOT_API_BASE_URL}/api/models/status")
    readyz = _get_json(f"{COPILOT_API_BASE_URL}/readyz")

    assert model_status["ocr_provider"] == "none"
    assert model_status["ocr_enabled"] is False
    assert model_status["vision_ocr_enabled"] is False
    assert model_status["external_model_egress"] is False
    assert readyz["checks"]["ocr_enabled"] is False
    assert readyz["checks"]["vision_ocr_enabled"] is False
    assert readyz["checks"]["llm_egress_disabled"] is True


def _get_json(url: str) -> dict[str, Any]:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        response = client.get(url)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return payload
