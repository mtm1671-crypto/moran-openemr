import json

import pytest
import respx
from httpx import Response

from app.config import Settings
from app.ocr_providers import OcrProviderError, extract_image_text_with_provider


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_ocr_uses_ocr_token_budget_and_retries_transient_failure() -> None:
    settings = Settings(
        app_env="local",
        ocr_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
        openrouter_demo_data_only=True,
        openrouter_ocr_model="baidu/qianfan-ocr-fast:free",
        openrouter_ocr_max_tokens=1234,
        model_retry_backoff_seconds=0,
    )
    route = respx.post("https://openrouter.test/api/v1/chat/completions").mock(
        side_effect=[
            Response(429, json={"error": {"message": "rate limited"}}),
            Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "TEST RESULT FLAG REFERENCE UNITS\nHemoglobin A1c 7.4 H 4.0-5.6 %",
                            }
                        }
                    ]
                },
            ),
        ]
    )

    text = await extract_image_text_with_provider(
        content=b"fake-png",
        content_type="image/png",
        settings=settings,
    )
    request_body = json.loads(route.calls.last.request.content)

    assert route.call_count == 2
    assert request_body["model"] == "baidu/qianfan-ocr-fast:free"
    assert request_body["max_tokens"] == 1234
    assert request_body["messages"][0]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert "Hemoglobin A1c" in text


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_ocr_fails_closed_when_vision_model_returns_no_text() -> None:
    settings = Settings(
        app_env="local",
        ocr_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
        openrouter_demo_data_only=True,
        openrouter_ocr_model="baidu/qianfan-ocr-fast:free",
    )
    respx.post("https://openrouter.test/api/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": None}}]},
        )
    )

    with pytest.raises(OcrProviderError, match="OpenRouter OCR request failed"):
        await extract_image_text_with_provider(
            content=b"fake-png",
            content_type="image/png",
            settings=settings,
        )
