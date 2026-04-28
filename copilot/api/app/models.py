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


class CapabilityResponse(BaseModel):
    roles: list[Role]
    tools: list[str]
    providers: dict[str, bool]
    retention_days: int
