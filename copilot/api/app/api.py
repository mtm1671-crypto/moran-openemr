"""FastAPI routes for the Clinical Co-Pilot.

This module is the API orchestrator. It keeps the model on a short leash:
authenticate the OpenEMR user, lock the selected patient, retrieve evidence,
optionally search derived vector evidence, call the configured model provider,
verify citations, and only then stream a final answer.
"""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import get_request_user
from app.config import Settings, get_settings
from app.document_ingestion import router as document_router
from app.document_storage import approved_document_evidence
from app.evidence_tools import EvidenceRetrievalResult, FhirEvidenceService
from app.fhir_client import OpenEMRFhirClient
from app.guideline_rag import guideline_hits_to_evidence, retrieve_guideline_chunks
from app.models import (
    CapabilityResponse,
    ChatRequest,
    EvidenceObject,
    JobStatusResponse,
    ObservabilityStatusResponse,
    PatientSummary,
    RequestUser,
    ReindexRequest,
    ReindexResponse,
    Role,
    ToolContract,
)
from app.jobs import run_patient_reindex
from app.openemr_auth import resolve_fhir_bearer_token
from app.observation_writer import openemr_observation_create_supported
from app.persistence import (
    append_chat_messages,
    build_audit_event,
    build_evidence_cache_record,
    database_ready,
    document_workflow_persistence_configured,
    document_workflow_storage_ready,
    evidence_cache_ready,
    initialize_phi_schema,
    operational_storage_ready,
    read_evidence_cache_record,
    read_approved_document_evidence,
    read_job_run,
    vector_store_ready,
    write_audit_event,
    write_evidence_cache_record,
)
from app.openai_models import (
    OpenAIEmbeddingAdapter,
    OpenAIModelError,
    OpenAIProviderAdapter,
    OpenRouterProviderAdapter,
)
from app.providers import MockProviderAdapter, ProviderAdapter
from app.telemetry import emit_telemetry_event
from app.vector_store import VectorStoreError, index_and_search_evidence, search_patient_evidence
from app.verifier import VerificationError, verify_answer

router = APIRouter()
router.include_router(document_router)


async def initialize_phi_storage(settings: Settings) -> None:
    # These tables are derived/product storage, not OpenEMR truth. They are still
    # required when PHI controls, vector search, or encrypted evidence cache are on.
    if (
        settings.requires_phi_controls()
        or settings.vector_search_enabled
        or settings.evidence_cache_enabled
        or settings.document_workflow_persistence_enabled
    ):
        await initialize_phi_schema(settings)


class HealthResponse(BaseModel):
    ok: bool
    service: str
    environment: str


class ReadinessResponse(BaseModel):
    ok: bool
    service: str
    environment: str
    checks: dict[str, bool]
    errors: list[str]


class VectorStatusResponse(BaseModel):
    enabled: bool
    ready: bool
    backend: str
    embedding_provider: str
    embedding_dimensions: int
    search_limit: int
    candidate_limit: int


class ModelStatusResponse(BaseModel):
    llm_provider: str
    llm_model: str | None
    embedding_provider: str
    embedding_model: str | None
    ocr_provider: str
    ocr_model: str | None
    ocr_enabled: bool
    vision_ocr_enabled: bool
    external_model_egress: bool
    phi_controls_required: bool
    openai_configured: bool
    openrouter_configured: bool
    openrouter_demo_data_only: bool
    model_retry_attempts: int


@router.get("/healthz", response_model=HealthResponse)
async def healthz(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(ok=True, service="clinical-copilot-api", environment=settings.app_env)


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(settings: Settings = Depends(get_settings)) -> ReadinessResponse:
    errors = settings.runtime_config_errors()
    database_ok = True
    if (
        settings.requires_phi_controls()
        or settings.vector_search_enabled
        or settings.evidence_cache_enabled
        or settings.document_workflow_persistence_enabled
    ):
        database_ok = await database_ready(settings)
        if not database_ok:
            errors = [*errors, "DATABASE_URL did not pass connectivity check"]
    vector_ok = await vector_store_ready(settings)
    if settings.vector_search_enabled and not vector_ok:
        errors = [*errors, "vector store schema did not pass readiness check"]
    cache_ok = await evidence_cache_ready(settings)
    if settings.evidence_cache_enabled and not cache_ok:
        errors = [*errors, "evidence cache schema did not pass readiness check"]
    document_workflow_storage_ok = await document_workflow_storage_ready(settings)
    if settings.document_workflow_persistence_enabled and not document_workflow_storage_ok:
        errors = [*errors, "document workflow storage schema did not pass readiness check"]
    operational_ok = True
    if (
        settings.requires_phi_controls()
        or settings.database_url is not None
        or settings.document_workflow_persistence_enabled
    ):
        operational_ok = await operational_storage_ready(settings)
        if not operational_ok:
            errors = [*errors, "operational PHI storage schema did not pass readiness check"]
    service_account_configured = (
        settings.openemr_service_account_enabled
        and (
            settings.openemr_service_bearer_token is not None
            or (
                settings.openemr_service_client_id is not None
                and settings.openemr_service_client_secret is not None
                and (
                    settings.openemr_service_token_url is not None
                    or settings.openemr_oauth_token_url is not None
                )
            )
        )
    )
    service_account_ok = not settings.openemr_service_account_enabled or service_account_configured
    nightly_reindex_ok = not settings.nightly_reindex_enabled or service_account_configured
    if not nightly_reindex_ok:
        errors = [*errors, "OpenEMR service account is required for nightly reindex"]
    openai_configured = not settings.uses_openai_models() or settings.openai_api_key is not None
    openrouter_configured = (
        not settings.uses_openrouter_models() or settings.openrouter_api_key is not None
    )
    ocr_provider_configured = (
        settings.ocr_provider == "none"
        or (settings.ocr_provider == "openai" and settings.openai_api_key is not None)
        or (settings.ocr_provider == "openrouter" and settings.openrouter_api_key is not None)
    )
    ocr_model_configured = settings.ocr_model_configured()

    return ReadinessResponse(
        ok=not errors,
        service="clinical-copilot-api",
        environment=settings.app_env,
        checks={
            "runtime_config": not errors,
            "phi_controls": settings.requires_phi_controls(),
            "database": database_ok,
            "vector_search_enabled": settings.vector_search_enabled,
            "vector_store": vector_ok,
            "pgvector_backend": settings.vector_index_backend == "pgvector",
            "evidence_cache_enabled": settings.evidence_cache_enabled,
            "evidence_cache": cache_ok,
            "document_workflow_persistence_enabled": settings.document_workflow_persistence_enabled,
            "document_workflow_database_configured": settings.database_url is not None,
            "document_workflow_encryption_configured": settings.encryption_key is not None,
            "document_workflow_storage": document_workflow_storage_ok,
            "document_workflow_persistence_ready": (
                settings.document_workflow_persistence_enabled and document_workflow_storage_ok
            ),
            "operational_storage": operational_ok,
            "audit_persistence": operational_ok,
            "conversation_persistence": operational_ok and settings.conversation_persistence_enabled,
            "job_status_storage": operational_ok,
            "service_account_configured": service_account_configured,
            "service_account_config_valid": service_account_ok,
            "nightly_maintenance_enabled": settings.nightly_maintenance_enabled,
            "nightly_reindex_enabled": settings.nightly_reindex_enabled,
            "structured_logging": settings.structured_logging_enabled,
            "ocr_enabled": settings.ocr_provider != "none",
            "ocr_provider_configured": ocr_provider_configured,
            "ocr_model_configured": ocr_model_configured,
            "vision_ocr_enabled": settings.ocr_provider in {"openai", "openrouter"},
            "openemr_fhir_configured": settings.openemr_fhir_base_url is not None
            or not settings.requires_phi_controls(),
            "openemr_tls_verify": settings.openemr_tls_verify or not settings.requires_phi_controls(),
            "llm_egress_disabled": (
                settings.llm_provider == "mock"
                and settings.embedding_provider == "none"
                and settings.ocr_provider == "none"
                and not (
                    settings.vector_search_enabled
                    and settings.vector_embedding_provider == "openai"
                )
                and not settings.allow_phi_to_anthropic
                and not settings.allow_phi_to_openai
                and not settings.allow_phi_to_openrouter
                and not settings.allow_phi_to_local
            )
            or not settings.requires_phi_controls(),
            "openai_configured": openai_configured,
            "openrouter_configured": openrouter_configured,
        },
        errors=errors,
    )


@router.get("/api/vector/status", response_model=VectorStatusResponse)
async def vector_status(settings: Settings = Depends(get_settings)) -> VectorStatusResponse:
    return VectorStatusResponse(
        enabled=settings.vector_search_enabled,
        ready=await vector_store_ready(settings),
        backend=settings.vector_index_backend,
        embedding_provider=settings.vector_embedding_provider,
        embedding_dimensions=settings.vector_embedding_dimensions,
        search_limit=settings.vector_search_limit,
        candidate_limit=settings.vector_candidate_limit,
    )


@router.get("/api/models/status", response_model=ModelStatusResponse)
async def model_status(settings: Settings = Depends(get_settings)) -> ModelStatusResponse:
    return ModelStatusResponse(
        llm_provider=settings.llm_provider,
        llm_model=_configured_llm_model(settings),
        embedding_provider=settings.embedding_provider,
        embedding_model=_configured_embedding_model(settings),
        ocr_provider=settings.ocr_provider,
        ocr_model=_configured_ocr_model(settings),
        ocr_enabled=settings.ocr_provider != "none",
        vision_ocr_enabled=settings.ocr_provider in {"openai", "openrouter"},
        external_model_egress=settings.uses_openai_models() or settings.uses_openrouter_models(),
        phi_controls_required=settings.requires_phi_controls(),
        openai_configured=not settings.uses_openai_models() or settings.openai_api_key is not None,
        openrouter_configured=(
            not settings.uses_openrouter_models() or settings.openrouter_api_key is not None
        ),
        openrouter_demo_data_only=settings.openrouter_demo_data_only,
        model_retry_attempts=settings.model_retry_attempts,
    )


@router.get("/api/me", response_model=RequestUser)
async def me(user: Annotated[RequestUser, Depends(get_request_user)]) -> RequestUser:
    return user


@router.get("/api/observability/status", response_model=ObservabilityStatusResponse)
async def observability_status(settings: Settings = Depends(get_settings)) -> ObservabilityStatusResponse:
    return ObservabilityStatusResponse(
        structured_logging_enabled=settings.structured_logging_enabled,
        audit_persistence_required=settings.audit_persistence_required,
        conversation_persistence_enabled=settings.conversation_persistence_enabled,
        vector_search_enabled=settings.vector_search_enabled,
        vector_index_backend=settings.vector_index_backend,
        service_account_enabled=settings.openemr_service_account_enabled,
        nightly_maintenance_enabled=settings.nightly_maintenance_enabled,
        nightly_reindex_enabled=settings.nightly_reindex_enabled,
    )


@router.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def job_status(
    job_id: str,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> JobStatusResponse:
    _require_job_access(user)
    record = await read_job_run(settings, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job was not found")
    return JobStatusResponse(
        job_id=record.job_id,
        job_type=record.job_type,
        status=record.status,
        actor_user_id=record.actor_user_id,
        patient_id_hash=record.patient_id_hash,
        metadata=record.metadata,
        error_code=record.error_code,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


@router.get("/api/capabilities", response_model=CapabilityResponse)
async def capabilities(settings: Settings = Depends(get_settings)) -> CapabilityResponse:
    tool_schemas = _clinical_tool_schemas()
    document_workflow_ready = (
        settings.document_workflow_persistence_enabled
        and await document_workflow_storage_ready(settings)
    )
    return CapabilityResponse(
        roles=[Role.doctor, Role.np_pa, Role.nurse, Role.ma, Role.admin],
        tools=list(tool_schemas),
        tool_schemas=tool_schemas,
        providers={
            "openai_phi_allowed": settings.allow_phi_to_openai,
            "anthropic_phi_allowed": settings.allow_phi_to_anthropic,
            "openrouter_phi_allowed": settings.allow_phi_to_openrouter,
            "local_phi_allowed": settings.allow_phi_to_local,
            "vector_search_enabled": settings.vector_search_enabled,
            "vector_embeddings_external": settings.vector_embedding_provider == "openai",
            "ocr_enabled": settings.ocr_provider != "none",
            "ocr_openai_enabled": settings.ocr_provider == "openai",
            "ocr_openrouter_enabled": settings.ocr_provider == "openrouter",
            "vision_ocr_enabled": settings.ocr_provider in {"openai", "openrouter"},
            "external_model_egress": settings.uses_openai_models()
            or settings.uses_openrouter_models(),
            "openrouter_demo_data_only": settings.openrouter_demo_data_only,
            "vector_index_backend_pgvector": settings.vector_index_backend == "pgvector",
            "evidence_cache_enabled": settings.evidence_cache_enabled,
            "document_workflow_persistence_enabled": settings.document_workflow_persistence_enabled,
            "document_workflow_persistence_ready": document_workflow_ready,
            "openemr_observation_create_supported": await openemr_observation_create_supported(settings),
            "nightly_maintenance_enabled": settings.nightly_maintenance_enabled,
            "nightly_reindex_enabled": settings.nightly_reindex_enabled,
            "service_account_enabled": settings.openemr_service_account_enabled,
            "audit_persistence_required": settings.audit_persistence_required,
            "conversation_persistence_enabled": settings.conversation_persistence_enabled,
        },
        retention_days=settings.conversation_retention_days,
    )


def _clinical_tool_schemas() -> dict[str, ToolContract]:
    patient_id_input = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "patient_id": {
                "type": "string",
                "minLength": 1,
                "description": "OpenEMR FHIR Patient.id for the selected patient.",
            }
        },
        "required": ["patient_id"],
    }
    evidence_output = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "evidence": {
                "type": "array",
                "items": {"$ref": "#/$defs/EvidenceObject"},
            },
            "limitations": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["evidence"],
        "$defs": {
            "EvidenceObject": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "evidence_id": {"type": "string"},
                    "patient_id": {"type": "string"},
                    "source_system": {"type": "string", "const": "openemr"},
                    "source_type": {"type": "string"},
                    "source_id": {"type": "string"},
                    "display_name": {"type": "string"},
                    "fact": {"type": "string"},
                    "source_url": {"type": ["string", "null"]},
                    "metadata": {"type": "object"},
                },
                "required": [
                    "evidence_id",
                    "patient_id",
                    "source_system",
                    "source_type",
                    "source_id",
                    "display_name",
                    "fact",
                ],
            }
        },
    }

    return {
        "patient_search": ToolContract(
            name="patient_search",
            description="Search authorized OpenEMR patients visible to the current user.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {
                        "type": ["string", "null"],
                        "minLength": 2,
                        "maxLength": 100,
                        "description": "Optional name or identifier fragment.",
                    },
                    "count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                    },
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "patients": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "patient_id": {"type": "string"},
                                "display_name": {"type": "string"},
                                "birth_date": {"type": ["string", "null"]},
                                "gender": {"type": ["string", "null"]},
                                "source_system": {"type": "string", "const": "openemr"},
                            },
                            "required": ["patient_id", "display_name", "source_system"],
                        },
                    }
                },
                "required": ["patients"],
            },
        ),
        "get_patient_header": _evidence_tool_contract(
            name="get_patient_header",
            description="Retrieve patient demographics and header context for the selected patient.",
            input_schema=patient_id_input,
            output_schema=evidence_output,
        ),
        "get_active_problems": _evidence_tool_contract(
            name="get_active_problems",
            description="Retrieve active problems and relevant condition history.",
            input_schema=patient_id_input,
            output_schema=evidence_output,
        ),
        "get_recent_labs": _evidence_tool_contract(
            name="get_recent_labs",
            description="Retrieve recent lab observations with source-backed values.",
            input_schema=patient_id_input,
            output_schema=evidence_output,
        ),
        "get_medications": _evidence_tool_contract(
            name="get_medications",
            description="Retrieve active and recent medications from OpenEMR FHIR records.",
            input_schema=patient_id_input,
            output_schema=evidence_output,
        ),
        "get_allergies": _evidence_tool_contract(
            name="get_allergies",
            description="Retrieve allergy and intolerance records for the selected patient.",
            input_schema=patient_id_input,
            output_schema=evidence_output,
        ),
        "get_recent_notes": _evidence_tool_contract(
            name="get_recent_notes",
            description="Retrieve recent unstructured clinical notes exposed through OpenEMR.",
            input_schema=patient_id_input,
            output_schema=evidence_output,
        ),
        "search_patient_evidence": ToolContract(
            name="search_patient_evidence",
            description=(
                "Search the selected patient's indexed source-backed evidence and clinical notes "
                "using the production vector index."
            ),
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "patient_id": {"type": "string", "minLength": 1},
                    "query": {"type": "string", "minLength": 2, "maxLength": 500},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 6},
                },
                "required": ["patient_id", "query"],
            },
            output_schema=evidence_output,
        ),
        "verify_claims": ToolContract(
            name="verify_claims",
            description="Verify answer claims and citations against selected-patient evidence.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "patient_id": {"type": "string", "minLength": 1},
                    "answer": {"type": "string", "minLength": 1},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "evidence_id": {"type": "string"},
                                "label": {"type": "string"},
                                "source_url": {"type": ["string", "null"]},
                            },
                            "required": ["evidence_id", "label"],
                        },
                    },
                },
                "required": ["patient_id", "answer", "citations"],
            },
            output_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "verification": {
                        "type": "string",
                        "enum": ["passed", "failed"],
                    },
                    "errors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["verification", "errors"],
            },
        ),
    }


def _evidence_tool_contract(
    *,
    name: str,
    description: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
) -> ToolContract:
    return ToolContract(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema=output_schema,
    )


@router.get("/api/patients", response_model=list[PatientSummary])
async def patients(
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
    query: str | None = Query(default=None, min_length=2, max_length=100),
    count: int = Query(default=100, ge=1, le=100),
) -> list[PatientSummary]:
    if settings.openemr_fhir_base_url is None:
        return [
            PatientSummary(
                patient_id="demo-diabetes-001",
                display_name="Demo Patient",
                birth_date="1975-04-12",
                gender="female",
            )
        ]

    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    try:
        if query is None:
            return await client.list_patients(count=count)
        return await client.search_patients(query=query, count=min(count, 20))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OpenEMR FHIR access denied",
            ) from exc
        raise HTTPException(status_code=502, detail="OpenEMR patient search failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OpenEMR patient search failed") from exc


@router.get("/api/patients/{patient_id}", response_model=PatientSummary)
async def patient(
    patient_id: str,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> PatientSummary:
    if settings.openemr_fhir_base_url is None:
        if patient_id == "demo-diabetes-001":
            return PatientSummary(
                patient_id="demo-diabetes-001",
                display_name="Demo Patient",
                birth_date="1975-04-12",
                gender="female",
            )
        return PatientSummary(
            patient_id=patient_id,
            display_name="Selected OpenEMR patient",
            birth_date=None,
            gender=None,
        )

    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    try:
        return await client.get_patient_summary(patient_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OpenEMR FHIR access denied",
            ) from exc
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="OpenEMR patient was not found") from exc
        raise HTTPException(status_code=502, detail="OpenEMR patient retrieval failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OpenEMR patient retrieval failed") from exc


@router.post("/api/patients/{patient_id}/reindex", response_model=ReindexResponse)
async def reindex_patient(
    patient_id: str,
    request: ReindexRequest,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> ReindexResponse:
    _require_reindex_access(user)
    if not settings.openemr_service_account_enabled:
        raise HTTPException(
            status_code=503,
            detail="OpenEMR service account is not configured for backend reindex",
        )
    if not settings.vector_search_enabled:
        raise HTTPException(status_code=503, detail="Vector search is not enabled")
    try:
        result = await run_patient_reindex(
            settings=settings,
            patient_id=patient_id,
            actor_user_id=user.user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Patient reindex failed") from exc
    return ReindexResponse(
        job_id=str(result["job_id"]),
        status="succeeded",
        patient_id=patient_id,
        indexed_evidence_count=int(result["indexed_evidence_count"]),
    )


@router.get("/api/source/openemr/{resource_type}/{resource_id}")
async def openemr_source(
    resource_type: str,
    resource_id: str,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
    patient_id: str | None = Query(default=None, min_length=1, max_length=100),
) -> dict[str, Any]:
    allowed_resource_types = {
        "Patient",
        "Condition",
        "Observation",
        "MedicationRequest",
        "AllergyIntolerance",
        "DocumentReference",
    }
    if resource_type not in allowed_resource_types:
        raise HTTPException(status_code=400, detail="Unsupported OpenEMR source resource type")
    if settings.openemr_fhir_base_url is None:
        raise HTTPException(status_code=404, detail="OpenEMR FHIR is not configured")
    source_patient_id = patient_id if patient_id is not None else resource_id if resource_type == "Patient" else None
    if source_patient_id is None:
        raise HTTPException(
            status_code=422,
            detail="patient_id is required for patient-scoped OpenEMR source resources",
        )

    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    try:
        source = await client.read_resource(resource_type, resource_id)
        if not _resource_belongs_to_patient(source, source_patient_id):
            raise HTTPException(status_code=404, detail="OpenEMR source was not found")
        await _write_source_audit(
            settings=settings,
            user=user,
            patient_id=source_patient_id,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome="success",
        )
        return source
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OpenEMR FHIR access denied",
            ) from exc
        if exc.response.status_code == 404:
            fallback_source = await _search_source_by_id(
                client, resource_type, resource_id, source_patient_id
            )
            if fallback_source is not None:
                await _write_source_audit(
                    settings=settings,
                    user=user,
                    patient_id=source_patient_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    outcome="success",
                )
                return fallback_source
            raise HTTPException(status_code=404, detail="OpenEMR source was not found") from exc
        raise HTTPException(status_code=502, detail="OpenEMR source retrieval failed") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OpenEMR source retrieval failed") from exc


async def _search_source_by_id(
    client: OpenEMRFhirClient,
    resource_type: str,
    resource_id: str,
    patient_id: str,
) -> dict[str, Any] | None:
    bundle = await client.search_bundle(resource_type, {"_id": resource_id, "_count": "1"})
    source = _resource_from_bundle(bundle, resource_type, resource_id, patient_id)
    if source is not None:
        return source

    if resource_type == "Patient":
        return None

    bundle = await client.search_bundle(resource_type, {"patient": patient_id, "_count": "100"})
    return _resource_from_bundle(bundle, resource_type, resource_id, patient_id)


def _resource_from_bundle(
    bundle: dict[str, Any],
    resource_type: str,
    resource_id: str,
    patient_id: str,
) -> dict[str, Any] | None:
    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if (
            isinstance(resource, dict)
            and resource.get("resourceType") == resource_type
            and resource.get("id") == resource_id
            and _resource_belongs_to_patient(resource, patient_id)
        ):
            return resource
    return None


def _resource_belongs_to_patient(resource: dict[str, Any], patient_id: str) -> bool:
    if resource.get("resourceType") == "Patient":
        return resource.get("id") == patient_id

    subject = resource.get("subject")
    if isinstance(subject, dict) and subject.get("reference") == f"Patient/{patient_id}":
        return True

    patient = resource.get("patient")
    if isinstance(patient, dict) and patient.get("reference") == f"Patient/{patient_id}":
        return True

    return False


async def _write_source_audit(
    *,
    settings: Settings,
    user: RequestUser,
    patient_id: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
) -> None:
    if not _persistent_phi_storage_configured(settings):
        return
    await write_audit_event(
        settings,
        build_audit_event(
            settings=settings,
            actor_user_id=user.user_id,
            action="source_read",
            outcome=outcome,
            patient_id=patient_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_payload={"resource_type": resource_type},
        ),
    )


@router.get("/api/source/demo-lab-a1c")
async def demo_source() -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": "demo-lab-a1c",
        "status": "final",
        "code": {"text": "Demo A1c"},
        "valueQuantity": {"value": 8.6, "unit": "%"},
        "effectiveDateTime": "2026-03-12",
    }


@router.post("/api/chat")
async def chat(
    request: ChatRequest,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    return StreamingResponse(
        _chat_events(request=request, user=user, settings=settings),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


async def _chat_events(request: ChatRequest, user: RequestUser, settings: Settings) -> AsyncIterator[str]:
    started_at = datetime.now(tz=UTC)
    yield _sse("status", {"message": "checking access", "role": user.role})

    # The MVP is deliberately read-only. Treatment-plan or medication-change
    # requests are refused before any retrieval or model call can happen.
    if _is_treatment_advice_request(request.message):
        yield _sse("status", {"message": "enforcing read-only MVP policy"})
        payload = {
            "answer": (
                "I can't recommend medication changes, diagnoses, orders, or treatment plans "
                "in this MVP. I can show source-backed current medications, allergies, active "
                "problems, and recent labs to support clinician review."
            ),
            "citations": [],
            "audit": {
                "verification": "refused_treatment_recommendation",
                "policy": "read_only_clinical_information",
                "patient_id": request.patient_id,
            },
        }
        payload = await _persist_and_annotate_chat_payload(
            settings=settings,
            user=user,
            request=request,
            payload=payload,
            started_at=started_at,
            evidence_count=0,
        )
        yield _sse(
            "final",
            payload,
        )
        return

    yield _sse("status", {"message": "retrieving evidence", "patient_id": request.patient_id})

    try:
        # Evidence retrieval is the boundary between OpenEMR truth and Co-Pilot
        # derived read models. The model never chooses the patient or source ids.
        retrieval = await _retrieve_evidence(request=request, user=user, settings=settings)
    except HTTPException as exc:
        payload = {
            "answer": "I could not retrieve source-backed OpenEMR evidence for this patient.",
            "citations": [],
            "audit": {
                "verification": "failed",
                "error": "fhir_access_failed",
                "status_code": exc.status_code,
                "detail": exc.detail,
            },
        }
        payload = await _persist_and_annotate_chat_payload(
            settings=settings,
            user=user,
            request=request,
            payload=payload,
            started_at=started_at,
            evidence_count=0,
        )
        yield _sse(
            "final",
            payload,
        )
        return
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        error = "fhir_access_denied" if status_code in {401, 403} else "fhir_retrieval_failed"
        payload = {
            "answer": "I could not retrieve source-backed OpenEMR evidence for this patient.",
            "citations": [],
            "audit": {
                "verification": "failed",
                "error": error,
                "status_code": status_code,
            },
        }
        payload = await _persist_and_annotate_chat_payload(
            settings=settings,
            user=user,
            request=request,
            payload=payload,
            started_at=started_at,
            evidence_count=0,
        )
        yield _sse(
            "final",
            payload,
        )
        return
    except VectorStoreError as exc:
        payload = {
            "answer": "I could not search the source-backed vector index for this patient.",
            "citations": [],
            "audit": {
                "verification": "failed",
                "error": "vector_store_failed",
                "detail": str(exc),
            },
        }
        payload = await _persist_and_annotate_chat_payload(
            settings=settings,
            user=user,
            request=request,
            payload=payload,
            started_at=started_at,
            evidence_count=0,
        )
        yield _sse(
            "final",
            payload,
        )
        return
    except Exception as exc:
        payload = {
            "answer": "I could not retrieve source-backed OpenEMR evidence for this patient.",
            "citations": [],
            "audit": {
                "verification": "failed",
                "error": "fhir_retrieval_failed",
                "detail": str(exc),
            },
        }
        payload = await _persist_and_annotate_chat_payload(
            settings=settings,
            user=user,
            request=request,
            payload=payload,
            started_at=started_at,
            evidence_count=0,
        )
        yield _sse(
            "final",
            payload,
        )
        return

    yield _sse(
        "status",
        {
            "message": "preparing model context",
            "evidence_count": len(retrieval.evidence),
            "tools": retrieval.tools,
        },
    )

    if settings.embedding_provider == "openai":
        yield _sse("status", {"message": "ranking evidence with embeddings"})
        try:
            ranked_evidence = await OpenAIEmbeddingAdapter(settings).rank_evidence(
                message=request.message,
                evidence=retrieval.evidence,
                limit=settings.model_evidence_limit,
            )
        except OpenAIModelError as exc:
            payload = {
                "answer": "I could not rank the source-backed evidence for this patient.",
                "citations": [],
                "audit": {
                    "verification": "failed",
                    "error": "embedding_provider_failed",
                    "detail": str(exc),
                },
            }
            payload = await _persist_and_annotate_chat_payload(
                settings=settings,
                user=user,
                request=request,
                payload=payload,
                started_at=started_at,
                evidence_count=len(retrieval.evidence),
            )
            yield _sse(
                "final",
                payload,
            )
            return
        retrieval = EvidenceRetrievalResult(
            evidence=ranked_evidence,
            tools=[*retrieval.tools, "openai_embedding_rank"],
            limitations=retrieval.limitations,
        )

    provider = _provider_for_settings(settings)
    try:
        # Provider output is treated as a draft. It must survive schema/citation
        # parsing and the verifier below before the UI sees it.
        answer = await provider.answer(
            patient_id=request.patient_id,
            user_message=request.message,
            evidence=retrieval.evidence,
        )
    except OpenAIModelError as exc:
        yield _sse("status", {"message": "model output failed validation; using source-backed fallback"})
        answer = await MockProviderAdapter().answer(
            patient_id=request.patient_id,
            user_message=request.message,
            evidence=retrieval.evidence,
        )
        answer.audit["provider"] = "source_backed_fallback"
        answer.audit["llm_provider_failed"] = settings.llm_provider
        answer.audit["llm_error"] = str(exc)
        answer.audit["reasoning_summary"] = (
            "The model response was unavailable or failed schema/citation validation, so the "
            "response was generated from retrieved source evidence and re-verified."
        )

    answer.audit["tools"] = retrieval.tools
    answer.audit["limitations"] = retrieval.limitations
    answer.audit["agent_loop"] = {
        "mode": "bounded_server_orchestrated",
        "max_steps": settings.agent_loop_max_steps,
        "steps": [
            "check_access",
            *retrieval.tools,
            f"provider:{answer.audit.get('provider', settings.llm_provider)}",
            "verify_claims",
        ][: settings.agent_loop_max_steps],
    }

    try:
        # Final safety gate: every factual claim must cite selected-patient
        # evidence. Failure becomes a refusal, not a partially trusted answer.
        verify_answer(answer, retrieval.evidence, request.patient_id)
    except VerificationError as exc:
        payload = {
            "answer": (
                "I could not verify the answer against selected-patient evidence, "
                "so I am not showing it."
            ),
            "citations": [],
            "audit": {"verification": "failed", "reason": str(exc)},
        }
        payload = await _persist_and_annotate_chat_payload(
            settings=settings,
            user=user,
            request=request,
            payload=payload,
            started_at=started_at,
            evidence_count=len(retrieval.evidence),
        )
        yield _sse(
            "final",
            payload,
        )
        return

    answer.audit["verification"] = "passed"
    payload = await _persist_and_annotate_chat_payload(
        settings=settings,
        user=user,
        request=request,
        payload=answer.model_dump(mode="json"),
        started_at=started_at,
        evidence_count=len(retrieval.evidence),
    )
    yield _sse("final", payload)


async def _persist_and_annotate_chat_payload(
    *,
    settings: Settings,
    user: RequestUser,
    request: ChatRequest,
    payload: dict[str, Any],
    started_at: datetime,
    evidence_count: int,
) -> dict[str, Any]:
    audit = payload.setdefault("audit", {})
    if not isinstance(audit, dict):
        audit = {}
        payload["audit"] = audit

    duration_ms = max(int((datetime.now(tz=UTC) - started_at).total_seconds() * 1000), 0)
    outcome = _chat_audit_outcome(audit)
    metadata = {
        "outcome": outcome,
        "verification": str(audit.get("verification") or "unknown"),
        "provider": str(audit.get("provider") or "unknown"),
        "tool_count": len(audit.get("tools", [])) if isinstance(audit.get("tools"), list) else 0,
        "citation_count": len(payload.get("citations", []))
        if isinstance(payload.get("citations"), list)
        else 0,
        "evidence_count": evidence_count,
        "duration_ms": duration_ms,
    }
    emit_telemetry_event(settings, event="chat_completed", metadata=metadata)

    if not _persistent_phi_storage_configured(settings):
        audit["persistence"] = "skipped"
        return payload

    try:
        # Conversation rows are useful product memory, but audit is the safety
        # dependency. In PHI mode, audit persistence failure withholds the answer.
        if settings.conversation_persistence_enabled:
            conversation_id = await append_chat_messages(
                settings=settings,
                actor_user_id=user.user_id,
                patient_id=request.patient_id,
                user_message=request.message,
                assistant_payload=payload,
                conversation_id=request.conversation_id,
            )
            payload["conversation_id"] = conversation_id
            audit["conversation_persistence"] = "written"

        await write_audit_event(
            settings,
            build_audit_event(
                settings=settings,
                actor_user_id=user.user_id,
                action="chat_completion",
                outcome=outcome,
                patient_id=request.patient_id,
                reason_code=str(audit.get("error") or audit.get("verification") or outcome),
                metadata_payload=metadata,
            ),
        )
        audit["audit_persistence"] = "written"
    except Exception as exc:
        audit["persistence"] = "failed"
        audit["persistence_error"] = exc.__class__.__name__
        emit_telemetry_event(
            settings,
            event="chat_persistence_failed",
            metadata={"error_class": exc.__class__.__name__},
        )
        if settings.requires_phi_controls() and settings.audit_persistence_required:
            return {
                "answer": (
                    "I could not complete this request because the clinical audit store is "
                    "unavailable. No verified answer is shown."
                ),
                "citations": [],
                "audit": {
                    "verification": "failed",
                    "error": "audit_persistence_failed",
                    "persistence_error": exc.__class__.__name__,
                },
            }
    return payload


def _persistent_phi_storage_configured(settings: Settings) -> bool:
    return settings.database_url is not None and settings.encryption_key is not None


def _chat_audit_outcome(audit: dict[str, Any]) -> str:
    verification = audit.get("verification")
    if verification == "passed":
        return "success"
    if verification == "refused_treatment_recommendation":
        return "refused"
    return "failure"


async def _retrieve_evidence(
    *,
    request: ChatRequest,
    user: RequestUser,
    settings: Settings,
) -> EvidenceRetrievalResult:
    if settings.openemr_fhir_base_url is None:
        # Local/demo mode can answer from deterministic fixtures. Production PHI
        # mode requires OpenEMR FHIR, enforced by Settings.runtime_config_errors().
        document_evidence = await _approved_document_evidence(settings, request.patient_id)
        retrieval = EvidenceRetrievalResult(
            evidence=_merge_evidence(_demo_evidence(request.patient_id), document_evidence),
            tools=_merge_strings(
                ["demo_evidence"],
                ["approved_document_evidence"] if document_evidence else [],
            ),
            limitations=["OPENEMR_FHIR_BASE_URL is not configured; demo evidence was used."],
        )
        retrieval = _augment_with_guideline_evidence(
            patient_id=request.patient_id,
            message=request.message,
            retrieval=retrieval,
        )
        if settings.vector_search_enabled:
            return await _augment_with_vector_search_with_failover(
                settings=settings,
                patient_id=request.patient_id,
                message=request.message,
                retrieval=retrieval,
                service=None,
            )
        return retrieval

    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    service = FhirEvidenceService(client)
    # Structured FHIR evidence is collected before vector search so common
    # factual questions do not need semantic search or a larger model context.
    retrieval = await _collect_evidence_with_cache(
        settings=settings,
        user=user,
        patient_id=request.patient_id,
        message=request.message,
        quick_question_id=request.quick_question_id,
        service=service,
    )
    document_evidence = await _approved_document_evidence(settings, request.patient_id)
    if document_evidence:
        retrieval = EvidenceRetrievalResult(
            evidence=_merge_evidence(retrieval.evidence, document_evidence),
            tools=_merge_strings(retrieval.tools, ["approved_document_evidence"]),
            limitations=retrieval.limitations,
        )
    retrieval = _augment_with_guideline_evidence(
        patient_id=request.patient_id,
        message=request.message,
        retrieval=retrieval,
    )
    if settings.vector_search_enabled:
        return await _augment_with_vector_search_with_failover(
            settings=settings,
            patient_id=request.patient_id,
            message=request.message,
            retrieval=retrieval,
            service=service,
        )
    return retrieval


async def _approved_document_evidence(settings: Settings, patient_id: str) -> list[EvidenceObject]:
    memory_evidence = approved_document_evidence(patient_id)
    if not document_workflow_persistence_configured(settings):
        return memory_evidence
    persisted_evidence = await read_approved_document_evidence(settings, patient_id)
    return _merge_evidence(memory_evidence, persisted_evidence)


def _augment_with_guideline_evidence(
    *,
    patient_id: str,
    message: str,
    retrieval: EvidenceRetrievalResult,
) -> EvidenceRetrievalResult:
    document_facts = [
        item.fact
        for item in retrieval.evidence
        if item.metadata.get("schema") == "w2_document_fact_v1"
    ]
    question_mentions_guidelines = any(
        token in message.lower()
        for token in [
            "guideline",
            "diabetes",
            "a1c",
            "lipid",
            "ldl",
            "hypertension",
            "blood pressure",
            "pay attention",
            "changed",
        ]
    )
    if not document_facts and not question_mentions_guidelines:
        return retrieval

    hits = retrieve_guideline_chunks(
        question=message,
        patient_facts=[],
        extracted_facts=document_facts,
        limit=3,
    )
    if not hits:
        return retrieval
    return EvidenceRetrievalResult(
        evidence=_merge_evidence(
            retrieval.evidence,
            guideline_hits_to_evidence(patient_id=patient_id, hits=hits),
        ),
        tools=_merge_strings(retrieval.tools, ["guideline_rag"]),
        limitations=retrieval.limitations,
    )


async def _augment_with_vector_search_with_failover(
    *,
    settings: Settings,
    patient_id: str,
    message: str,
    retrieval: EvidenceRetrievalResult,
    service: FhirEvidenceService | None,
) -> EvidenceRetrievalResult:
    try:
        return await _augment_with_vector_search(
            settings=settings,
            patient_id=patient_id,
            message=message,
            retrieval=retrieval,
            service=service,
        )
    except (VectorStoreError, httpx.HTTPError) as exc:
        # Vector search is a derived projection. If it is unavailable, keep the
        # live OpenEMR evidence path alive and surface the limitation in audit.
        emit_telemetry_event(
            settings,
            event="vector_search_degraded",
            metadata={"error_class": exc.__class__.__name__},
        )
        return EvidenceRetrievalResult(
            evidence=retrieval.evidence,
            tools=_merge_strings(retrieval.tools, ["vector_search_unavailable"]),
            limitations=_merge_strings(
                retrieval.limitations,
                [
                    (
                        "Vector search was unavailable, so the answer used live "
                        "OpenEMR FHIR evidence already retrieved for this question."
                    )
                ],
            ),
        )


async def _collect_evidence_with_cache(
    *,
    settings: Settings,
    user: RequestUser,
    patient_id: str,
    message: str,
    quick_question_id: str | None,
    service: FhirEvidenceService,
) -> EvidenceRetrievalResult:
    if not _evidence_cache_configured(settings):
        return await service.collect_for_question(
            patient_id=patient_id,
            message=message,
            quick_question_id=quick_question_id,
        )

    # Cache key includes actor, role, scopes, patient, and normalized question.
    # That prevents one clinician/context from reusing another context's evidence.
    cache_key = _evidence_cache_key(
        user=user,
        patient_id=patient_id,
        message=message,
        quick_question_id=quick_question_id,
    )
    try:
        cached = await read_evidence_cache_record(
            settings=settings,
            patient_id=patient_id,
            cache_key=cache_key,
        )
    except Exception as exc:
        cached = None
        emit_telemetry_event(
            settings,
            event="evidence_cache_read_failed",
            metadata={"error_class": exc.__class__.__name__},
        )
    if cached is not None:
        try:
            retrieval = _retrieval_from_cache_payload(cached.payload)
            return EvidenceRetrievalResult(
                evidence=retrieval.evidence,
                tools=_merge_strings(retrieval.tools, ["evidence_cache_hit"]),
                limitations=retrieval.limitations,
            )
        except ValueError:
            pass

    retrieval = await service.collect_for_question(
        patient_id=patient_id,
        message=message,
        quick_question_id=quick_question_id,
    )
    record = build_evidence_cache_record(
        settings=settings,
        patient_id=patient_id,
        cache_key=cache_key,
        payload=_retrieval_cache_payload(retrieval),
        ttl_seconds=settings.evidence_cache_ttl_seconds,
    )
    try:
        await write_evidence_cache_record(settings, record)
    except Exception as exc:
        emit_telemetry_event(
            settings,
            event="evidence_cache_write_failed",
            metadata={"error_class": exc.__class__.__name__},
        )
        return EvidenceRetrievalResult(
            evidence=retrieval.evidence,
            tools=_merge_strings(retrieval.tools, ["evidence_cache_unavailable"]),
            limitations=_merge_strings(
                retrieval.limitations,
                ["Evidence cache was unavailable; live OpenEMR FHIR evidence was used."],
            ),
        )
    return EvidenceRetrievalResult(
        evidence=retrieval.evidence,
        tools=_merge_strings(retrieval.tools, ["evidence_cache_write"]),
        limitations=retrieval.limitations,
    )


async def _augment_with_vector_search(
    *,
    settings: Settings,
    patient_id: str,
    message: str,
    retrieval: EvidenceRetrievalResult,
    service: FhirEvidenceService | None,
) -> EvidenceRetrievalResult:
    try:
        # Search existing patient-scoped vectors first. If the index is warm,
        # this avoids re-embedding the same source evidence on every turn.
        existing_vector_evidence = await search_patient_evidence(
            settings=settings,
            patient_id=patient_id,
            query=message,
        )
    except VectorStoreError:
        existing_vector_evidence = []
    if existing_vector_evidence:
        if service is not None:
            hydrated = await service.hydrate_vector_hits(existing_vector_evidence)
            existing_vector_evidence = hydrated.evidence
            limitations = _merge_strings(retrieval.limitations, hydrated.limitations)
            hydration_tools = hydrated.tools
        else:
            limitations = list(retrieval.limitations)
            hydration_tools = []
        return EvidenceRetrievalResult(
            evidence=_merge_evidence(retrieval.evidence, existing_vector_evidence),
            tools=_merge_strings(
                retrieval.tools,
                ["search_patient_evidence", *hydration_tools],
            ),
            limitations=limitations,
        )

    index_evidence = retrieval.evidence
    limitations = list(retrieval.limitations)
    if service is not None:
        # Cold index path: collect a broader selected-patient evidence set, write
        # the derived vector rows, then search the projection.
        seed_retrieval = await service.collect_patient_index_evidence(patient_id)
        index_evidence = _merge_evidence(retrieval.evidence, seed_retrieval.evidence)
        limitations = _merge_strings(limitations, seed_retrieval.limitations)

    vector_evidence = await index_and_search_evidence(
        settings=settings,
        patient_id=patient_id,
        query=message,
        evidence=index_evidence,
    )
    cold_hydration_tools: list[str] = []
    if service is not None and vector_evidence:
        cold_hydrated = await service.hydrate_vector_hits(vector_evidence)
        vector_evidence = cold_hydrated.evidence
        limitations = _merge_strings(limitations, cold_hydrated.limitations)
        cold_hydration_tools = cold_hydrated.tools
    return EvidenceRetrievalResult(
        evidence=_merge_evidence(retrieval.evidence, vector_evidence),
        tools=_merge_strings(
            retrieval.tools,
            ["index_patient_evidence", "search_patient_evidence", *cold_hydration_tools],
        ),
        limitations=limitations,
    )


def _evidence_cache_configured(settings: Settings) -> bool:
    return (
        settings.evidence_cache_enabled
        and settings.database_url is not None
        and settings.encryption_key is not None
    )


def _evidence_cache_key(
    *,
    user: RequestUser,
    patient_id: str,
    message: str,
    quick_question_id: str | None,
) -> str:
    return json.dumps(
        {
            "version": "evidence_retrieval_v1",
            "user_id": user.user_id,
            "role": user.role,
            "scopes": sorted(user.scopes),
            "patient_id": patient_id,
            "message": " ".join(message.lower().split()),
            "quick_question_id": quick_question_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _retrieval_cache_payload(retrieval: EvidenceRetrievalResult) -> dict[str, Any]:
    return {
        "schema": "evidence_retrieval_v1",
        "evidence": [item.model_dump(mode="json") for item in retrieval.evidence],
        "tools": retrieval.tools,
        "limitations": retrieval.limitations,
    }


def _retrieval_from_cache_payload(payload: dict[str, Any]) -> EvidenceRetrievalResult:
    if payload.get("schema") != "evidence_retrieval_v1":
        raise ValueError("Unsupported evidence cache payload schema")
    evidence_items = payload.get("evidence")
    tools = payload.get("tools")
    limitations = payload.get("limitations")
    if not isinstance(evidence_items, list) or not isinstance(tools, list):
        raise ValueError("Evidence cache payload was invalid")
    if limitations is None:
        limitations = []
    if not isinstance(limitations, list):
        raise ValueError("Evidence cache payload limitations were invalid")
    return EvidenceRetrievalResult(
        evidence=[EvidenceObject.model_validate(item) for item in evidence_items],
        tools=[str(item) for item in tools],
        limitations=[str(item) for item in limitations],
    )


def _merge_evidence(
    primary: list[EvidenceObject],
    secondary: list[EvidenceObject],
) -> list[EvidenceObject]:
    merged: list[EvidenceObject] = []
    seen: set[str] = set()
    for item in [*primary, *secondary]:
        if item.evidence_id in seen:
            continue
        merged.append(item)
        seen.add(item.evidence_id)
    return merged


def _merge_strings(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*primary, *secondary]:
        if item in seen:
            continue
        merged.append(item)
        seen.add(item)
    return merged


def _provider_for_settings(settings: Settings) -> ProviderAdapter:
    if settings.llm_provider == "mock":
        return MockProviderAdapter()
    if settings.llm_provider == "openai":
        return OpenAIProviderAdapter(settings)
    if settings.llm_provider == "openrouter":
        return OpenRouterProviderAdapter(settings)
    raise OpenAIModelError(f"Unsupported LLM provider: {settings.llm_provider}")


def _configured_llm_model(settings: Settings) -> str | None:
    if settings.llm_provider == "openai":
        return settings.openai_llm_model
    if settings.llm_provider == "openrouter":
        return settings.openrouter_llm_model
    return None


def _configured_embedding_model(settings: Settings) -> str | None:
    if settings.embedding_provider == "openai":
        return settings.openai_embedding_model
    return None


def _configured_ocr_model(settings: Settings) -> str | None:
    if settings.ocr_provider == "openai":
        return settings.openai_ocr_model
    if settings.ocr_provider == "openrouter":
        return settings.openrouter_ocr_model
    return None


def _require_reindex_access(user: RequestUser) -> None:
    if user.role not in {Role.doctor, Role.np_pa, Role.admin}:
        raise HTTPException(status_code=403, detail="Role is not allowed to reindex patient evidence")


def _require_job_access(user: RequestUser) -> None:
    if user.role not in {Role.doctor, Role.np_pa, Role.admin}:
        raise HTTPException(status_code=403, detail="Role is not allowed to inspect job status")


def _demo_evidence(patient_id: str) -> list[EvidenceObject]:
    now = datetime.now(tz=UTC)
    return [
        EvidenceObject(
            evidence_id="ev_demo_a1c",
            patient_id=patient_id,
            source_type="lab_result",
            source_id="demo-lab-a1c",
            display_name="Demo A1c",
            fact="Demo A1c was 8.6% on 2026-03-12",
            effective_at=datetime(2026, 3, 12, tzinfo=UTC),
            source_updated_at=datetime(2026, 3, 12, tzinfo=UTC),
            retrieved_at=now,
            source_url="/api/source/demo-lab-a1c",
        )
    ]


def _is_treatment_advice_request(message: str) -> bool:
    text = message.lower()
    direct_terms = [
        "should i",
        "should we",
        "recommend",
        "prescribe",
        "order",
        "diagnose",
        "treat",
        "treatment plan",
        "medication changes",
        "med changes",
        "change medication",
        "adjust medication",
        "adjust dose",
        "increase dose",
        "decrease dose",
        "stop medication",
        "start medication",
    ]
    clinical_terms = [
        "medication",
        "medicine",
        "meds",
        "dose",
        "dosage",
        "treatment",
        "therapy",
        "plan",
        "diagnosis",
        "lab",
    ]
    return any(term in text for term in direct_terms) and any(term in text for term in clinical_terms)


def _sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
