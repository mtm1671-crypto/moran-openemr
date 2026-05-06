from __future__ import annotations

import hashlib

from app.document_models import (
    ExtractedFact,
    IntakeFact,
    LabResultFact,
    W2DocType,
    W2FactStatus,
    W2FactType,
    W2ProposedDestination,
)
from app.extraction_adapters import extract_typed_facts
from app.config import Settings
from app.ocr_layout import extract_layout, extract_layout_async


def extract_document_facts(
    *,
    job_id: str,
    patient_id: str | None,
    doc_type: W2DocType,
    source_id: str,
    content: bytes,
    content_type: str,
) -> list[ExtractedFact]:
    layout = extract_layout(content, content_type)
    typed_facts = extract_typed_facts(doc_type=doc_type, layout=layout, source_id=source_id)
    return [
        _normalize_fact(
            job_id=job_id,
            patient_id=patient_id,
            doc_type=doc_type,
            fact=fact,
        )
        for fact in typed_facts
    ]


async def extract_document_facts_async(
    *,
    job_id: str,
    patient_id: str | None,
    doc_type: W2DocType,
    source_id: str,
    content: bytes,
    content_type: str,
    settings: Settings,
) -> list[ExtractedFact]:
    layout = await extract_layout_async(content, content_type, settings)
    typed_facts = extract_typed_facts(doc_type=doc_type, layout=layout, source_id=source_id)
    return [
        _normalize_fact(
            job_id=job_id,
            patient_id=patient_id,
            doc_type=doc_type,
            fact=fact,
        )
        for fact in typed_facts
    ]


def _normalize_fact(
    *,
    job_id: str,
    patient_id: str | None,
    doc_type: W2DocType,
    fact: LabResultFact | IntakeFact,
) -> ExtractedFact:
    if isinstance(fact, LabResultFact):
        normalized = _lab_normalized_value(fact)
        return ExtractedFact(
            fact_id=_fact_id(job_id, "lab", fact.test_name, normalized),
            document_job_id=job_id,
            patient_id=patient_id,
            doc_type=doc_type,
            fact_type=W2FactType.lab_result,
            display_label=fact.test_name,
            normalized_value=normalized,
            status=W2FactStatus.review_required,
            extraction_confidence=fact.extraction_confidence,
            proposed_destination=W2ProposedDestination.openemr_observation,
            citation=fact.source_citation,
            payload=fact.model_dump(mode="json"),
        )

    return ExtractedFact(
        fact_id=_fact_id(job_id, fact.fact_type, fact.label, fact.value),
        document_job_id=job_id,
        patient_id=patient_id,
        doc_type=doc_type,
        fact_type=fact.fact_type,
        display_label=fact.label,
        normalized_value=fact.value,
        status=W2FactStatus.review_required,
        extraction_confidence=fact.extraction_confidence,
        proposed_destination=W2ProposedDestination.derived_evidence,
        citation=fact.source_citation,
        payload=fact.model_dump(mode="json"),
    )


def _lab_normalized_value(fact: LabResultFact) -> str:
    value = fact.value
    if fact.unit:
        value = f"{value} {fact.unit}"
    parts = [value]
    if fact.collection_date:
        parts.append(f"on {fact.collection_date.isoformat()}")
    if fact.abnormal_flag != "unknown":
        parts.append(f"({fact.abnormal_flag})")
    return " ".join(parts)


def _fact_id(*parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"w2fact-{digest[:24]}"
