import json
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings, get_settings
from app.main import app
from app.openemr_auth import clear_dev_password_token_cache


@pytest.fixture(autouse=True)
def reset_app_overrides() -> None:
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    yield
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()


@respx.mock
def test_chat_uses_openemr_evidence_tools_and_returns_verified_sources() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    patient_route = respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Patient",
                "id": "p1",
                "name": [{"given": ["Jane"], "family": "Moran"}],
                "birthDate": "1975-04-12",
                "gender": "female",
            },
        )
    )
    condition_route = respx.get("http://openemr.test/apis/default/fhir/Condition").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": "c1",
                            "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
                            "code": {"text": "Type 2 diabetes mellitus"},
                            "recordedDate": "2026-02-01",
                        }
                    }
                ],
            },
        )
    )
    observation_route = respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "id": "o1",
                            "status": "final",
                            "code": {"text": "Hemoglobin A1c"},
                            "valueQuantity": {"value": 8.6, "unit": "%"},
                            "effectiveDateTime": "2026-03-12T00:00:00Z",
                            "interpretation": [{"coding": [{"code": "H", "display": "High"}]}],
                        }
                    }
                ],
            },
        )
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "p1", "message": "What should I know before seeing this patient?"},
        headers={"Authorization": "Bearer user-token"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert "Demo A1c" not in final["answer"]
    assert "Jane Moran" in final["answer"]
    assert "Type 2 diabetes mellitus" in final["answer"]
    assert "Hemoglobin A1c was 8.6 %" in final["answer"]
    assert final["audit"]["verification"] == "passed"
    assert final["audit"]["tools"] == [
        "get_patient_demographics",
        "get_active_problems",
        "get_recent_labs",
    ]
    assert len(final["citations"]) == 5
    assert patient_route.calls[0].request.headers["authorization"] == "Bearer user-token"
    assert condition_route.calls[0].request.url.params["patient"] == "p1"
    assert observation_route.calls[0].request.url.params["_sort"] == "-date"


@respx.mock
def test_chat_returns_safe_failure_when_openemr_denies_evidence_access() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(403, json={"error": "forbidden"})
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "p1", "message": "What is the patient name?"},
        headers={"Authorization": "Bearer user-token"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert final["answer"] == "I could not retrieve source-backed OpenEMR evidence for this patient."
    assert final["citations"] == []
    assert final["audit"]["verification"] == "failed"
    assert final["audit"]["error"] == "fhir_access_denied"
    assert final["audit"]["status_code"] == 403


@respx.mock
def test_chat_returns_medication_and_allergy_evidence_when_requested() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Patient",
                "id": "p1",
                "name": [{"given": ["Jane"], "family": "Moran"}],
            },
        )
    )
    medication_route = respx.get("http://openemr.test/apis/default/fhir/MedicationRequest").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": "m1",
                            "status": "active",
                            "medicationCodeableConcept": {"text": "Metformin 1000 mg tablet"},
                            "dosageInstruction": [{"text": "Take one tablet twice daily."}],
                        }
                    }
                ],
            },
        )
    )
    allergy_route = respx.get("http://openemr.test/apis/default/fhir/AllergyIntolerance").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "AllergyIntolerance",
                            "id": "a1",
                            "code": {"text": "Penicillin"},
                            "reaction": [{"manifestation": [{"text": "Rash"}]}],
                        }
                    }
                ],
            },
        )
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "p1", "message": "Show current medications and allergies."},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert "Metformin 1000 mg tablet" in final["answer"]
    assert "Penicillin" in final["answer"]
    assert final["audit"]["verification"] == "passed"
    assert final["audit"]["tools"] == [
        "get_patient_demographics",
        "get_medications",
        "get_allergies",
    ]
    assert medication_route.calls[0].request.url.params["status"] == "active"
    assert allergy_route.calls[0].request.url.params["patient"] == "p1"


def test_chat_refuses_treatment_recommendation_requests() -> None:
    settings = Settings(app_env="local", dev_auth_bypass=True, openemr_fhir_base_url=None)
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).post(
        "/api/chat",
        json={
            "patient_id": "demo-diabetes-001",
            "message": "What medication changes should I make?",
        },
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert "can't recommend medication changes" in final["answer"]
    assert final["citations"] == []
    assert final["audit"]["verification"] == "refused_treatment_recommendation"


def test_chat_uses_demo_fallback_when_openemr_fhir_is_not_configured() -> None:
    settings = Settings(app_env="local", dev_auth_bypass=True, openemr_fhir_base_url=None)
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "demo-diabetes-001", "message": "What were the recent labs?"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert "Demo A1c was 8.6%" in final["answer"]
    assert final["audit"]["verification"] == "passed"
    assert final["audit"]["tools"] == ["demo_evidence"]


def _final_event(sse_text: str) -> dict[str, Any]:
    event_name: str | None = None
    for line in sse_text.splitlines():
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")
        if event_name == "final" and line.startswith("data: "):
            payload = json.loads(line.removeprefix("data: "))
            assert isinstance(payload, dict)
            return payload
    raise AssertionError(f"No final event in SSE response:\n{sse_text}")
