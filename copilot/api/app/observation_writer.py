from __future__ import annotations

from typing import Any

from app.config import Settings
from app.document_models import ExtractedFact, W2FactType, W2ProposedDestination
from app.fhir_client import OpenEMRFhirClient
from app.models import RequestUser
from app.openemr_auth import resolve_fhir_bearer_token


class ObservationWriteError(RuntimeError):
    pass


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

    resource = build_observation_resource(fact)
    if settings.openemr_fhir_base_url is None:
        if settings.requires_phi_controls():
            raise ObservationWriteError("OPENEMR_FHIR_BASE_URL is required before writing PHI")
        return f"demo-observation-{fact.fact_id}"

    bearer_token = await resolve_fhir_bearer_token(user, settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=bearer_token)
    created = await client.create_resource("Observation", resource)
    resource_id = created.get("id")
    if not isinstance(resource_id, str) or not resource_id:
        raise ObservationWriteError("OpenEMR did not return an Observation id")
    return resource_id


def build_observation_resource(fact: ExtractedFact) -> dict[str, Any]:
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
        "subject": {"reference": f"Patient/{fact.patient_id}"},
        "note": [
            {
                "text": (
                    "Imported from Week 2 synthetic document review with "
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

