from datetime import UTC, datetime
import json

import pytest
import respx
from httpx import Response

from app.config import Settings
from app.models import EvidenceObject
from app.openai_models import (
    OpenAIEmbeddingAdapter,
    OpenAIModelError,
    OpenAIProviderAdapter,
    OpenRouterProviderAdapter,
)


@pytest.mark.asyncio
@respx.mock
async def test_openai_provider_uses_responses_api_and_returns_cited_answer() -> None:
    settings = Settings(
        llm_provider="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.openai.test/v1",
        openai_reasoning_effort="none",
    )
    route = respx.post("https://api.openai.test/v1/responses").mock(
        return_value=Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "answer": "A1c was 8.6% on 2026-03-12.",
                        "evidence_ids": ["ev_a1c"],
                        "reasoning_summary": "Used cited lab evidence only.",
                    }
                ),
                "usage": {"input_tokens": 100, "output_tokens": 25, "total_tokens": 125},
            },
        )
    )

    answer = await OpenAIProviderAdapter(settings).answer(
        patient_id="p1",
        user_message="What were the recent labs?",
        evidence=[_evidence("ev_a1c", "lab_result", "A1c was 8.6% on 2026-03-12.")],
    )

    request_body = json.loads(route.calls[0].request.content)
    assert route.calls[0].request.headers["authorization"] == "Bearer test-key"
    assert request_body["model"] == "gpt-5.5"
    assert request_body["store"] is False
    assert request_body["text"]["format"]["type"] == "json_schema"
    assert answer.answer == "A1c was 8.6% on 2026-03-12."
    assert answer.citations[0].evidence_id == "ev_a1c"
    assert answer.audit["provider"] == "openai"
    assert answer.audit["usage"] == {
        "input_tokens": 100,
        "output_tokens": 25,
        "total_tokens": 125,
    }


@pytest.mark.asyncio
@respx.mock
async def test_openai_provider_retries_transient_model_failure() -> None:
    settings = Settings(
        llm_provider="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.openai.test/v1",
        openai_reasoning_effort="none",
        model_retry_backoff_seconds=0,
    )
    route = respx.post("https://api.openai.test/v1/responses").mock(
        side_effect=[
            Response(429, json={"error": {"message": "rate limited"}}),
            Response(
                200,
                json={
                    "output_text": json.dumps(
                        {
                            "answer": "A1c was 8.6%.",
                            "evidence_ids": ["ev_a1c"],
                            "reasoning_summary": "Used cited lab evidence only.",
                        }
                    )
                },
            ),
        ]
    )

    answer = await OpenAIProviderAdapter(settings).answer(
        patient_id="p1",
        user_message="What were the recent labs?",
        evidence=[_evidence("ev_a1c", "lab_result", "A1c was 8.6%.")],
    )

    assert answer.answer == "A1c was 8.6%."
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_openai_provider_rejects_unknown_evidence_ids() -> None:
    settings = Settings(
        llm_provider="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.openai.test/v1",
        openai_reasoning_effort="none",
    )
    respx.post("https://api.openai.test/v1/responses").mock(
        return_value=Response(
            200,
            json={
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "answer": "A1c was elevated.",
                                        "evidence_ids": ["ev_missing"],
                                        "reasoning_summary": "Invalid citation.",
                                    }
                                ),
                            }
                        ]
                    }
                ]
            },
        )
    )

    with pytest.raises(OpenAIModelError, match="unknown evidence ids"):
        await OpenAIProviderAdapter(settings).answer(
            patient_id="p1",
            user_message="What were the recent labs?",
            evidence=[_evidence("ev_a1c", "lab_result", "A1c was 8.6%.")],
        )


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_provider_uses_chat_completions_and_returns_cited_answer() -> None:
    settings = Settings(
        llm_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
        openrouter_demo_data_only=True,
    )
    route = respx.post("https://openrouter.test/api/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "answer": "A1c was 8.6% on 2026-03-12.",
                                    "evidence_ids": ["ev_a1c"],
                                    "reasoning_summary": "Used cited lab evidence only.",
                                }
                            ),
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 25, "total_tokens": 125},
            },
        )
    )

    answer = await OpenRouterProviderAdapter(settings).answer(
        patient_id="p1",
        user_message="What were the recent labs?",
        evidence=[_evidence("ev_a1c", "lab_result", "A1c was 8.6% on 2026-03-12.")],
    )

    request_body = json.loads(route.calls[0].request.content)
    assert route.calls[0].request.headers["authorization"] == "Bearer test-key"
    assert request_body["model"] == "nvidia/nemotron-3-super-120b-a12b:free"
    assert request_body["messages"][0]["role"] == "system"
    assert request_body["response_format"] == {"type": "json_object"}
    assert answer.answer == "A1c was 8.6% on 2026-03-12."
    assert answer.citations[0].evidence_id == "ev_a1c"
    assert answer.audit["provider"] == "openrouter"
    assert answer.audit["demo_data_only"] is True


@pytest.mark.asyncio
@respx.mock
async def test_openai_embeddings_rank_evidence_by_similarity() -> None:
    settings = Settings(
        embedding_provider="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.openai.test/v1",
    )
    route = respx.post("https://api.openai.test/v1/embeddings").mock(
        side_effect=[
            Response(
                200,
                json={
                    "data": [
                        {
                            "object": "embedding",
                            "embedding": [1.0, 0.0],
                            "index": 0,
                        }
                    ]
                },
            ),
            Response(
                200,
                json={
                    "data": [
                        {
                            "object": "embedding",
                            "embedding": [0.0, 1.0],
                            "index": 0,
                        },
                        {
                            "object": "embedding",
                            "embedding": [1.0, 0.0],
                            "index": 1,
                        },
                    ]
                },
            ),
        ]
    )
    problem = _evidence("ev_problem", "active_problem", "Active problem: hypertension.")
    lab = _evidence("ev_lab", "lab_result", "Creatinine was 1.4 mg/dL.")

    ranked = await OpenAIEmbeddingAdapter(settings).rank_evidence(
        message="kidney lab result",
        evidence=[problem, lab],
        limit=1,
    )

    assert ranked == [lab]
    assert route.call_count == 2
    first_body = json.loads(route.calls[0].request.content)
    assert first_body["model"] == "text-embedding-3-large"
    assert first_body["encoding_format"] == "float"


def _evidence(evidence_id: str, source_type: str, fact: str) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=evidence_id,
        patient_id="p1",
        source_type=source_type,
        source_id=evidence_id,
        display_name=evidence_id,
        fact=fact,
        retrieved_at=datetime.now(tz=UTC),
        source_url=f"/source/{evidence_id}",
    )
