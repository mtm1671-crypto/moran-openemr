from __future__ import annotations

import base64
from typing import Any

from app.config import Settings
from app.openai_models import (
    OpenAIModelError,
    _extract_chat_completion_text,
    _extract_response_text,
    _post_openai_json,
    _post_openrouter_json,
)


class OcrProviderError(RuntimeError):
    pass


_OCR_INSTRUCTIONS = """
Transcribe the clinical document image exactly enough for deterministic extraction.
- Return plain text only, no markdown, no explanation.
- Preserve line order and table row order.
- Keep lab result rows as readable text with test name, result, flag, range, and unit when visible.
- Keep intake section headings and rows readable.
- Use [unclear] for unreadable characters.
- Do not infer missing values.
""".strip()


async def extract_image_text_with_provider(
    *,
    content: bytes,
    content_type: str,
    settings: Settings,
) -> str:
    if settings.ocr_provider == "openai":
        return await _extract_image_text_with_openai(
            content=content,
            content_type=content_type,
            settings=settings,
        )
    if settings.ocr_provider == "openrouter":
        return await _extract_image_text_with_openrouter(
            content=content,
            content_type=content_type,
            settings=settings,
        )
    raise OcrProviderError("Image OCR is not configured for local deterministic extraction")


async def _extract_image_text_with_openai(
    *,
    content: bytes,
    content_type: str,
    settings: Settings,
) -> str:
    image_url = f"data:{_data_url_content_type(content_type)};base64,{_base64(content)}"
    payload: dict[str, Any] = {
        "model": settings.openai_ocr_model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _OCR_INSTRUCTIONS},
                    {
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": settings.openai_ocr_detail,
                    },
                ],
            }
        ],
        "store": False,
        "max_output_tokens": settings.openai_ocr_max_output_tokens,
    }
    try:
        response_json = await _post_openai_json(settings=settings, path="/responses", payload=payload)
        text = _extract_response_text(response_json).strip()
    except OpenAIModelError as exc:
        raise OcrProviderError("OpenAI OCR request failed") from exc

    if not text:
        raise OcrProviderError("OpenAI OCR returned empty text")
    return text


async def _extract_image_text_with_openrouter(
    *,
    content: bytes,
    content_type: str,
    settings: Settings,
) -> str:
    image_url = f"data:{_data_url_content_type(content_type)};base64,{_base64(content)}"
    payload: dict[str, Any] = {
        "model": settings.openrouter_ocr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_INSTRUCTIONS},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "max_tokens": settings.openrouter_ocr_max_tokens,
        "temperature": 0,
    }
    try:
        response_json = await _post_openrouter_json(
            settings=settings,
            path="/chat/completions",
            payload=payload,
        )
        text = _extract_chat_completion_text(response_json).strip()
    except OpenAIModelError as exc:
        raise OcrProviderError("OpenRouter OCR request failed") from exc

    if not text:
        raise OcrProviderError("OpenRouter OCR returned empty text")
    return text


def _base64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


def _data_url_content_type(content_type: str) -> str:
    if content_type == "image/jpg":
        return "image/jpeg"
    return content_type
