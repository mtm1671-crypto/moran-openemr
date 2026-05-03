import argparse
import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.config import Settings, get_settings
from app.evidence_tools import FhirEvidenceService
from app.fhir_client import OpenEMRFhirClient
from app.openemr_auth import OpenEMRTokenError, resolve_service_fhir_bearer_token
from app.persistence import (
    build_job_run_record,
    build_semantic_relationship_records,
    create_job_run,
    initialize_phi_schema,
    purge_expired_phi_records,
    update_job_run,
    upsert_semantic_relationship_records,
)
from app.telemetry import emit_telemetry_event
from app.vector_store import VectorStoreError, index_patient_evidence


async def run_nightly_maintenance(settings: Settings) -> dict[str, Any]:
    settings.assert_runtime_config()
    if not (settings.requires_phi_controls() or settings.vector_search_enabled or settings.evidence_cache_enabled):
        return {
            "ok": True,
            "job": "nightly_maintenance",
            "skipped": True,
            "reason": "persistent PHI storage is not enabled",
            "ran_at": datetime.now(tz=UTC).isoformat(),
        }

    await initialize_phi_schema(settings)
    purge_counts = await purge_expired_phi_records(settings)
    reindex_result: dict[str, Any] | None = None
    if settings.nightly_reindex_enabled:
        reindex_result = await run_nightly_patient_reindex(settings)
    return {
        "ok": True,
        "job": "nightly_maintenance",
        "skipped": False,
        "ran_at": datetime.now(tz=UTC).isoformat(),
        "purge_counts": purge_counts,
        "reindex": reindex_result,
    }


async def run_patient_reindex(
    *,
    settings: Settings,
    patient_id: str,
    actor_user_id: str = "system",
) -> dict[str, Any]:
    settings.assert_runtime_config()
    if settings.openemr_fhir_base_url is None:
        raise RuntimeError("OPENEMR_FHIR_BASE_URL is required for patient reindex")
    if not settings.vector_search_enabled:
        raise RuntimeError("VECTOR_SEARCH_ENABLED must be true for patient reindex")

    await initialize_phi_schema(settings)
    job_id = await create_job_run(
        settings,
        build_job_run_record(
            settings=settings,
            job_type="patient_reindex",
            status="running",
            actor_user_id=actor_user_id,
            patient_id=patient_id,
            metadata_payload={"trigger": "api_or_worker"},
        ),
    )
    emit_telemetry_event(
        settings,
        event="patient_reindex_started",
        metadata={"job_type": "patient_reindex"},
    )
    try:
        bearer_token = await resolve_service_fhir_bearer_token(settings)
        service = FhirEvidenceService(
            OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
        )
        retrieval = await service.collect_patient_index_evidence(patient_id)
        indexed_count = await index_patient_evidence(settings=settings, evidence=retrieval.evidence)
        relationship_records = build_semantic_relationship_records(
            settings=settings,
            evidence=retrieval.evidence,
            ttl_days=settings.vector_index_ttl_days,
        )
        await upsert_semantic_relationship_records(settings, relationship_records)
        metadata: dict[str, Any] = {
            "indexed_evidence_count": indexed_count,
            "relationship_count": len(relationship_records),
            "tool_count": len(retrieval.tools),
            "limitation_count": len(retrieval.limitations),
        }
        await update_job_run(
            settings=settings,
            job_id=job_id,
            status="succeeded",
            metadata_payload=metadata,
        )
        emit_telemetry_event(settings, event="patient_reindex_succeeded", metadata=metadata)
        return {
            "ok": True,
            "job_id": job_id,
            "job": "patient_reindex",
            "indexed_evidence_count": indexed_count,
            "relationship_count": len(relationship_records),
        }
    except (OpenEMRTokenError, VectorStoreError, Exception) as exc:
        metadata = {"error_class": exc.__class__.__name__}
        await update_job_run(
            settings=settings,
            job_id=job_id,
            status="failed",
            metadata_payload=metadata,
            error_code="patient_reindex_failed",
        )
        emit_telemetry_event(settings, event="patient_reindex_failed", metadata=metadata)
        raise


async def run_nightly_patient_reindex(settings: Settings) -> dict[str, Any]:
    if settings.openemr_fhir_base_url is None:
        return {"ok": False, "skipped": True, "reason": "OpenEMR FHIR is not configured"}
    bearer_token = await resolve_service_fhir_bearer_token(settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    patients = await client.list_patients(count=settings.nightly_reindex_patient_count)
    results: list[dict[str, Any]] = []
    for patient in patients:
        results.append(
            await run_patient_reindex(
                settings=settings,
                patient_id=patient.patient_id,
                actor_user_id="system:nightly_reindex",
            )
        )
    return {"ok": True, "patient_count": len(patients), "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Clinical Co-Pilot background jobs")
    parser.add_argument(
        "job",
        choices=["nightly-maintenance", "patient-reindex"],
        help="Background job to run once and exit.",
    )
    parser.add_argument("--patient-id", help="OpenEMR FHIR Patient.id for patient-reindex.")
    args = parser.parse_args()

    settings = get_settings()
    if args.job == "nightly-maintenance":
        result = asyncio.run(run_nightly_maintenance(settings))
    elif args.job == "patient-reindex":
        if not args.patient_id:
            raise SystemExit("--patient-id is required for patient-reindex")
        result = asyncio.run(run_patient_reindex(settings=settings, patient_id=args.patient_id))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
