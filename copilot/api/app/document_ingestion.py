"""Week 2 document ingestion, extraction, review, and write routes.

Documents are treated as staged evidence. Extraction can propose facts, but a
human review decision is required before lab facts are written to OpenEMR.
"""

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
    StoredDocumentSource,
    append_document_job_trace,
    approved_document_evidence,
    begin_document_write,
    cache_document_workflow,
    create_document_workflow,
    document_workflow_snapshot,
    fact_counts,
    read_document_facts,
    read_document_source,
    require_document_job,
    replace_document_facts,
    source_sha256,
    update_document_fact,
    update_document_job,
)
from app.extraction_adapters import ExtractionError
from app.fhir_client import OpenEMRFhirClient
from app.extraction_pipeline import extract_document_facts_async
from app.models import EvidenceObject, RequestUser, Role
from app.observation_writer import ObservationWriteError, write_lab_fact_observation
from app.ocr_layout import LayoutExtractionError
from app.openemr_auth import resolve_fhir_bearer_token
from app.persistence import (
    document_workflow_persistence_configured,
    read_approved_document_evidence,
    read_document_workflow_snapshot,
    read_document_workflow_snapshot_by_source_key,
    upsert_document_workflow_snapshot,
)
from app.telemetry import emit_telemetry_event
from app.w2_graph import W2GraphState, supervisor_route

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

    job, source, was_created = await _get_or_create_document_workflow(
        request=request,
        content=content,
        actor_user_id=user.user_id,
        settings=settings,
    )
    if not was_created and _needs_fresh_extraction(job.job_id):
        update_document_job(
            job.job_id,
            status=W2JobStatus.extracting,
            trace="reextracting_after_write_failure",
            error_code=None,
        )
        replace_document_facts(job.job_id, [])
        await _persist_document_job(settings, job.job_id)
    elif not was_created or job.status in {W2JobStatus.review_required, W2JobStatus.ready_to_write, W2JobStatus.completed}:
        # Idempotent upload: repeated submits for the same source return the
        # existing job instead of duplicating extraction work. A prior failed
        # chart write is the exception: clicking Extract should restore a clean
        # review state instead of resurfacing stale write errors.
        await _persist_document_job(settings, job.job_id)
        return _job_response(job.job_id)

    update_document_job(job.job_id, status=W2JobStatus.extracting, trace="extracting_started")
    await _persist_document_job(settings, job.job_id)
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
        await _persist_document_job(settings, job.job_id)
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
    _append_supervisor_trace(job.job_id, review_submitted=False)
    await _persist_document_job(settings, job.job_id)
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
    if job.patient_id is None and any(decision.action == "approve" for decision in request.decisions):
        # We allow extraction without a patient so example docs can be tested,
        # but approved facts cannot enter patient evidence until scoped.
        raise HTTPException(
            status_code=422,
            detail="Assign the document to a patient before approving extracted facts",
        )
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
    _append_supervisor_trace(job.job_id, review_submitted=True)
    await _persist_document_job(settings, job.job_id)
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
    if job.patient_id is None:
        raise HTTPException(
            status_code=422,
            detail="Assign the document to a patient before writing extracted facts",
        )
    job, write_started = begin_document_write(job.job_id)
    await _persist_document_job(settings, job.job_id)
    if not write_started:
        # Prevent duplicate write drains from racing each other. Production
        # outbox workers would enforce this with row locks / SKIP LOCKED.
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
    writable_statuses = {W2FactStatus.approved, W2FactStatus.write_failed}
    for fact in read_document_facts(job.job_id):
        if fact.status not in writable_statuses:
            skipped_count += 1
            continue
        if fact.proposed_destination != W2ProposedDestination.openemr_observation:
            skipped_count += 1
            continue
        try:
            resource_id = await write_lab_fact_observation(fact=fact, user=user, settings=settings)
        except (ObservationWriteError, httpx.HTTPError) as exc:
            # Keep per-fact write diagnostics visible to the reviewer. This is
            # how the UI can explain whether scope, value mapping, or FHIR failed.
            write_error = _write_error_message(exc)
            failed_count += 1
            update_document_fact(
                job.job_id,
                fact.model_copy(
                    update={
                        "status": W2FactStatus.write_failed,
                        "write_error": write_error,
                    }
                ),
            )
            emit_telemetry_event(
                settings,
                event="w2_document_fact_write_failed",
                metadata={
                    "doc_type": job.doc_type.value,
                    "fact_type": fact.fact_type.value,
                    "destination": fact.proposed_destination.value,
                    "error_kind": _write_error_kind(write_error),
                },
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
    _append_supervisor_trace(job.job_id, review_submitted=True)
    await _persist_document_job(settings, job.job_id)
    emit_telemetry_event(
        settings,
        event="w2_document_write_finished",
        metadata={
            "written_count": written_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "error_kinds": _write_error_counts(final_facts),
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
    if document_workflow_persistence_configured(settings):
        evidence = _merge_document_evidence(
            evidence,
            await read_approved_document_evidence(settings, patient_id),
        )
    return {
        "patient_id": patient_id,
        "evidence_count": len(evidence),
        "evidence": [item.model_dump(mode="json") for item in evidence],
    }


def _job_response(job_id: str) -> DocumentJobResponse:
    job = require_document_job(job_id)
    facts = read_document_facts(job_id)
    return DocumentJobResponse(job=job, fact_counts=fact_counts(facts))


async def _get_or_create_document_workflow(
    *,
    request: DocumentAttachExtractRequest,
    content: bytes,
    actor_user_id: str,
    settings: Settings,
) -> tuple[DocumentJobRecord, StoredDocumentSource, bool]:
    if document_workflow_persistence_configured(settings):
        snapshot = await read_document_workflow_snapshot_by_source_key(
            settings=settings,
            patient_id=request.patient_id,
            doc_type=request.doc_type,
            source_hash=source_sha256(content),
            content_type=request.content_type,
        )
        if snapshot is not None:
            job, source, facts = snapshot
            cache_document_workflow(job=job, source=source, facts=facts)
            return job, source, False

    return create_document_workflow(
        patient_id=request.patient_id,
        doc_type=request.doc_type,
        filename=request.filename,
        content_type=request.content_type,
        content=content,
        actor_user_id=actor_user_id,
    )


async def _require_job_for_user(
    job_id: str,
    user: RequestUser,
    settings: Settings,
) -> DocumentJobRecord:
    job = await _require_cached_or_persisted_job(job_id, settings)
    source = read_document_source(job.source.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source document was not found")
    if job.patient_id != source.patient_id:
        raise HTTPException(status_code=500, detail="Document job source mismatch")
    if job.patient_id is None:
        if user.role == Role.admin or job.actor_user_id == user.user_id:
            return job
        raise HTTPException(status_code=403, detail="Unassigned document access denied")
    await _require_patient_access(user=user, patient_id=job.patient_id, settings=settings)
    return job


async def _require_cached_or_persisted_job(job_id: str, settings: Settings) -> DocumentJobRecord:
    try:
        return require_document_job(job_id)
    except KeyError:
        if document_workflow_persistence_configured(settings):
            snapshot = await read_document_workflow_snapshot(settings, job_id)
            if snapshot is not None:
                job, source, facts = snapshot
                cache_document_workflow(job=job, source=source, facts=facts)
                return job
        raise HTTPException(status_code=404, detail="Document job was not found")


async def _persist_document_job(settings: Settings, job_id: str) -> None:
    if not document_workflow_persistence_configured(settings):
        return
    job, source, facts = document_workflow_snapshot(job_id)
    await upsert_document_workflow_snapshot(
        settings=settings,
        job=job,
        source=source,
        facts=facts,
    )


def _needs_fresh_extraction(job_id: str) -> bool:
    return any(fact.status == W2FactStatus.write_failed for fact in read_document_facts(job_id))


def _append_supervisor_trace(job_id: str, *, review_submitted: bool) -> None:
    job, _source, facts = document_workflow_snapshot(job_id)
    state = W2GraphState(
        document_job_id=job.job_id,
        patient_id=job.patient_id or "unassigned",
        extracted_facts=facts,
        review_submitted=review_submitted,
        guideline_retrieved=False,
    )
    decision = supervisor_route(state)
    append_document_job_trace(
        job_id,
        f"supervisor:{decision.route.value}:{decision.reason}",
    )


def _merge_document_evidence(
    first: list[EvidenceObject],
    second: list[EvidenceObject],
) -> list[EvidenceObject]:
    merged: list[EvidenceObject] = []
    seen: set[str] = set()
    for item in [*first, *second]:
        evidence_id = getattr(item, "evidence_id", None)
        if not isinstance(evidence_id, str) or evidence_id in seen:
            continue
        merged.append(item)
        seen.add(evidence_id)
    return merged


def _write_error_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            detail = _operation_outcome_summary(exc.response)
            suffix = f": {detail}" if detail else ""
            return (
                f"OpenEMR write denied (HTTP {status_code}): "
                f"re-authorize with user/Observation.write scope{suffix}"
            )
        if status_code == 400:
            detail = _operation_outcome_summary(exc.response)
            suffix = f": {detail}" if detail else ""
            return f"OpenEMR rejected the Observation payload (HTTP 400){suffix}"
        return f"OpenEMR write failed (HTTP {status_code})"
    if isinstance(exc, httpx.TimeoutException):
        return "OpenEMR write timed out"
    if isinstance(exc, ObservationWriteError):
        return str(exc) or exc.__class__.__name__
    return exc.__class__.__name__


def _operation_outcome_summary(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None

    for key in ("error_description", "detail", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:180]

    issues = payload.get("issue")
    if isinstance(issues, list):
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            diagnostics = issue.get("diagnostics")
            if isinstance(diagnostics, str) and diagnostics.strip():
                return diagnostics.strip()[:180]
            details = issue.get("details")
            if isinstance(details, dict):
                text = details.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()[:180]
            code = issue.get("code")
            if isinstance(code, str) and code.strip():
                return code.strip()[:180]
    return None


def _write_error_kind(message: str | None) -> str:
    if not message:
        return "none"
    if "HTTP 401" in message or "HTTP 403" in message:
        return "authorization"
    if "HTTP 400" in message:
        return "payload_validation"
    if "timed out" in message:
        return "timeout"
    if "HTTP " in message:
        return "openemr_http"
    return "local_validation"


def _write_error_counts(facts: list[ExtractedFact]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fact in facts:
        if fact.status != W2FactStatus.write_failed:
            continue
        kind = _write_error_kind(fact.write_error)
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _require_document_access(user: RequestUser) -> None:
    if user.role not in {Role.doctor, Role.np_pa, Role.nurse, Role.admin}:
        raise HTTPException(status_code=403, detail="Role is not allowed to review documents")


async def _require_patient_access(
    *,
    user: RequestUser,
    patient_id: str | None,
    settings: Settings,
) -> None:
    if patient_id is None:
        return
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
