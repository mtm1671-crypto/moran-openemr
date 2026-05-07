from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import EvidenceObject


@dataclass(frozen=True)
class GuidelineChunk:
    chunk_id: str
    domain: str
    title: str
    section_heading: str
    snippet: str
    source_url_or_path: str


@dataclass(frozen=True)
class GuidelineHit:
    chunk: GuidelineChunk
    score: float


GUIDELINE_CORPUS = [
    GuidelineChunk(
        chunk_id="diabetes-a1c-monitoring",
        domain="diabetes",
        title="Synthetic Diabetes Guideline",
        section_heading="A1c monitoring",
        snippet="Use recent A1c values as context for diabetes follow-up and monitoring.",
        source_url_or_path="synthetic://guidelines/diabetes#a1c-monitoring",
    ),
    GuidelineChunk(
        chunk_id="hypertension-bp-followup",
        domain="hypertension",
        title="Synthetic Hypertension Guideline",
        section_heading="Blood pressure follow-up",
        snippet="Use repeated blood pressure readings and medication adherence context during follow-up.",
        source_url_or_path="synthetic://guidelines/hypertension#bp-followup",
    ),
    GuidelineChunk(
        chunk_id="lipids-ldl-risk",
        domain="lipids",
        title="Synthetic Lipid Guideline",
        section_heading="LDL and cardiovascular risk",
        snippet="Use LDL results with cardiovascular risk factors when preparing chart summaries.",
        source_url_or_path="synthetic://guidelines/lipids#ldl-risk",
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
    scored = [
        GuidelineHit(chunk=chunk, score=_score_chunk(query_tokens, chunk))
        for chunk in GUIDELINE_CORPUS
    ]
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
                "domain": hit.chunk.domain,
                "score": hit.score,
            },
        )
        for hit in hits
    ]


def _score_chunk(query_tokens: set[str], chunk: GuidelineChunk) -> float:
    chunk_tokens = _tokens(
        " ".join([chunk.domain, chunk.title, chunk.section_heading, chunk.snippet])
    )
    if not query_tokens or not chunk_tokens:
        return 0.0
    overlap = query_tokens.intersection(chunk_tokens)
    return len(overlap) / len(chunk_tokens)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))
