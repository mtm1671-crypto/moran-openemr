from __future__ import annotations

import base64
import binascii
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


MIN_REVIEWABLE_CONFIDENCE = 0.55
MIN_AUTO_ACCEPT_CONFIDENCE = 0.9
MAX_DOCUMENT_BYTES = 2_000_000


class W2DocType(StrEnum):
    lab_pdf = "lab_pdf"
    intake_form = "intake_form"


class W2JobStatus(StrEnum):
    received = "received"
    extracting = "extracting"
    review_required = "review_required"
    ready_to_write = "ready_to_write"
    writing = "writing"
    completed = "completed"
    failed = "failed"


class W2FactStatus(StrEnum):
    extracted = "extracted"
    review_required = "review_required"
    approved = "approved"
    rejected = "rejected"
    written = "written"
    write_failed = "write_failed"


class W2FactType(StrEnum):
    lab_result = "lab_result"
    intake_chief_concern = "intake_chief_concern"
    intake_medication = "intake_medication"
    intake_allergy = "intake_allergy"
    intake_history = "intake_history"


class W2ProposedDestination(StrEnum):
    openemr_observation = "openemr_observation"
    derived_evidence = "derived_evidence"


class W2CitationSourceType(StrEnum):
    local_document = "local_document"
    openemr_document = "openemr_document"
    openemr_fhir = "openemr_fhir"
    guideline = "guideline"


class DocumentBoundingBox(BaseModel):
    page: int = Field(ge=1)
    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_order(self) -> DocumentBoundingBox:
        if self.x0 >= self.x1:
            raise ValueError("bbox x0 must be less than x1")
        if self.y0 >= self.y1:
            raise ValueError("bbox y0 must be less than y1")
        return self


class DocumentSourceCitation(BaseModel):
    source_type: W2CitationSourceType
    source_id: str = Field(min_length=1, max_length=180)
    page_or_section: str = Field(min_length=1, max_length=120)
    field_or_chunk_id: str = Field(min_length=1, max_length=160)
    quote_or_value: str = Field(min_length=1, max_length=240)
    bbox: DocumentBoundingBox | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_document_bbox(self) -> DocumentSourceCitation:
        if self.source_type in {
            W2CitationSourceType.local_document,
            W2CitationSourceType.openemr_document,
        } and self.bbox is None:
            raise ValueError("document citations require a bounding box")
        return self


class LabResultFact(BaseModel):
    test_name: str = Field(min_length=1, max_length=120)
    loinc_code: str | None = Field(default=None, max_length=40)
    value: str = Field(min_length=1, max_length=80)
    unit: str | None = Field(default=None, max_length=40)
    reference_range: str | None = Field(default=None, max_length=80)
    collection_date: date | None = None
    abnormal_flag: Literal["low", "normal", "high", "abnormal", "unknown"] = "unknown"
    source_citation: DocumentSourceCitation
    extraction_confidence: float = Field(ge=0, le=1)
    proposed_destination: Literal[W2ProposedDestination.openemr_observation] = (
        W2ProposedDestination.openemr_observation
    )


class IntakeFact(BaseModel):
    fact_type: Literal[
        W2FactType.intake_chief_concern,
        W2FactType.intake_medication,
        W2FactType.intake_allergy,
        W2FactType.intake_history,
    ]
    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=240)
    source_citation: DocumentSourceCitation
    extraction_confidence: float = Field(ge=0, le=1)
    proposed_destination: Literal[W2ProposedDestination.derived_evidence] = (
        W2ProposedDestination.derived_evidence
    )


class ExtractedFact(BaseModel):
    fact_id: str = Field(min_length=1, max_length=80)
    document_job_id: str = Field(min_length=1, max_length=80)
    patient_id: str = Field(min_length=1, max_length=100)
    doc_type: W2DocType
    fact_type: W2FactType
    display_label: str = Field(min_length=1, max_length=140)
    normalized_value: str = Field(min_length=1, max_length=280)
    status: W2FactStatus = W2FactStatus.review_required
    extraction_confidence: float = Field(ge=0, le=1)
    proposed_destination: W2ProposedDestination
    citation: DocumentSourceCitation
    payload: dict[str, Any] = Field(default_factory=dict)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    written_resource_id: str | None = None
    write_error: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def schema_valid(self) -> bool:
        return True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def citation_present(self) -> bool:
        return bool(self.citation.source_id and self.citation.field_or_chunk_id)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bbox_present(self) -> bool:
        return self.citation.bbox is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_human_review(self) -> bool:
        return (
            self.status == W2FactStatus.review_required
            or self.extraction_confidence < MIN_AUTO_ACCEPT_CONFIDENCE
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def blocking_reasons(self) -> list[str]:
        reasons: list[str] = []
        if self.extraction_confidence < MIN_REVIEWABLE_CONFIDENCE:
            reasons.append("extraction_confidence_below_review_threshold")
        if not self.citation_present:
            reasons.append("citation_missing")
        if not self.bbox_present:
            reasons.append("bbox_missing")
        if (
            self.proposed_destination == W2ProposedDestination.openemr_observation
            and self.fact_type != W2FactType.lab_result
        ):
            reasons.append("only_lab_results_can_write_observations")
        return reasons

    @model_validator(mode="after")
    def validate_destination(self) -> ExtractedFact:
        if (
            self.proposed_destination == W2ProposedDestination.openemr_observation
            and self.fact_type != W2FactType.lab_result
        ):
            raise ValueError("only lab_result facts can write OpenEMR Observations")
        return self


class DocumentSourceSummary(BaseModel):
    source_id: str
    filename: str
    content_type: str
    source_sha256: str
    byte_count: int


class DocumentJobRecord(BaseModel):
    job_id: str
    patient_id: str
    doc_type: W2DocType
    status: W2JobStatus
    actor_user_id: str
    source: DocumentSourceSummary
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None
    trace: list[str] = Field(default_factory=list)


class DocumentAttachExtractRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=100)
    doc_type: W2DocType
    filename: str = Field(min_length=1, max_length=160)
    content_type: str = Field(min_length=1, max_length=120)
    content_base64: str = Field(min_length=1)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        normalized = value.lower().strip()
        allowed = {"application/pdf", "text/plain", "text/csv", "application/octet-stream"}
        if normalized not in allowed:
            raise ValueError("unsupported document content type")
        return normalized

    def decoded_content(self) -> bytes:
        try:
            content = base64.b64decode(self.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("content_base64 must be valid base64") from exc
        if not content:
            raise ValueError("document content cannot be empty")
        if len(content) > MAX_DOCUMENT_BYTES:
            raise ValueError("document content exceeds maximum supported size")
        return content


class DocumentJobResponse(BaseModel):
    job: DocumentJobRecord
    fact_counts: dict[str, int]


class ReviewDecision(BaseModel):
    fact_id: str = Field(min_length=1, max_length=80)
    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=240)


class ReviewDecisionsRequest(BaseModel):
    decisions: list[ReviewDecision] = Field(min_length=1, max_length=100)


class DocumentReviewPayload(BaseModel):
    job: DocumentJobRecord
    facts: list[ExtractedFact]
    trace: list[str]


class DocumentReviewResult(BaseModel):
    job: DocumentJobRecord
    facts: list[ExtractedFact]
    fact_counts: dict[str, int]


class DocumentWriteResult(BaseModel):
    job: DocumentJobRecord
    written_count: int
    skipped_count: int
    failed_count: int
    facts: list[ExtractedFact]


def now_utc() -> datetime:
    return datetime.now(tz=UTC)

