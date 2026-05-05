from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_request_user
from app.config import Settings, get_settings
from app.document_models import (
    DocumentAttachExtractRequest,
    DocumentJobRecord,
    DocumentJobResponse,
    DocumentReviewPayload,
    DocumentReviewResult,
    DocumentWriteResult,
    ExtractedFact,
    ReviewDecisionsRequest,
    W2FactStatus,
    W2JobStatus,
    W2ProposedDestination,
    now_utc,
)
from app.document_storage import (
    approved_document_evidence,
    begin_document_write,
    create_document_workflow,
    fact_counts,
    read_document_facts,
    read_document_source,
    require_document_job,
    replace_document_facts,
    update_document_fact,
    update_document_job,
)
from app.extraction_adapters import ExtractionError
from app.fhir_client import OpenEMRFhirClient
from app.extraction_pipeline import extract_document_facts_async
from app.models import RequestUser, Role
from app.observation_writer import ObservationWriteError, write_lab_fact_observation
from app.ocr_layout import LayoutExtractionError
from app.openemr_auth import resolve_fhir_bearer_token
from app.telemetry import emit_telemetry_event

router = APIRouter(prefix="/api/documents", tags=["week2-documents"])


@router.post(
    "/attach-and-extract",
    response_model=DocumentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def attach_and_extract(
    request: DocumentAttachExtractRequest,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> DocumentJobResponse:
    _require_document_access(user)
    await _require_patient_access(user=user, patient_id=request.patient_id, settings=settings)
    try:
        content = request.decoded_content()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job, source, was_created = create_document_workflow(
        patient_id=request.patient_id,
        doc_type=request.doc_type,
        filename=request.filename,
        content_type=request.content_type,
        content=content,
        actor_user_id=user.user_id,
    )
    if not was_created or job.status in {W2JobStatus.review_required, W2JobStatus.ready_to_write, W2JobStatus.completed}:
        return _job_response(job.job_id)

    update_document_job(job.job_id, status=W2JobStatus.extracting, trace="extracting_started")
    try:
        facts = await extract_document_facts_async(
            job_id=job.job_id,
            patient_id=request.patient_id,
            doc_type=request.doc_type,
            source_id=source.source_id,
            content=source.content,
            content_type=source.content_type,
            settings=settings,
        )
    except (ExtractionError, LayoutExtractionError, ValueError) as exc:
        update_document_job(
            job.job_id,
            status=W2JobStatus.failed,
            trace="extracting_failed",
            error_code=exc.__class__.__name__,
        )
        emit_telemetry_event(
            settings,
            event="w2_document_extraction_failed",
            metadata={"error_class": exc.__class__.__name__, "doc_type": request.doc_type.value},
        )
        raise HTTPException(status_code=422, detail="Document extraction failed") from exc

    replace_document_facts(job.job_id, facts)
    update_document_job(
        job.job_id,
        status=W2JobStatus.review_required,
        trace=f"extracted_{len(facts)}_facts",
    )
    emit_telemetry_event(
        settings,
        event="w2_document_extraction_succeeded",
        metadata={"doc_type": request.doc_type.value, "fact_count": len(facts)},
    )
    return _job_response(job.job_id)


@router.get("/{job_id}", response_model=DocumentJobResponse)
async def document_job(
    job_id: str,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> DocumentJobResponse:
    job = await _require_job_for_user(job_id, user, settings)
    return _job_response(job.job_id)


@router.get("/{job_id}/review", response_model=DocumentReviewPayload)
async def document_review(
    job_id: str,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> DocumentReviewPayload:
    job = await _require_job_for_user(job_id, user, settings)
    return DocumentReviewPayload(job=job, facts=read_document_facts(job.job_id), trace=job.trace)


@router.post("/{job_id}/review/decisions", response_model=DocumentReviewResult)
async def submit_review_decisions(
    job_id: str,
    request: ReviewDecisionsRequest,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> DocumentReviewResult:
    _require_document_access(user)
    job = await _require_job_for_user(job_id, user, settings)
    facts = {fact.fact_id: fact for fact in read_document_facts(job.job_id)}
    for decision in request.decisions:
        fact = facts.get(decision.fact_id)
        if fact is None:
            raise HTTPException(status_code=404, detail="Extracted fact was not found")
        if decision.action == "approve":
            if fact.blocking_reasons:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "fact_id": fact.fact_id,
                        "blocking_reasons": fact.blocking_reasons,
                    },
                )
            updated = fact.model_copy(
                update={
                    "status": W2FactStatus.approved,
                    "reviewed_by": user.user_id,
                    "reviewed_at": now_utc(),
                }
            )
        else:
            updated = fact.model_copy(
                update={
                    "status": W2FactStatus.rejected,
                    "reviewed_by": user.user_id,
                    "reviewed_at": now_utc(),
                }
            )
        update_document_fact(job.job_id, updated)

    next_status = _status_after_review(read_document_facts(job.job_id))
    updated_job = update_document_job(
        job.job_id,
        status=next_status,
        trace="review_decisions_persisted",
    )
    emit_telemetry_event(
        settings,
        event="w2_document_review_decisions",
        metadata={"decision_count": len(request.decisions), "status": next_status.value},
    )
    facts_list = read_document_facts(job.job_id)
    return DocumentReviewResult(
        job=updated_job,
        facts=facts_list,
        fact_counts=fact_counts(facts_list),
    )


@router.post("/{job_id}/write", response_model=DocumentWriteResult)
async def write_approved_facts(
    job_id: str,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> DocumentWriteResult:
    _require_document_access(user)
    job = await _require_job_for_user(job_id, user, settings)
    job, write_started = begin_document_write(job.job_id)
    if not write_started:
        if job.status == W2JobStatus.writing:
            raise HTTPException(status_code=409, detail="Document write already in progress")
        return DocumentWriteResult(
            job=job,
            written_count=0,
            skipped_count=0,
            failed_count=0,
            facts=read_document_facts(job.job_id),
        )

    written_count = 0
    skipped_count = 0
    failed_count = 0
    for fact in read_document_facts(job.job_id):
        if fact.status != W2FactStatus.approved:
            skipped_count += 1
            continue
        if fact.proposed_destination != W2ProposedDestination.openemr_observation:
            skipped_count += 1
            continue
        try:
            resource_id = await write_lab_fact_observation(fact=fact, user=user, settings=settings)
        except (ObservationWriteError, httpx.HTTPError) as exc:
            failed_count += 1
            update_document_fact(
                job.job_id,
                fact.model_copy(
                    update={
                        "status": W2FactStatus.write_failed,
                        "write_error": exc.__class__.__name__,
                    }
                ),
            )
            continue
        written_count += 1
        update_document_fact(
            job.job_id,
            fact.model_copy(
                update={
                    "status": W2FactStatus.written,
                    "written_resource_id": resource_id,
                    "write_error": None,
                }
            ),
        )

    final_facts = read_document_facts(job.job_id)
    has_unresolved_review = any(fact.status == W2FactStatus.review_required for fact in final_facts)
    final_status = (
        W2JobStatus.completed
        if failed_count == 0 and not has_unresolved_review
        else W2JobStatus.review_required
    )
    updated_job = update_document_job(
        job.job_id,
        status=final_status,
        trace="write_finished",
    )
    emit_telemetry_event(
        settings,
        event="w2_document_write_finished",
        metadata={
            "written_count": written_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
        },
    )
    return DocumentWriteResult(
        job=updated_job,
        written_count=written_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        facts=final_facts,
    )


@router.get("/patients/{patient_id}/approved-evidence")
async def approved_evidence(
    patient_id: str,
    user: Annotated[RequestUser, Depends(get_request_user)],
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _require_document_access(user)
    await _require_patient_access(user=user, patient_id=patient_id, settings=settings)
    evidence = approved_document_evidence(patient_id)
    return {
        "patient_id": patient_id,
        "evidence_count": len(evidence),
        "evidence": [item.model_dump(mode="json") for item in evidence],
    }


def _job_response(job_id: str) -> DocumentJobResponse:
    job = require_document_job(job_id)
    facts = read_document_facts(job_id)
    return DocumentJobResponse(job=job, fact_counts=fact_counts(facts))


async def _require_job_for_user(
    job_id: str,
    user: RequestUser,
    settings: Settings,
) -> DocumentJobRecord:
    job = require_document_job(job_id)
    source = read_document_source(job.source.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source document was not found")
    if job.patient_id != source.patient_id:
        raise HTTPException(status_code=500, detail="Document job source mismatch")
    await _require_patient_access(user=user, patient_id=job.patient_id, settings=settings)
    return job


def _require_document_access(user: RequestUser) -> None:
    if user.role not in {Role.doctor, Role.np_pa, Role.nurse, Role.admin}:
        raise HTTPException(status_code=403, detail="Role is not allowed to review documents")


async def _require_patient_access(
    *,
    user: RequestUser,
    patient_id: str,
    settings: Settings,
) -> None:
    if settings.openemr_fhir_base_url is None:
        return
    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    try:
        await client.get_patient_summary(patient_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="OpenEMR patient access denied") from exc
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="OpenEMR patient was not found") from exc
        raise HTTPException(status_code=502, detail="OpenEMR patient access check failed") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="OpenEMR patient access check failed") from exc


def _status_after_review(facts: list[ExtractedFact]) -> W2JobStatus:
    if any(fact.status == W2FactStatus.approved for fact in facts):
        return W2JobStatus.ready_to_write
    if facts and all(fact.status == W2FactStatus.rejected for fact in facts):
        return W2JobStatus.completed
    return W2JobStatus.review_required
