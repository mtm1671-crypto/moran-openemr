import json
import math
from typing import Any, TypeGuard

import httpx

from app.config import Settings
from app.http_retry import RetryPolicy, request_with_retries
from app.models import Citation, EvidenceObject, VerifiedAnswer


class OpenAIModelError(RuntimeError):
    pass


_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string"},
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "reasoning_summary": {"type": "string"},
    },
    "required": ["answer", "evidence_ids", "reasoning_summary"],
}

_READ_ONLY_INSTRUCTIONS = """
You are AgentForge Clinical Co-Pilot. Answer only from the provided OpenEMR evidence.
This is a read-only clinician support workflow:
- Do not diagnose, recommend treatment, recommend medication changes, order tests, or write plans.
- If evidence is missing, say what is missing instead of guessing.
- Cite only evidence_ids from the provided evidence list.
- Keep the answer concise and source-backed.
Return only a JSON object matching the requested schema. Do not include markdown fences or prose
outside the JSON object.
""".strip()


class OpenAIProviderAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def answer(
        self,
        *,
        patient_id: str,
        user_message: str,
        evidence: list[EvidenceObject],
    ) -> VerifiedAnswer:
        evidence_for_model = evidence[: self._settings.model_evidence_limit]
        payload: dict[str, Any] = {
            "model": self._settings.openai_llm_model,
            "instructions": _READ_ONLY_INSTRUCTIONS,
            "input": _build_response_input(
                patient_id=patient_id,
                user_message=user_message,
                evidence=evidence_for_model,
            ),
            "store": False,
            "max_output_tokens": self._settings.openai_max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "clinical_copilot_answer",
                    "strict": True,
                    "schema": _ANSWER_SCHEMA,
                },
                "verbosity": "low",
            },
        }
        if self._settings.openai_reasoning_effort != "none":
            payload["reasoning"] = {"effort": self._settings.openai_reasoning_effort}

        response_json = await _post_openai_json(
            settings=self._settings,
            path="/responses",
            payload=payload,
        )
        raw_text = _extract_response_text(response_json)
        parsed = _parse_answer_json(raw_text)
        answer_text = parsed["answer"]
        evidence_ids = parsed["evidence_ids"]
        reasoning_summary = parsed["reasoning_summary"]

        known_evidence = {item.evidence_id: item for item in evidence_for_model}
        unknown_ids = [evidence_id for evidence_id in evidence_ids if evidence_id not in known_evidence]
        if unknown_ids:
            raise OpenAIModelError(f"OpenAI response cited unknown evidence ids: {unknown_ids}")
        if evidence_for_model and not evidence_ids:
            raise OpenAIModelError("OpenAI response did not cite retrieved evidence")

        citations = [
            Citation(
                evidence_id=evidence_id,
                label=known_evidence[evidence_id].display_name,
                source_url=known_evidence[evidence_id].source_url,
            )
            for evidence_id in evidence_ids
        ]
        return VerifiedAnswer(
            answer=answer_text,
            citations=citations,
            audit={
                "patient_id": patient_id,
                "provider": "openai",
                "model": self._settings.openai_llm_model,
                "verification": "pending",
                "evidence_count": len(evidence),
                "evidence_used_count": len(citations),
                "reasoning_summary": reasoning_summary,
                "usage": _usage_summary(response_json.get("usage")),
            },
        )


class OpenRouterProviderAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def answer(
        self,
        *,
        patient_id: str,
        user_message: str,
        evidence: list[EvidenceObject],
    ) -> VerifiedAnswer:
        evidence_for_model = evidence[: self._settings.model_evidence_limit]
        response_json = await _post_openrouter_json(
            settings=self._settings,
            path="/chat/completions",
            payload={
                "model": self._settings.openrouter_llm_model,
                "messages": [
                    {"role": "system", "content": _READ_ONLY_INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": _build_response_input(
                            patient_id=patient_id,
                            user_message=user_message,
                            evidence=evidence_for_model,
                        ),
                    },
                ],
                "max_tokens": self._settings.openrouter_max_tokens,
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
        )
        raw_text = _extract_chat_completion_text(response_json)
        parsed = _parse_answer_json(raw_text)
        answer_text = parsed["answer"]
        evidence_ids = parsed["evidence_ids"]
        reasoning_summary = parsed["reasoning_summary"]

        known_evidence = {item.evidence_id: item for item in evidence_for_model}
        unknown_ids = [evidence_id for evidence_id in evidence_ids if evidence_id not in known_evidence]
        if unknown_ids:
            raise OpenAIModelError(f"OpenRouter response cited unknown evidence ids: {unknown_ids}")
        if evidence_for_model and not evidence_ids:
            raise OpenAIModelError("OpenRouter response did not cite retrieved evidence")

        citations = [
            Citation(
                evidence_id=evidence_id,
                label=known_evidence[evidence_id].display_name,
                source_url=known_evidence[evidence_id].source_url,
            )
            for evidence_id in evidence_ids
        ]
        return VerifiedAnswer(
            answer=answer_text,
            citations=citations,
            audit={
                "patient_id": patient_id,
                "provider": "openrouter",
                "model": self._settings.openrouter_llm_model,
                "verification": "pending",
                "evidence_count": len(evidence),
                "evidence_used_count": len(citations),
                "reasoning_summary": reasoning_summary,
                "usage": _usage_summary(response_json.get("usage")),
                "demo_data_only": self._settings.openrouter_demo_data_only,
            },
        )


class OpenAIEmbeddingAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response_json = await _post_openai_json(
            settings=self._settings,
            path="/embeddings",
            payload={
                "model": self._settings.openai_embedding_model,
                "input": texts,
                "encoding_format": "float",
            },
        )
        data = response_json.get("data")
        if not isinstance(data, list):
            raise OpenAIModelError("OpenAI embeddings response did not include a data list")

        indexed_embeddings: list[tuple[int, list[float]]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            embedding = item.get("embedding")
            if not isinstance(index, int) or not _is_number_list(embedding):
                continue
            indexed_embeddings.append((index, [float(value) for value in embedding]))

        if len(indexed_embeddings) != len(texts):
            raise OpenAIModelError("OpenAI embeddings response count did not match input count")
        return [embedding for _, embedding in sorted(indexed_embeddings)]

    async def rank_evidence(
        self,
        *,
        message: str,
        evidence: list[EvidenceObject],
        limit: int,
    ) -> list[EvidenceObject]:
        if len(evidence) <= 1:
            return evidence

        query_embedding = (await self.embed_texts([message]))[0]
        evidence_embeddings = await self.embed_texts([_embedding_text(item) for item in evidence])
        scored = [
            (_cosine_similarity(query_embedding, embedding), index, item)
            for index, (item, embedding) in enumerate(zip(evidence, evidence_embeddings, strict=True))
        ]
        scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        return [item for _, _, item in scored[:limit]]


def _build_response_input(
    *,
    patient_id: str,
    user_message: str,
    evidence: list[EvidenceObject],
) -> str:
    return json.dumps(
        {
            "patient_id": patient_id,
            "clinician_question": user_message,
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "source_type": item.source_type,
                    "display_name": item.display_name,
                    "fact": item.fact,
                    "effective_at": item.effective_at.isoformat() if item.effective_at else None,
                    "confidence": item.confidence,
                }
                for item in evidence
            ],
        },
        separators=(",", ":"),
    )


async def _post_openai_json(
    *,
    settings: Settings,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if settings.openai_api_key is None:
        raise OpenAIModelError("OPENAI_API_KEY is not configured")

    try:
        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            response = await request_with_retries(
                client,
                "POST",
                _openai_url(settings, path),
                policy=RetryPolicy(
                    attempts=settings.model_retry_attempts,
                    backoff_seconds=settings.model_retry_backoff_seconds,
                ),
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response_json = response.json()
    except httpx.HTTPError as exc:
        raise OpenAIModelError("OpenAI request failed") from exc
    except json.JSONDecodeError as exc:
        raise OpenAIModelError("OpenAI response was not valid JSON") from exc

    if not isinstance(response_json, dict):
        raise OpenAIModelError("OpenAI response was not a JSON object")
    return response_json


async def _post_openrouter_json(
    *,
    settings: Settings,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if settings.openrouter_api_key is None:
        raise OpenAIModelError("OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
        "Content-Type": "application/json",
        "X-Title": settings.openrouter_app_name,
    }
    if settings.openrouter_site_url:
        headers["HTTP-Referer"] = settings.openrouter_site_url

    try:
        async with httpx.AsyncClient(timeout=settings.openrouter_timeout_seconds) as client:
            response = await request_with_retries(
                client,
                "POST",
                _openrouter_url(settings, path),
                policy=RetryPolicy(
                    attempts=settings.model_retry_attempts,
                    backoff_seconds=settings.model_retry_backoff_seconds,
                ),
                headers=headers,
                json=payload,
            )
            response_json = response.json()
    except httpx.HTTPError as exc:
        raise OpenAIModelError("OpenRouter request failed") from exc
    except json.JSONDecodeError as exc:
        raise OpenAIModelError("OpenRouter response was not valid JSON") from exc

    if not isinstance(response_json, dict):
        raise OpenAIModelError("OpenRouter response was not a JSON object")
    return response_json


def _openai_url(settings: Settings, path: str) -> str:
    return f"{settings.openai_base_url.rstrip('/')}/{path.lstrip('/')}"


def _openrouter_url(settings: Settings, path: str) -> str:
    return f"{settings.openrouter_base_url.rstrip('/')}/{path.lstrip('/')}"


def _extract_response_text(response_json: dict[str, Any]) -> str:
    direct_text = response_json.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    output = response_json.get("output")
    if not isinstance(output, list):
        raise OpenAIModelError("OpenAI response did not include output text")

    chunks: list[str] = []
    for output_item in output:
        if not isinstance(output_item, dict):
            continue
        content = output_item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)
            output_text = content_item.get("output_text")
            if isinstance(output_text, str) and output_text:
                chunks.append(output_text)

    if not chunks:
        raise OpenAIModelError("OpenAI response did not include output text")
    return "\n".join(chunks)


def _extract_chat_completion_text(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAIModelError("OpenRouter response did not include choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenAIModelError("OpenRouter response choice was invalid")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenAIModelError("OpenRouter response did not include a message")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text_item = item.get("text")
            if isinstance(text_item, str):
                chunks.append(text_item)
        text = "\n".join(chunks).strip()
        if text:
            return text
    raise OpenAIModelError("OpenRouter response did not include message text")


def _parse_answer_json(raw_text: str) -> dict[str, Any]:
    raw_text = _strip_markdown_json(raw_text)
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise OpenAIModelError("OpenAI answer was not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise OpenAIModelError("OpenAI answer was not a JSON object")
    answer = parsed.get("answer")
    evidence_ids = parsed.get("evidence_ids")
    reasoning_summary = parsed.get("reasoning_summary")
    if not isinstance(answer, str) or not answer.strip():
        raise OpenAIModelError("OpenAI answer was missing answer text")
    if not isinstance(evidence_ids, list) or not all(
        isinstance(evidence_id, str) for evidence_id in evidence_ids
    ):
        raise OpenAIModelError("OpenAI answer evidence_ids were invalid")
    if not isinstance(reasoning_summary, str):
        reasoning_summary = "Model returned an answer with validated source evidence IDs."
    return {
        "answer": answer,
        "evidence_ids": evidence_ids,
        "reasoning_summary": reasoning_summary,
    }


def _strip_markdown_json(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).removeprefix("json").strip()
    return stripped


def _usage_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        key: item
        for key, item in value.items()
        if key in {"input_tokens", "output_tokens", "total_tokens"}
        and isinstance(item, int)
    }


def _embedding_text(item: EvidenceObject) -> str:
    return f"{item.source_type}: {item.display_name}. {item.fact}"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise OpenAIModelError("Embedding dimensions did not match")
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0
    return dot / (left_norm * right_norm)


def _is_number_list(value: Any) -> TypeGuard[list[int | float]]:
    return isinstance(value, list) and all(isinstance(item, (int, float)) for item in value)
