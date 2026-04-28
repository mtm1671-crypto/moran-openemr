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
from app.evidence_tools import EvidenceRetrievalResult, FhirEvidenceService
from app.fhir_client import OpenEMRFhirClient
from app.models import (
    CapabilityResponse,
    ChatRequest,
    EvidenceObject,
    PatientSummary,
    RequestUser,
    Role,
)
from app.openemr_auth import resolve_fhir_bearer_token
from app.providers import MockProviderAdapter
from app.verifier import VerificationError, verify_answer

router = APIRouter()


class HealthResponse(BaseModel):
    ok: bool
    service: str
    environment: str


@router.get("/healthz", response_model=HealthResponse)
async def healthz(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(ok=True, service="clinical-copilot-api", environment=settings.app_env)


@router.get("/api/me", response_model=RequestUser)
async def me(user: Annotated[RequestUser, Depends(get_request_user)]) -> RequestUser:
    return user


@router.get("/api/capabilities", response_model=CapabilityResponse)
async def capabilities(settings: Settings = Depends(get_settings)) -> CapabilityResponse:
    return CapabilityResponse(
        roles=[Role.doctor, Role.np_pa, Role.nurse, Role.ma, Role.admin],
        tools=[
            "patient_search",
            "get_patient_header",
            "get_active_problems",
            "get_recent_labs",
            "get_medications",
            "get_allergies",
            "verify_claims",
        ],
        providers={
            "anthropic_phi_allowed": settings.allow_phi_to_anthropic,
            "openrouter_phi_allowed": settings.allow_phi_to_openrouter,
            "local_phi_allowed": settings.allow_phi_to_local,
        },
        retention_days=settings.conversation_retention_days,
    )


@router.get("/api/patients", response_model=list[PatientSummary])
async def patients(
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
    query: str = Query(min_length=2, max_length=100),
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
        return await client.search_patients(query=query, count=20)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OpenEMR FHIR access denied",
            ) from exc
        raise HTTPException(status_code=502, detail="OpenEMR patient search failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OpenEMR patient search failed") from exc


@router.get("/api/source/openemr/{resource_type}/{resource_id}")
async def openemr_source(
    resource_type: str,
    resource_id: str,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
    patient_id: str | None = Query(default=None, min_length=1, max_length=100),
) -> dict[str, Any]:
    allowed_resource_types = {"Patient", "Condition", "Observation"}
    if resource_type not in allowed_resource_types:
        raise HTTPException(status_code=400, detail="Unsupported OpenEMR source resource type")
    if settings.openemr_fhir_base_url is None:
        raise HTTPException(status_code=404, detail="OpenEMR FHIR is not configured")

    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    try:
        source = await client.read_resource(resource_type, resource_id)
        if patient_id is not None and not _resource_belongs_to_patient(source, patient_id):
            raise HTTPException(status_code=404, detail="OpenEMR source was not found")
        return source
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OpenEMR FHIR access denied",
            ) from exc
        if exc.response.status_code == 404:
            fallback_source = await _search_source_by_id(client, resource_type, resource_id, patient_id)
            if fallback_source is not None:
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
    patient_id: str | None,
) -> dict[str, Any] | None:
    bundle = await client.search_bundle(resource_type, {"_id": resource_id, "_count": "1"})
    source = _resource_from_bundle(bundle, resource_type, resource_id, patient_id)
    if source is not None:
        return source

    if patient_id is None or resource_type == "Patient":
        return None

    bundle = await client.search_bundle(resource_type, {"patient": patient_id, "_count": "100"})
    return _resource_from_bundle(bundle, resource_type, resource_id, patient_id)


def _resource_from_bundle(
    bundle: dict[str, Any],
    resource_type: str,
    resource_id: str,
    patient_id: str | None,
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
            and (patient_id is None or _resource_belongs_to_patient(resource, patient_id))
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
    yield _sse("status", {"message": "checking access", "role": user.role})
    yield _sse("status", {"message": "retrieving evidence", "patient_id": request.patient_id})

    try:
        retrieval = await _retrieve_evidence(request=request, user=user, settings=settings)
    except HTTPException as exc:
        yield _sse(
            "final",
            {
                "answer": "I could not retrieve source-backed OpenEMR evidence for this patient.",
                "citations": [],
                "audit": {
                    "verification": "failed",
                    "error": "fhir_access_failed",
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            },
        )
        return
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        error = "fhir_access_denied" if status_code in {401, 403} else "fhir_retrieval_failed"
        yield _sse(
            "final",
            {
                "answer": "I could not retrieve source-backed OpenEMR evidence for this patient.",
                "citations": [],
                "audit": {
                    "verification": "failed",
                    "error": error,
                    "status_code": status_code,
                },
            },
        )
        return
    except Exception as exc:
        yield _sse(
            "final",
            {
                "answer": "I could not retrieve source-backed OpenEMR evidence for this patient.",
                "citations": [],
                "audit": {
                    "verification": "failed",
                    "error": "fhir_retrieval_failed",
                    "detail": str(exc),
                },
            },
        )
        return

    yield _sse(
        "status",
        {
            "message": "verifying sources",
            "evidence_count": len(retrieval.evidence),
            "tools": retrieval.tools,
        },
    )

    provider = MockProviderAdapter()
    answer = await provider.answer(
        patient_id=request.patient_id,
        user_message=request.message,
        evidence=retrieval.evidence,
    )
    answer.audit["tools"] = retrieval.tools
    answer.audit["limitations"] = retrieval.limitations

    try:
        verify_answer(answer, retrieval.evidence, request.patient_id)
    except VerificationError as exc:
        yield _sse(
            "final",
            {
                "answer": (
                    "I could not verify the answer against selected-patient evidence, "
                    "so I am not showing it."
                ),
                "citations": [],
                "audit": {"verification": "failed", "reason": str(exc)},
            },
        )
        return

    answer.audit["verification"] = "passed"
    yield _sse("final", answer.model_dump(mode="json"))


async def _retrieve_evidence(
    *,
    request: ChatRequest,
    user: RequestUser,
    settings: Settings,
) -> EvidenceRetrievalResult:
    if settings.openemr_fhir_base_url is None:
        return EvidenceRetrievalResult(
            evidence=_demo_evidence(request.patient_id),
            tools=["demo_evidence"],
            limitations=["OPENEMR_FHIR_BASE_URL is not configured; demo evidence was used."],
        )

    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    service = FhirEvidenceService(client)
    return await service.collect_for_question(
        patient_id=request.patient_id,
        message=request.message,
        quick_question_id=request.quick_question_id,
    )


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


def _sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
