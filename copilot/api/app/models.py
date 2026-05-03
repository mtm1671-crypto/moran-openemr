from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Role(StrEnum):
    doctor = "doctor"
    np_pa = "np_pa"
    nurse = "nurse"
    ma = "ma"
    admin = "admin"


class RequestUser(BaseModel):
    user_id: str
    role: Role
    scopes: list[str] = Field(default_factory=list)
    practitioner_id: str | None = None
    organization_id: str | None = None
    access_token: str | None = Field(default=None, exclude=True)


class PatientSummary(BaseModel):
    patient_id: str
    display_name: str
    birth_date: str | None = None
    gender: str | None = None
    source_system: Literal["openemr"] = "openemr"


class EvidenceObject(BaseModel):
    evidence_id: str
    patient_id: str
    source_system: Literal["openemr"] = "openemr"
    source_type: str
    source_id: str
    display_name: str
    fact: str
    effective_at: datetime | None = None
    source_updated_at: datetime | None = None
    retrieved_at: datetime
    confidence: Literal["source_record", "derived", "unknown"] = "source_record"
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    evidence_id: str
    label: str
    source_url: str | None = None


class VerifiedAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    audit: dict[str, Any]


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    quick_question_id: str | None = None
    conversation_id: str | None = None


class ToolContract(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class CapabilityResponse(BaseModel):
    roles: list[Role]
    tools: list[str]
    tool_schemas: dict[str, ToolContract] = Field(default_factory=dict)
    providers: dict[str, bool]
    retention_days: int


class ReindexRequest(BaseModel):
    force: bool = False


class ReindexResponse(BaseModel):
    job_id: str
    status: str
    patient_id: str
    indexed_evidence_count: int | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    actor_user_id: str
    patient_id_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ObservabilityStatusResponse(BaseModel):
    structured_logging_enabled: bool
    audit_persistence_required: bool
    conversation_persistence_enabled: bool
    vector_search_enabled: bool
    vector_index_backend: str
    service_account_enabled: bool
    nightly_maintenance_enabled: bool
    nightly_reindex_enabled: bool
