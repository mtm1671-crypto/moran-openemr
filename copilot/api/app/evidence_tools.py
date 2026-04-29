from dataclasses import dataclass, field
from datetime import UTC, datetime
from re import sub
from typing import Any

from app.fhir_client import OpenEMRFhirClient
from app.models import EvidenceObject


@dataclass(frozen=True)
class EvidenceRetrievalResult:
    evidence: list[EvidenceObject]
    tools: list[str]
    limitations: list[str] = field(default_factory=list)


class FhirEvidenceService:
    def __init__(self, client: OpenEMRFhirClient) -> None:
        self._client = client

    async def collect_for_question(
        self,
        *,
        patient_id: str,
        message: str,
        quick_question_id: str | None = None,
    ) -> EvidenceRetrievalResult:
        requested_tools = _tools_for_message(message, quick_question_id)
        evidence: list[EvidenceObject] = []
        limitations: list[str] = []
        completed_tools: list[str] = []

        if "get_patient_demographics" in requested_tools:
            completed_tools.append("get_patient_demographics")
            evidence.extend(await self.get_patient_demographics(patient_id))

        if "get_active_problems" in requested_tools:
            completed_tools.append("get_active_problems")
            problems = await self.get_active_problems(patient_id)
            if not problems:
                limitations.append("No active problems were returned by OpenEMR FHIR.")
            evidence.extend(problems)

        if "get_recent_labs" in requested_tools:
            completed_tools.append("get_recent_labs")
            labs = await self.get_recent_labs(patient_id)
            if not labs:
                limitations.append("No recent laboratory observations were returned by OpenEMR FHIR.")
            evidence.extend(labs)

        if "get_medications" in requested_tools:
            completed_tools.append("get_medications")
            medications = await self.get_medications(patient_id)
            if not medications:
                limitations.append("No active medications were returned by OpenEMR FHIR.")
            evidence.extend(medications)

        if "get_allergies" in requested_tools:
            completed_tools.append("get_allergies")
            allergies = await self.get_allergies(patient_id)
            if not allergies:
                limitations.append("No allergies were returned by OpenEMR FHIR.")
            evidence.extend(allergies)

        return EvidenceRetrievalResult(
            evidence=evidence,
            tools=completed_tools,
            limitations=limitations,
        )

    async def get_patient_demographics(self, patient_id: str) -> list[EvidenceObject]:
        patient = await self._client.get_patient(patient_id)
        return patient_demographics_evidence(patient)

    async def get_active_problems(self, patient_id: str) -> list[EvidenceObject]:
        conditions = await self._client.search_active_conditions(patient_id)
        return [condition_evidence(condition, patient_id) for condition in conditions]

    async def get_recent_labs(self, patient_id: str) -> list[EvidenceObject]:
        observations = await self._client.search_lab_observations(patient_id)
        return [lab_observation_evidence(observation, patient_id) for observation in observations]

    async def get_medications(self, patient_id: str) -> list[EvidenceObject]:
        medication_requests = await self._client.search_medication_requests(patient_id)
        return [
            medication_request_evidence(medication_request, patient_id)
            for medication_request in medication_requests
        ]

    async def get_allergies(self, patient_id: str) -> list[EvidenceObject]:
        allergies = await self._client.search_allergy_intolerances(patient_id)
        return [allergy_intolerance_evidence(allergy, patient_id) for allergy in allergies]


def patient_demographics_evidence(patient: dict[str, Any]) -> list[EvidenceObject]:
    patient_id = _resource_id(patient, "unknown-patient")
    display_name = _patient_name(patient) or patient_id
    retrieved_at = datetime.now(tz=UTC)
    source_url = _source_url("Patient", patient_id)

    evidence = [
        EvidenceObject(
            evidence_id=_evidence_id("patient", patient_id, "name"),
            patient_id=patient_id,
            source_type="patient_demographics",
            source_id=patient_id,
            display_name="Patient name",
            fact=f"Patient name is {display_name}.",
            retrieved_at=retrieved_at,
            source_url=source_url,
            metadata={"field": "name"},
        )
    ]

    birth_date = patient.get("birthDate")
    if isinstance(birth_date, str) and birth_date:
        evidence.append(
            EvidenceObject(
                evidence_id=_evidence_id("patient", patient_id, "birthDate"),
                patient_id=patient_id,
                source_type="patient_demographics",
                source_id=patient_id,
                display_name="Patient birth date",
                fact=f"Patient birth date is {birth_date}.",
                effective_at=_parse_fhir_datetime(birth_date),
                retrieved_at=retrieved_at,
                source_url=source_url,
                metadata={"field": "birthDate"},
            )
        )

    gender = patient.get("gender")
    if isinstance(gender, str) and gender:
        evidence.append(
            EvidenceObject(
                evidence_id=_evidence_id("patient", patient_id, "gender"),
                patient_id=patient_id,
                source_type="patient_demographics",
                source_id=patient_id,
                display_name="Patient gender",
                fact=f"Patient gender is {gender}.",
                retrieved_at=retrieved_at,
                source_url=source_url,
                metadata={"field": "gender"},
            )
        )

    return evidence


def condition_evidence(condition: dict[str, Any], patient_id: str) -> EvidenceObject:
    condition_id = _resource_id(condition, "unknown-condition")
    display = _codeable_concept_display(condition.get("code")) or condition_id
    clinical_status = _codeable_concept_display(condition.get("clinicalStatus"))
    date_value = _first_string(
        condition.get("recordedDate"),
        condition.get("onsetDateTime"),
        condition.get("abatementDateTime"),
    )
    status_prefix = "Active problem"
    if clinical_status and "active" not in clinical_status.lower():
        status_prefix = "Problem"

    return EvidenceObject(
        evidence_id=_evidence_id("condition", patient_id, condition_id),
        patient_id=patient_id,
        source_type="active_problem",
        source_id=condition_id,
        display_name=display,
        fact=f"{status_prefix}: {display}.",
        effective_at=_parse_fhir_datetime(date_value),
        source_updated_at=_parse_fhir_datetime(condition.get("recordedDate")),
        retrieved_at=datetime.now(tz=UTC),
        source_url=_source_url("Condition", condition_id, patient_id),
        metadata={
            "clinical_status": clinical_status,
            "recordedDate": condition.get("recordedDate"),
        },
    )


def lab_observation_evidence(observation: dict[str, Any], patient_id: str) -> EvidenceObject:
    observation_id = _resource_id(observation, "unknown-observation")
    display = _codeable_concept_display(observation.get("code")) or observation_id
    value = _observation_value(observation)
    observed_at = _first_string(
        observation.get("effectiveDateTime"),
        observation.get("issued"),
        observation.get("effectiveInstant"),
    )
    interpretation = _interpretation_display(observation)
    abnormal = _is_abnormal_interpretation(interpretation)

    if value and observed_at:
        fact = f"{display} was {value} on {observed_at}."
    elif value:
        fact = f"{display} was {value}."
    elif observed_at:
        fact = f"{display} was recorded on {observed_at}."
    else:
        fact = f"{display} was returned by OpenEMR as a laboratory observation."

    if abnormal:
        fact = f"{fact} OpenEMR marked the result as abnormal."

    return EvidenceObject(
        evidence_id=_evidence_id("observation", patient_id, observation_id),
        patient_id=patient_id,
        source_type="lab_result",
        source_id=observation_id,
        display_name=display,
        fact=fact,
        effective_at=_parse_fhir_datetime(observed_at),
        source_updated_at=_parse_fhir_datetime(observation.get("issued")),
        retrieved_at=datetime.now(tz=UTC),
        source_url=_source_url("Observation", observation_id, patient_id),
        metadata={
            "interpretation": interpretation,
            "abnormal": abnormal,
            "status": observation.get("status"),
            "value": value,
        },
    )


def medication_request_evidence(medication_request: dict[str, Any], patient_id: str) -> EvidenceObject:
    medication_request_id = _resource_id(medication_request, "unknown-medication-request")
    display = (
        _codeable_concept_display(medication_request.get("medicationCodeableConcept"))
        or _reference_display(medication_request.get("medicationReference"))
        or medication_request_id
    )
    status_value = medication_request.get("status")
    status_text = status_value if isinstance(status_value, str) and status_value else "unknown status"
    authored_on = medication_request.get("authoredOn")
    dosage_text = _first_dosage_text(medication_request)

    fact = f"Medication request ({status_text}): {display}."
    if dosage_text:
        fact = f"{fact} Sig: {dosage_text.rstrip('.')}."
    if isinstance(authored_on, str) and authored_on:
        fact = f"{fact} Authored on {authored_on}."

    return EvidenceObject(
        evidence_id=_evidence_id("medication_request", patient_id, medication_request_id),
        patient_id=patient_id,
        source_type="medication",
        source_id=medication_request_id,
        display_name=display,
        fact=fact,
        effective_at=_parse_fhir_datetime(authored_on),
        source_updated_at=_parse_fhir_datetime(authored_on),
        retrieved_at=datetime.now(tz=UTC),
        source_url=_source_url("MedicationRequest", medication_request_id, patient_id),
        metadata={
            "status": status_text,
            "dosage": dosage_text,
        },
    )


def allergy_intolerance_evidence(allergy: dict[str, Any], patient_id: str) -> EvidenceObject:
    allergy_id = _resource_id(allergy, "unknown-allergy")
    display = _codeable_concept_display(allergy.get("code")) or allergy_id
    clinical_status = _codeable_concept_display(allergy.get("clinicalStatus"))
    verification_status = _codeable_concept_display(allergy.get("verificationStatus"))
    recorded_date = allergy.get("recordedDate")
    reaction = _first_reaction_display(allergy)

    fact = f"Allergy/intolerance: {display}."
    if clinical_status:
        fact = f"{fact} Clinical status: {clinical_status}."
    if verification_status:
        fact = f"{fact} Verification: {verification_status}."
    if reaction:
        fact = f"{fact} Reaction: {reaction}."
    if isinstance(recorded_date, str) and recorded_date:
        fact = f"{fact} Recorded on {recorded_date}."

    return EvidenceObject(
        evidence_id=_evidence_id("allergy_intolerance", patient_id, allergy_id),
        patient_id=patient_id,
        source_type="allergy",
        source_id=allergy_id,
        display_name=display,
        fact=fact,
        effective_at=_parse_fhir_datetime(recorded_date),
        source_updated_at=_parse_fhir_datetime(recorded_date),
        retrieved_at=datetime.now(tz=UTC),
        source_url=_source_url("AllergyIntolerance", allergy_id, patient_id),
        metadata={
            "clinical_status": clinical_status,
            "verification_status": verification_status,
            "reaction": reaction,
        },
    )


def _tools_for_message(message: str, quick_question_id: str | None) -> list[str]:
    text = f"{message} {quick_question_id or ''}".lower()
    tools = ["get_patient_demographics"]

    wants_demographics = any(
        term in text
        for term in ["demographic", "name", "birth", "date of birth", "gender", "age"]
    )
    wants_broad_brief = any(
        term in text for term in ["before seeing", "know", "brief", "summary", "overview"]
    )
    wants_problems = any(term in text for term in ["problem", "history", "condition", "diagnosis"])
    wants_labs = any(term in text for term in ["lab", "a1c", "result", "abnormal", "creatinine", "egfr"])
    wants_medications = any(
        term in text for term in ["medication", "medicine", "meds", "prescription", "drug"]
    )
    wants_allergies = any(term in text for term in ["allergy", "allergies", "intolerance"])

    if wants_broad_brief or wants_problems:
        tools.append("get_active_problems")
    if wants_broad_brief or wants_labs:
        tools.append("get_recent_labs")
    if wants_medications:
        tools.append("get_medications")
    if wants_allergies:
        tools.append("get_allergies")

    if len(tools) == 1 and not any(
        [wants_demographics, wants_broad_brief, wants_problems, wants_labs, wants_medications, wants_allergies]
    ):
        tools.extend(["get_active_problems", "get_recent_labs"])

    return tools


def _patient_name(patient: dict[str, Any]) -> str | None:
    names = patient.get("name")
    if not isinstance(names, list) or not names:
        return None
    first = names[0]
    if not isinstance(first, dict):
        return None
    given = first.get("given")
    family = first.get("family")
    parts: list[str] = []
    if isinstance(given, list):
        parts.extend(str(item) for item in given if item)
    if isinstance(family, str) and family:
        parts.append(family)
    return " ".join(parts) if parts else None


def _codeable_concept_display(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    text = value.get("text")
    if isinstance(text, str) and text:
        return text
    coding = value.get("coding")
    if not isinstance(coding, list):
        return None
    for item in coding:
        if not isinstance(item, dict):
            continue
        display = item.get("display")
        if isinstance(display, str) and display:
            return display
        code = item.get("code")
        if isinstance(code, str) and code:
            return code
    return None


def _reference_display(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    display = value.get("display")
    if isinstance(display, str) and display:
        return display
    reference = value.get("reference")
    return reference if isinstance(reference, str) and reference else None


def _interpretation_display(observation: dict[str, Any]) -> str | None:
    interpretation = observation.get("interpretation")
    if not isinstance(interpretation, list) or not interpretation:
        return None
    return _codeable_concept_display(interpretation[0])


def _is_abnormal_interpretation(interpretation: str | None) -> bool:
    if not interpretation:
        return False
    return interpretation.lower() in {"a", "aa", "h", "hh", "l", "ll", "abnormal", "high", "low"}


def _observation_value(observation: dict[str, Any]) -> str | None:
    quantity = observation.get("valueQuantity")
    if isinstance(quantity, dict):
        value = quantity.get("value")
        unit = quantity.get("unit") or quantity.get("code")
        if value is not None and unit:
            return f"{value} {unit}"
        if value is not None:
            return str(value)

    value_string = observation.get("valueString")
    if isinstance(value_string, str) and value_string:
        return value_string

    value_concept = _codeable_concept_display(observation.get("valueCodeableConcept"))
    if value_concept:
        return value_concept

    return None


def _first_dosage_text(medication_request: dict[str, Any]) -> str | None:
    instructions = medication_request.get("dosageInstruction")
    if not isinstance(instructions, list):
        return None
    for instruction in instructions:
        if not isinstance(instruction, dict):
            continue
        text = instruction.get("text")
        if isinstance(text, str) and text:
            return text
    return None


def _first_reaction_display(allergy: dict[str, Any]) -> str | None:
    reactions = allergy.get("reaction")
    if not isinstance(reactions, list):
        return None
    for reaction in reactions:
        if not isinstance(reaction, dict):
            continue
        manifestations = reaction.get("manifestation")
        if not isinstance(manifestations, list):
            continue
        for manifestation in manifestations:
            display = _codeable_concept_display(manifestation)
            if display:
                return display
    return None


def _parse_fhir_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            return datetime.fromisoformat(f"{value}T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _resource_id(resource: dict[str, Any], fallback: str) -> str:
    value = resource.get("id")
    return value if isinstance(value, str) and value else fallback


def _evidence_id(prefix: str, patient_id: str, source_id: str) -> str:
    raw = f"ev_{prefix}_{patient_id}_{source_id}".lower()
    return sub(r"[^a-z0-9_]+", "_", raw).strip("_")


def _source_url(resource_type: str, resource_id: str, patient_id: str | None = None) -> str:
    url = f"/api/source/openemr/{resource_type}/{resource_id}"
    if patient_id is not None:
        return f"{url}?patient_id={patient_id}"
    return url
