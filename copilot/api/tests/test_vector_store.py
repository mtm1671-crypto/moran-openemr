import pytest

from app.config import Settings
from app.vector_store import HashEmbeddingAdapter, vectorizer_for_settings


@pytest.mark.asyncio
async def test_hash_embedding_adapter_is_deterministic_and_normalized() -> None:
    adapter = HashEmbeddingAdapter(dimensions=16)

    left = (await adapter.embed_texts(["A1c diabetes medication adherence"]))[0]
    right = (await adapter.embed_texts(["A1c diabetes medication adherence"]))[0]

    assert left == right
    assert len(left) == 16
    assert sum(value * value for value in left) == pytest.approx(1.0)
    assert adapter.provider == "hash"
    assert adapter.model_name == "local-hash-v1-16"


def test_vectorizer_for_settings_uses_hash_provider_by_default() -> None:
    settings = Settings(vector_embedding_dimensions=32)

    vectorizer = vectorizer_for_settings(settings)

    assert vectorizer.provider == "hash"
    assert vectorizer.model_name == "local-hash-v1-32"
