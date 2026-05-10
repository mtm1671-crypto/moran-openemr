from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from math import sqrt

from app.models import EvidenceObject


@dataclass(frozen=True)
class GuidelineChunk:
    corpus_id: str
    chunk_id: str
    domain: str
    source_authority: str
    title: str
    section_heading: str
    snippet: str
    source_url_or_path: str


@dataclass(frozen=True)
class GuidelineHit:
    chunk: GuidelineChunk
    score: float
    sparse_score: float
    dense_score: float


GUIDELINE_CORPUS = [
    GuidelineChunk(
        corpus_id="af-w2-primary-care-source-guidelines-v1",
        chunk_id="ada-standards-2026-glycemic-assessment",
        domain="diabetes",
        source_authority="American Diabetes Association",
        title="Standards of Care in Diabetes - 2026",
        section_heading="Glycemic goals and hypoglycemia",
        snippet=(
            "Use A1C and other glycemic data as source-backed context when reviewing diabetes "
            "control, follow-up needs, and patient-specific risk."
        ),
        source_url_or_path=(
            "https://professional.diabetes.org/standards-of-care/practice-guidelines-resources"
            "#diabetes-a1c-monitoring"
        ),
    ),
    GuidelineChunk(
        corpus_id="af-w2-primary-care-source-guidelines-v1",
        chunk_id="aha-acc-2025-hypertension-bp-confirmation",
        domain="hypertension",
        source_authority="American Heart Association and American College of Cardiology",
        title="2025 Guideline for the Prevention, Detection, Evaluation, and Management of High Blood Pressure in Adults",
        section_heading="Blood pressure confirmation and longitudinal management",
        snippet=(
            "Treat single blood pressure readings as context that should be interpreted with "
            "confirmed measurements, longitudinal trend, adherence, and cardiovascular risk."
        ),
        source_url_or_path=(
            "https://professional.heart.org/en/science-news/2025-guideline-for-the-prevention-detection-evaluation-and-management-of-high-blood-pressure-in-adults"
            "#hypertension-blood-pressure"
        ),
    ),
    GuidelineChunk(
        corpus_id="af-w2-primary-care-source-guidelines-v1",
        chunk_id="aha-acc-2018-cholesterol-ldl-risk",
        domain="lipids",
        source_authority="American Heart Association and American College of Cardiology",
        title="2018 Guideline on the Management of Blood Cholesterol",
        section_heading="LDL and cardiovascular risk",
        snippet=(
            "Use LDL cholesterol values together with ASCVD risk factors when preparing "
            "source-backed lipid summaries for clinician review."
        ),
        source_url_or_path=(
            "https://www.acc.org/Latest-in-Cardiology/ten-points-to-remember/2018/11/09/14/36/2018-Guideline-on-Management-of-Blood-Cholesterol"
            "#lipids-ldl-risk"
        ),
    ),
]


def retrieve_guideline_chunks(
    *,
    question: str,
    patient_facts: list[str],
    extracted_facts: list[str],
    limit: int = 3,
) -> list[GuidelineHit]:
    query_tokens = _tokens(" ".join([question, *patient_facts, *extracted_facts]))
    query_vector = _hashed_vector(query_tokens)
    scored = []
    for chunk in GUIDELINE_CORPUS:
        sparse_score = _sparse_score_chunk(query_tokens, chunk)
        dense_score = _dense_score_chunk(query_vector, chunk)
        score = (0.65 * sparse_score) + (0.35 * dense_score)
        scored.append(
            GuidelineHit(
                chunk=chunk,
                score=score,
                sparse_score=sparse_score,
                dense_score=dense_score,
            )
        )
    scored = [hit for hit in scored if hit.score > 0]
    scored.sort(key=lambda hit: hit.score, reverse=True)
    return scored[:limit]


def guideline_hits_to_evidence(
    *,
    patient_id: str,
    hits: list[GuidelineHit],
) -> list[EvidenceObject]:
    retrieved_at = datetime.now(tz=UTC)
    return [
        EvidenceObject(
            evidence_id=f"guideline:{hit.chunk.chunk_id}",
            patient_id=patient_id,
            source_type="guideline",
            source_id=hit.chunk.chunk_id,
            display_name=f"{hit.chunk.title}: {hit.chunk.section_heading}",
            fact=(
                f"Guideline context ({hit.chunk.domain}): "
                f"{hit.chunk.section_heading}. {hit.chunk.snippet}"
            ),
            retrieved_at=retrieved_at,
            confidence="source_record",
            source_url=hit.chunk.source_url_or_path,
            metadata={
                "schema": "w2_guideline_chunk_v1",
                "retrieval_mode": "hybrid_sparse_dense_guideline_rag",
                "corpus_id": hit.chunk.corpus_id,
                "source_type": "guideline",
                "source_id": hit.chunk.chunk_id,
                "source_authority": hit.chunk.source_authority,
                "title": hit.chunk.title,
                "section": hit.chunk.section_heading,
                "section_heading": hit.chunk.section_heading,
                "domain": hit.chunk.domain,
                "snippet": hit.chunk.snippet,
                "score": hit.score,
                "sparse_score": hit.sparse_score,
                "dense_score": hit.dense_score,
            },
        )
        for hit in hits
    ]


def _sparse_score_chunk(query_tokens: set[str], chunk: GuidelineChunk) -> float:
    chunk_tokens = _tokens(
        " ".join(
            [
                chunk.domain,
                chunk.source_authority,
                chunk.title,
                chunk.section_heading,
                chunk.snippet,
            ]
        )
    )
    if not query_tokens or not chunk_tokens:
        return 0.0
    overlap = query_tokens.intersection(chunk_tokens)
    return len(overlap) / len(chunk_tokens)


def _dense_score_chunk(query_vector: list[float], chunk: GuidelineChunk) -> float:
    chunk_vector = _hashed_vector(
        _tokens(
            " ".join(
                [
                    chunk.domain,
                    chunk.source_authority,
                    chunk.title,
                    chunk.section_heading,
                    chunk.snippet,
                ]
            )
        )
    )
    return _cosine(query_vector, chunk_vector)


def _tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_SEMANTIC_EXPANSIONS.get(token, set()))
    return expanded


def _hashed_vector(tokens: set[str], *, dimensions: int = 32) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokens:
        bucket = sum(token.encode("utf-8")) % dimensions
        vector[bucket] += 1.0
    return vector


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return (
        sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
        / (left_norm * right_norm)
    )


_SEMANTIC_EXPANSIONS = {
    "a1c": {"diabetes", "hemoglobin", "monitoring"},
    "cholesterol": {"lipids", "ldl", "risk"},
    "ldl": {"lipids", "cholesterol", "risk"},
    "lipid": {"lipids", "cholesterol", "risk"},
    "pressure": {"hypertension", "blood"},
    "bp": {"hypertension", "blood", "pressure"},
    "adherence": {"medication", "follow", "up"},
}
