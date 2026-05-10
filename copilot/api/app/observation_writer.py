"""FHIR Observation write adapter for approved extracted lab facts.

This is the narrow write boundary for Week 2. Extraction does not mutate the
chart directly; only reviewed lab facts proposed for OpenEMR Observations reach
this adapter.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.demo_patients import canonical_profile_patient_id
from app.document_models import ExtractedFact, W2FactType, W2ProposedDestination
from app.fhir_client import OpenEMRFhirClient
from app.models import RequestUser
from app.openemr_auth import resolve_fhir_bearer_token


class ObservationWriteError(RuntimeError):
    pass


DOCUMENT_FACT_IDENTIFIER_SYSTEM = "https://agentforge.dev/fhir/identifier/document-fact"
OBSERVATION_CREATE_UNAVAILABLE_MESSAGE = (
    "OpenEMR FHIR Observation.create is not exposed by this OpenEMR deployment; "
    "approved document evidence is retained, but chart lab writeback is unavailable."
)


async def write_lab_fact_observation(
    *,
    fact: ExtractedFact,
    user: RequestUser,
    settings: Settings,
) -> str:
    if fact.fact_type != W2FactType.lab_result:
        raise ObservationWriteError("Only lab_result facts can be written as Observations")
    if fact.proposed_destination != W2ProposedDestination.openemr_observation:
        raise ObservationWriteError("Fact is not proposed for OpenEMR Observation write")

    patient_id = _openemr_patient_id(fact, settings)
    resource = build_observation_resource(fact, patient_id=patient_id)
    if settings.demo_auth_bypass and user.access_token is None:
        raise ObservationWriteError(
            "Observation writeback is disabled while demo auth bypass is active; "
            "approved document evidence remains retrievable."
        )
    if settings.openemr_fhir_base_url is None:
        raise ObservationWriteError("OPENEMR_FHIR_BASE_URL is required before writing Observations")

    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    await _require_observation_create_supported(client)
    existing_id = await _find_existing_observation_id(client=client, fact=fact, patient_id=patient_id)
    if existing_id is not None:
        return existing_id
    created = await client.create_resource("Observation", resource)
    resource_id = created.get("id")
    if not isinstance(resource_id, str) or not resource_id:
        raise ObservationWriteError("OpenEMR did not return an Observation id")
    await _verify_observation_roundtrip(
        client=client,
        fact=fact,
        patient_id=patient_id,
        resource_id=resource_id,
    )
    return resource_id


async def openemr_observation_create_supported(settings: Settings) -> bool:
    if settings.openemr_fhir_base_url is None:
        return False
    client = OpenEMRFhirClient(settings=settings)
    try:
        return await client.supports_create("Observation")
    except httpx.HTTPError:
        return False


async def _require_observation_create_supported(client: OpenEMRFhirClient) -> None:
    try:
        supported = await client.supports_create("Observation")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403, 404}:
            return
        raise
    except httpx.HTTPError:
        return
    if not supported:
        raise ObservationWriteError(OBSERVATION_CREATE_UNAVAILABLE_MESSAGE)


def build_observation_resource(fact: ExtractedFact, *, patient_id: str | None = None) -> dict[str, Any]:
    if fact.patient_id is None:
        raise ObservationWriteError("Fact must be assigned to a patient before writing")
    patient_id = patient_id or fact.patient_id

    # Map the extracted fact into a minimal FHIR Observation. Keep provenance in
    # the note so a reviewer can trace the chart write back to the source span.
    payload = fact.payload
    value_text = str(payload.get("value") or fact.normalized_value.split()[0])
    numeric_value = _coerce_float(value_text)
    unit = payload.get("unit")
    loinc_code = payload.get("loinc_code")
    test_name = str(payload.get("test_name") or fact.display_label)
    collection_date = payload.get("collection_date")
    abnormal_flag = payload.get("abnormal_flag")

    code_coding: list[dict[str, str]] = []
    if isinstance(loinc_code, str) and loinc_code:
        code_coding.append(
            {
                "system": "http://loinc.org",
                "code": loinc_code,
                "display": test_name,
            }
        )

    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "status": "final",
        "identifier": [
            {
                "system": DOCUMENT_FACT_IDENTIFIER_SYSTEM,
                "value": fact.fact_id,
            }
        ],
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                        "display": "Laboratory",
                    }
                ],
                "text": "Laboratory",
            }
        ],
        "code": {"coding": code_coding, "text": test_name},
        "subject": {"reference": f"Patient/{patient_id}"},
        "note": [
            {
                "text": (
                    "Imported from Week 2 document review with "
                    f"source citation {fact.citation.field_or_chunk_id}."
                )
            }
        ],
    }
    if isinstance(collection_date, str) and collection_date:
        resource["effectiveDateTime"] = collection_date
    if numeric_value is not None:
        resource["valueQuantity"] = {"value": numeric_value}
        if isinstance(unit, str) and unit:
            resource["valueQuantity"]["unit"] = unit
            resource["valueQuantity"]["code"] = unit
    else:
        resource["valueString"] = value_text
    interpretation = _interpretation(abnormal_flag)
    if interpretation is not None:
        resource["interpretation"] = [interpretation]
    return resource


async def _find_existing_observation_id(
    *,
    client: OpenEMRFhirClient,
    fact: ExtractedFact,
    patient_id: str | None = None,
) -> str | None:
    if fact.patient_id is None:
        return None
    patient_id = patient_id or fact.patient_id
    existing = await client.search_observations_by_identifier(
        patient_id=patient_id,
        system=DOCUMENT_FACT_IDENTIFIER_SYSTEM,
        value=fact.fact_id,
    )
    for resource in existing:
        resource_id = resource.get("id")
        if isinstance(resource_id, str) and resource_id:
            return resource_id
    return None


async def _verify_observation_roundtrip(
    *,
    client: OpenEMRFhirClient,
    fact: ExtractedFact,
    patient_id: str,
    resource_id: str,
) -> None:
    try:
        resource = await client.read_resource("Observation", resource_id)
    except httpx.HTTPError as exc:
        raise ObservationWriteError("OpenEMR Observation round-trip read failed") from exc

    if resource.get("resourceType") != "Observation":
        raise ObservationWriteError("OpenEMR round-trip did not return an Observation")
    if resource.get("id") != resource_id:
        raise ObservationWriteError("OpenEMR round-trip returned the wrong Observation id")
    if fact.patient_id is None:
        raise ObservationWriteError("Fact must be assigned to a patient before verification")
    subject = resource.get("subject")
    if not isinstance(subject, dict) or subject.get("reference") != f"Patient/{patient_id}":
        raise ObservationWriteError("OpenEMR round-trip Observation subject did not match patient")
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list) or not any(
        isinstance(identifier, dict)
        and identifier.get("system") == DOCUMENT_FACT_IDENTIFIER_SYSTEM
        and identifier.get("value") == fact.fact_id
        for identifier in identifiers
    ):
        raise ObservationWriteError("OpenEMR round-trip Observation lost the document identifier")


def _openemr_patient_id(fact: ExtractedFact, settings: Settings) -> str:
    if fact.patient_id is None:
        raise ObservationWriteError("Fact must be assigned to a patient before writing")
    if settings.demo_auth_bypass:
        return canonical_profile_patient_id(fact.patient_id)
    return fact.patient_id


def _coerce_float(value: str) -> float | None:
    try:
        return float(value.lstrip("<>"))
    except ValueError:
        return None


def _interpretation(abnormal_flag: object) -> dict[str, Any] | None:
    mapping = {
        "high": ("H", "High"),
        "low": ("L", "Low"),
        "abnormal": ("A", "Abnormal"),
        "normal": ("N", "Normal"),
    }
    if not isinstance(abnormal_flag, str):
        return None
    selected = mapping.get(abnormal_flag)
    if selected is None:
        return None
    code, display = selected
    return {
        "coding": [
            {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                "code": code,
                "display": display,
            }
        ],
        "text": display,
    }
