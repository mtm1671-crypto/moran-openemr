import hashlib
import re
from typing import Protocol

from app.config import Settings
from app.models import EvidenceObject
from app.openai_models import OpenAIEmbeddingAdapter, OpenAIModelError
from app.persistence import (
    build_evidence_vector_record,
    search_evidence_vectors,
    upsert_evidence_vector_records,
)


class VectorStoreError(RuntimeError):
    pass


class EvidenceVectorizer(Protocol):
    @property
    def provider(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbeddingAdapter:
    def __init__(self, dimensions: int) -> None:
        if dimensions <= 0:
            raise VectorStoreError("Hash embedding dimensions must be positive")
        self._dimensions = dimensions

    @property
    def provider(self) -> str:
        return "hash"

    @property
    def model_name(self) -> str:
        return f"local-hash-v1-{self._dimensions}"

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_hash_embedding(text, self._dimensions) for text in texts]


class OpenAIVectorEmbeddingAdapter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._adapter = OpenAIEmbeddingAdapter(settings)

    @property
    def provider(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._settings.openai_embedding_model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self._adapter.embed_texts(texts)


def vectorizer_for_settings(settings: Settings) -> EvidenceVectorizer:
    if settings.vector_embedding_provider == "hash":
        return HashEmbeddingAdapter(settings.vector_embedding_dimensions)
    if settings.vector_embedding_provider == "openai":
        return OpenAIVectorEmbeddingAdapter(settings)
    raise VectorStoreError(f"Unsupported vector embedding provider: {settings.vector_embedding_provider}")


async def index_and_search_evidence(
    *,
    settings: Settings,
    patient_id: str,
    query: str,
    evidence: list[EvidenceObject],
) -> list[EvidenceObject]:
    if evidence:
        await index_patient_evidence(settings=settings, evidence=evidence)
    return await search_patient_evidence(settings=settings, patient_id=patient_id, query=query)


async def index_patient_evidence(*, settings: Settings, evidence: list[EvidenceObject]) -> int:
    if not evidence:
        return 0

    vectorizer = vectorizer_for_settings(settings)
    try:
        evidence_embeddings = await vectorizer.embed_texts([evidence_search_text(item) for item in evidence])
        records = [
            build_evidence_vector_record(
                settings=settings,
                evidence=item,
                embedding=embedding,
                embedding_provider=vectorizer.provider,
                embedding_model=vectorizer.model_name,
                ttl_days=settings.vector_index_ttl_days,
            )
            for item, embedding in zip(evidence, evidence_embeddings, strict=True)
        ]
        await upsert_evidence_vector_records(settings, records)
    except OpenAIModelError as exc:
        raise VectorStoreError(str(exc)) from exc
    except Exception as exc:
        raise VectorStoreError("Vector evidence indexing failed") from exc

    return len(records)


async def search_patient_evidence(
    *,
    settings: Settings,
    patient_id: str,
    query: str,
) -> list[EvidenceObject]:
    vectorizer = vectorizer_for_settings(settings)
    try:
        query_embedding = (await vectorizer.embed_texts([query]))[0]
        hits = await search_evidence_vectors(
            settings=settings,
            patient_id=patient_id,
            query_embedding=query_embedding,
            embedding_model=vectorizer.model_name,
            limit=settings.vector_search_limit,
            min_score=settings.vector_min_score,
            candidate_limit=settings.vector_candidate_limit,
        )
    except OpenAIModelError as exc:
        raise VectorStoreError(str(exc)) from exc
    except Exception as exc:
        raise VectorStoreError("Vector evidence search failed") from exc

    return [hit.evidence for hit in hits]


def evidence_search_text(evidence: EvidenceObject) -> str:
    return f"{evidence.source_type}: {evidence.display_name}. {evidence.fact}"


def _hash_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    tokens = _tokens(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())
