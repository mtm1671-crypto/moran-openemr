from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from app.document_models import (
    DocumentJobRecord,
    DocumentSourceSummary,
    ExtractedFact,
    W2DocType,
    W2FactStatus,
    W2JobStatus,
    now_utc,
)
from app.models import EvidenceObject


@dataclass(frozen=True)
class StoredDocumentSource:
    source_id: str
    patient_id: str
    doc_type: W2DocType
    filename: str
    content_type: str
    source_sha256: str
    content: bytes
    created_at: datetime

    def summary(self) -> DocumentSourceSummary:
        return DocumentSourceSummary(
            source_id=self.source_id,
            filename=self.filename,
            content_type=self.content_type,
            source_sha256=self.source_sha256,
            byte_count=len(self.content),
        )


_SOURCES: dict[str, StoredDocumentSource] = {}
_JOBS: dict[str, DocumentJobRecord] = {}
_FACTS_BY_JOB: dict[str, list[ExtractedFact]] = {}
_JOB_BY_SOURCE_KEY: dict[tuple[str, W2DocType, str], str] = {}


def reset_document_workflow_store() -> None:
    _SOURCES.clear()
    _JOBS.clear()
    _FACTS_BY_JOB.clear()
    _JOB_BY_SOURCE_KEY.clear()


def source_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def find_reusable_job(*, patient_id: str, doc_type: W2DocType, source_hash: str) -> DocumentJobRecord | None:
    job_id = _JOB_BY_SOURCE_KEY.get((patient_id, doc_type, source_hash))
    if job_id is None:
        return None
    return _JOBS.get(job_id)


def create_document_workflow(
    *,
    patient_id: str,
    doc_type: W2DocType,
    filename: str,
    content_type: str,
    content: bytes,
    actor_user_id: str,
) -> tuple[DocumentJobRecord, StoredDocumentSource]:
    digest = source_sha256(content)
    existing = find_reusable_job(patient_id=patient_id, doc_type=doc_type, source_hash=digest)
    if existing is not None:
        return existing, _SOURCES[existing.source.source_id]

    source_id = f"local-doc-{digest[:24]}"
    source = StoredDocumentSource(
        source_id=source_id,
        patient_id=patient_id,
        doc_type=doc_type,
        filename=filename,
        content_type=content_type,
        source_sha256=digest,
        content=content,
        created_at=now_utc(),
    )
    job = DocumentJobRecord(
        job_id=f"w2doc-{uuid4()}",
        patient_id=patient_id,
        doc_type=doc_type,
        status=W2JobStatus.received,
        actor_user_id=actor_user_id,
        source=source.summary(),
        created_at=source.created_at,
        updated_at=source.created_at,
        trace=["source_received"],
    )
    _SOURCES[source_id] = source
    _JOBS[job.job_id] = job
    _FACTS_BY_JOB[job.job_id] = []
    _JOB_BY_SOURCE_KEY[(patient_id, doc_type, digest)] = job.job_id
    return job, source


def read_document_job(job_id: str) -> DocumentJobRecord | None:
    return _JOBS.get(job_id)


def read_document_source(source_id: str) -> StoredDocumentSource | None:
    return _SOURCES.get(source_id)


def update_document_job(
    job_id: str,
    *,
    status: W2JobStatus,
    trace: str | None = None,
    error_code: str | None = None,
) -> DocumentJobRecord:
    job = require_document_job(job_id)
    next_trace = [*job.trace, trace] if trace else job.trace
    updated = job.model_copy(
        update={
            "status": status,
            "updated_at": now_utc(),
            "error_code": error_code,
            "trace": next_trace,
        }
    )
    _JOBS[job_id] = updated
    return updated


def replace_document_facts(job_id: str, facts: list[ExtractedFact]) -> None:
    require_document_job(job_id)
    _FACTS_BY_JOB[job_id] = list(facts)


def read_document_facts(job_id: str) -> list[ExtractedFact]:
    require_document_job(job_id)
    return list(_FACTS_BY_JOB.get(job_id, []))


def update_document_fact(job_id: str, fact: ExtractedFact) -> None:
    facts = read_document_facts(job_id)
    for index, existing in enumerate(facts):
        if existing.fact_id == fact.fact_id:
            facts[index] = fact
            _FACTS_BY_JOB[job_id] = facts
            return
    raise KeyError(f"Fact was not found: {fact.fact_id}")


def require_document_job(job_id: str) -> DocumentJobRecord:
    job = read_document_job(job_id)
    if job is None:
        raise KeyError(f"Document job was not found: {job_id}")
    return job


def fact_counts(facts: list[ExtractedFact]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fact in facts:
        counts[fact.status.value] = counts.get(fact.status.value, 0) + 1
    return counts


def approved_document_evidence(patient_id: str) -> list[EvidenceObject]:
    evidence: list[EvidenceObject] = []
    for job_id, facts in _FACTS_BY_JOB.items():
        job = _JOBS.get(job_id)
        if job is None or job.patient_id != patient_id:
            continue
        for fact in facts:
            if fact.status not in {W2FactStatus.approved, W2FactStatus.written}:
                continue
            evidence.append(_fact_to_evidence(job, fact))
    return evidence


def _fact_to_evidence(job: DocumentJobRecord, fact: ExtractedFact) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=f"document:{fact.fact_id}",
        patient_id=job.patient_id,
        source_system="openemr",
        source_type=fact.fact_type.value,
        source_id=fact.fact_id,
        display_name=fact.display_label,
        fact=f"{fact.display_label}: {fact.normalized_value}.",
        retrieved_at=now_utc(),
        confidence="derived",
        source_url=f"/api/documents/{job.job_id}/review",
        metadata={
            "schema": "w2_document_fact_v1",
            "document_job_id": job.job_id,
            "doc_type": job.doc_type.value,
            "citation": fact.citation.model_dump(mode="json"),
            "proposed_destination": fact.proposed_destination.value,
            "written_resource_id": fact.written_resource_id,
        },
    )

