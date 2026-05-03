from typing import Any, cast

import pytest

from app.evidence_tools import (
    FhirEvidenceService,
    allergy_intolerance_evidence,
    condition_evidence,
    document_reference_evidence,
    lab_observation_evidence,
    medication_request_evidence,
    patient_demographics_evidence,
)
from app.fhir_client import OpenEMRFhirClient


def test_patient_demographics_evidence_uses_patient_resource_fields() -> None:
    evidence = patient_demographics_evidence(
        {
            "resourceType": "Patient",
            "id": "p1",
            "name": [{"given": ["Jane"], "family": "Moran"}],
            "birthDate": "1975-04-12",
            "gender": "female",
        }
    )

    assert [item.display_name for item in evidence] == [
        "Patient name",
        "Patient birth date",
        "Patient gender",
    ]
    assert evidence[0].patient_id == "p1"
    assert evidence[0].fact == "Patient name is Jane Moran."
    assert evidence[1].effective_at is not None
    assert evidence[0].source_url == "/api/source/openemr/Patient/p1"


def test_condition_evidence_extracts_active_problem_display_and_dates() -> None:
    evidence = condition_evidence(
        {
            "resourceType": "Condition",
            "id": "c1",
            "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
            "code": {"text": "Type 2 diabetes mellitus"},
            "recordedDate": "2026-02-01T14:30:00Z",
        },
        patient_id="p1",
    )

    assert evidence.evidence_id == "ev_condition_p1_c1"
    assert evidence.source_type == "active_problem"
    assert evidence.fact == "Active problem: Type 2 diabetes mellitus."
    assert evidence.effective_at is not None
    assert evidence.metadata["clinical_status"] == "Active"
    assert evidence.source_url == "/api/source/openemr/Condition/c1?patient_id=p1"


def test_lab_observation_evidence_extracts_value_and_abnormal_interpretation() -> None:
    evidence = lab_observation_evidence(
        {
            "resourceType": "Observation",
            "id": "o1",
            "status": "final",
            "code": {"text": "Hemoglobin A1c"},
            "valueQuantity": {"value": 8.6, "unit": "%"},
            "effectiveDateTime": "2026-03-12T00:00:00Z",
            "interpretation": [{"coding": [{"code": "H", "display": "High"}]}],
        },
        patient_id="p1",
    )

    assert evidence.evidence_id == "ev_observation_p1_o1"
    assert evidence.display_name == "Hemoglobin A1c"
    assert evidence.fact == (
        "Hemoglobin A1c was 8.6 % on 2026-03-12T00:00:00Z. "
        "OpenEMR marked the result as abnormal."
    )
    assert evidence.metadata["abnormal"] is True
    assert evidence.source_url == "/api/source/openemr/Observation/o1?patient_id=p1"


def test_medication_request_evidence_extracts_medication_and_sig() -> None:
    evidence = medication_request_evidence(
        {
            "resourceType": "MedicationRequest",
            "id": "m1",
            "status": "active",
            "medicationCodeableConcept": {"text": "Metformin 1000 mg tablet"},
            "authoredOn": "2026-01-10T00:00:00Z",
            "dosageInstruction": [{"text": "Take one tablet twice daily."}],
        },
        patient_id="p1",
    )

    assert evidence.evidence_id == "ev_medication_request_p1_m1"
    assert evidence.source_type == "medication"
    assert evidence.display_name == "Metformin 1000 mg tablet"
    assert evidence.fact == (
        "Medication request (active): Metformin 1000 mg tablet. "
        "Sig: Take one tablet twice daily. Authored on 2026-01-10T00:00:00Z."
    )
    assert evidence.source_url == "/api/source/openemr/MedicationRequest/m1?patient_id=p1"


def test_allergy_intolerance_evidence_extracts_reaction_and_status() -> None:
    evidence = allergy_intolerance_evidence(
        {
            "resourceType": "AllergyIntolerance",
            "id": "a1",
            "clinicalStatus": {"coding": [{"display": "Active"}]},
            "verificationStatus": {"coding": [{"display": "Confirmed"}]},
            "code": {"text": "Penicillin"},
            "recordedDate": "2026-02-02",
            "reaction": [{"manifestation": [{"text": "Rash"}]}],
        },
        patient_id="p1",
    )

    assert evidence.evidence_id == "ev_allergy_intolerance_p1_a1"
    assert evidence.source_type == "allergy"
    assert evidence.fact == (
        "Allergy/intolerance: Penicillin. Clinical status: Active. "
        "Verification: Confirmed. Reaction: Rash. Recorded on 2026-02-02."
    )
    assert evidence.source_url == "/api/source/openemr/AllergyIntolerance/a1?patient_id=p1"


def test_document_reference_evidence_decodes_plain_text_attachment() -> None:
    evidence = document_reference_evidence(
        {
            "resourceType": "DocumentReference",
            "id": "d1",
            "status": "current",
            "type": {"text": "Progress Note"},
            "date": "2026-04-24T14:20:00Z",
            "subject": {"reference": "Patient/p1"},
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": (
                            "U3ViamVjdGl2ZTogcGF0aWVudCByZXBvcnRzIGltcHJvdmVkIGJyZWF0aGluZy4g"
                            "QXNzZXNzbWVudDogYXN0aG1hIHN5bXB0b21zIHN0YWJsZS4="
                        ),
                    }
                }
            ],
        },
        patient_id="p1",
    )

    assert evidence.evidence_id == "ev_document_reference_p1_d1"
    assert evidence.source_type == "clinical_note"
    assert evidence.display_name == "Progress Note"
    assert "patient reports improved breathing" in evidence.fact
    assert evidence.metadata["content_type"] == "text/plain"
    assert evidence.source_url == "/api/source/openemr/DocumentReference/d1?patient_id=p1"


@pytest.mark.asyncio
async def test_collect_for_question_runs_only_demographics_for_demographics_question() -> None:
    client = _FakeFhirClient()
    service = FhirEvidenceService(cast(OpenEMRFhirClient, client))

    result = await service.collect_for_question(
        patient_id="p1",
        message="What is the patient's name and date of birth?",
    )

    assert result.tools == ["get_patient_demographics"]
    assert len(result.evidence) == 2
    assert client.calls == ["get_patient"]


@pytest.mark.asyncio
async def test_collect_for_question_runs_all_core_tools_for_broad_brief() -> None:
    client = _FakeFhirClient()
    service = FhirEvidenceService(cast(OpenEMRFhirClient, client))

    result = await service.collect_for_question(
        patient_id="p1",
        message="What should I know before seeing this patient?",
    )

    assert result.tools == [
        "get_patient_demographics",
        "get_active_problems",
        "get_recent_labs",
        "get_recent_notes",
    ]
    assert [item.source_type for item in result.evidence] == [
        "patient_demographics",
        "patient_demographics",
        "active_problem",
        "lab_result",
        "clinical_note",
    ]
    assert client.calls == [
        "get_patient",
        "search_active_conditions",
        "search_lab_observations",
        "search_document_references",
    ]


@pytest.mark.asyncio
async def test_collect_for_question_runs_medication_and_allergy_tools_when_requested() -> None:
    client = _FakeFhirClient()
    service = FhirEvidenceService(cast(OpenEMRFhirClient, client))

    result = await service.collect_for_question(
        patient_id="p1",
        message="Show current medications and allergies.",
    )

    assert result.tools == ["get_patient_demographics", "get_medications", "get_allergies"]
    assert [item.source_type for item in result.evidence] == [
        "patient_demographics",
        "patient_demographics",
        "medication",
        "allergy",
    ]
    assert client.calls == [
        "get_patient",
        "search_medication_requests",
        "search_allergy_intolerances",
    ]


@pytest.mark.asyncio
async def test_collect_for_question_runs_note_tool_when_requested() -> None:
    client = _FakeFhirClient()
    service = FhirEvidenceService(cast(OpenEMRFhirClient, client))

    result = await service.collect_for_question(
        patient_id="p1",
        message="Summarize recent clinical notes for this patient.",
    )

    assert result.tools == ["get_patient_demographics", "get_recent_notes"]
    assert [item.source_type for item in result.evidence] == [
        "patient_demographics",
        "patient_demographics",
        "clinical_note",
    ]
    assert client.calls == ["get_patient", "search_document_references"]


class _FakeFhirClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_patient(self, patient_id: str) -> dict[str, Any]:
        self.calls.append("get_patient")
        return {
            "resourceType": "Patient",
            "id": patient_id,
            "name": [{"given": ["Jane"], "family": "Moran"}],
            "birthDate": "1975-04-12",
        }

    async def search_active_conditions(self, patient_id: str) -> list[dict[str, Any]]:
        self.calls.append("search_active_conditions")
        return [
            {
                "resourceType": "Condition",
                "id": "c1",
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "code": {"text": "Type 2 diabetes mellitus"},
            }
        ]

    async def search_lab_observations(self, patient_id: str) -> list[dict[str, Any]]:
        self.calls.append("search_lab_observations")
        return [
            {
                "resourceType": "Observation",
                "id": "o1",
                "code": {"text": "Hemoglobin A1c"},
                "valueQuantity": {"value": 8.6, "unit": "%"},
                "effectiveDateTime": "2026-03-12T00:00:00Z",
            }
        ]

    async def search_medication_requests(self, patient_id: str) -> list[dict[str, Any]]:
        self.calls.append("search_medication_requests")
        return [
            {
                "resourceType": "MedicationRequest",
                "id": "m1",
                "status": "active",
                "medicationCodeableConcept": {"text": "Metformin 1000 mg tablet"},
            }
        ]

    async def search_allergy_intolerances(self, patient_id: str) -> list[dict[str, Any]]:
        self.calls.append("search_allergy_intolerances")
        return [
            {
                "resourceType": "AllergyIntolerance",
                "id": "a1",
                "code": {"text": "Penicillin"},
            }
        ]

    async def search_document_references(self, patient_id: str) -> list[dict[str, Any]]:
        self.calls.append("search_document_references")
        return [
            {
                "resourceType": "DocumentReference",
                "id": "d1",
                "type": {"text": "Progress Note"},
                "date": "2026-04-24T14:20:00Z",
                "content": [
                    {
                        "attachment": {
                            "contentType": "text/plain",
                            "data": (
                                "U3ViamVjdGl2ZTogcGF0aWVudCByZXBvcnRzIGltcHJvdmVkIGJyZWF0aGluZy4g"
                                "QXNzZXNzbWVudDogYXN0aG1hIHN5bXB0b21zIHN0YWJsZS4="
                            ),
                        }
                    }
                ],
            }
        ]
