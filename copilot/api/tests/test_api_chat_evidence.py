from collections.abc import Generator
from datetime import UTC, datetime
import json
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.api import (
    _augment_with_vector_search_with_failover,
    _collect_evidence_with_cache,
    _evidence_cache_key,
    _retrieval_cache_payload,
    _retrieval_from_cache_payload,
)
from app.config import Settings, get_settings
from app.evidence_tools import EvidenceRetrievalResult
from app.main import app
from app.models import EvidenceObject, RequestUser, Role
from app.openemr_auth import clear_dev_password_token_cache
from app.vector_store import VectorStoreError

TEST_FERNET_KEY = "PAAhZkguTNgLSk3R268DyJ-Lu6c_M4_87k7s2Prrt_8="


@pytest.fixture(autouse=True)
def reset_app_overrides() -> Generator[None]:
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
    document_route = respx.get("http://openemr.test/apis/default/fhir/DocumentReference").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
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
    assert "patient reports improved breathing" in final["answer"]
    assert final["audit"]["verification"] == "passed"
    assert final["audit"]["tools"] == [
        "get_patient_demographics",
        "get_active_problems",
        "get_recent_labs",
        "get_recent_notes",
    ]
    assert len(final["citations"]) == 5
    assert patient_route.calls[0].request.headers["authorization"] == "Bearer user-token"
    assert condition_route.calls[0].request.url.params["patient"] == "p1"
    assert observation_route.calls[0].request.url.params["_sort"] == "-date"
    assert document_route.calls[0].request.url.params["category"] == "clinical-note"


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


@respx.mock
def test_chat_returns_recent_clinical_note_evidence_when_requested() -> None:
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
    document_route = respx.get("http://openemr.test/apis/default/fhir/DocumentReference").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
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
                        }
                    }
                ],
            },
        )
    )

    response = TestClient(app).post(
        "/api/chat",
        json={
            "patient_id": "p1",
            "message": "Summarize recent clinical notes for this patient.",
            "quick_question_id": "recent_notes",
        },
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert "Progress Note" in final["answer"]
    assert "asthma symptoms stable" in final["answer"]
    assert final["audit"]["verification"] == "passed"
    assert final["audit"]["tools"] == ["get_patient_demographics", "get_recent_notes"]
    assert final["citations"][1]["source_url"] == "/api/source/openemr/DocumentReference/d1?patient_id=p1"
    assert document_route.calls[0].request.url.params["patient"] == "p1"


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


def test_chat_uses_vector_search_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url=None,
        vector_search_enabled=True,
        database_url="postgresql://copilot:secret@db.example.test:5432/copilot",
        encryption_key=TEST_FERNET_KEY,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    async def fake_index_and_search_evidence(**kwargs: Any) -> list[Any]:
        assert kwargs["patient_id"] == "demo-diabetes-001"
        assert kwargs["query"] == "What were the recent labs?"
        return list(kwargs["evidence"])

    monkeypatch.setattr("app.api.index_and_search_evidence", fake_index_and_search_evidence)

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "demo-diabetes-001", "message": "What were the recent labs?"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert "Demo A1c was 8.6%" in final["answer"]
    assert final["audit"]["verification"] == "passed"
    assert final["audit"]["tools"] == [
        "demo_evidence",
        "index_patient_evidence",
        "search_patient_evidence",
    ]


@pytest.mark.asyncio
async def test_vector_search_failure_falls_back_to_retrieved_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieval = EvidenceRetrievalResult(
        evidence=[
            EvidenceObject(
                evidence_id="ev1",
                patient_id="patient-1",
                source_type="lab_result",
                source_id="lab-1",
                display_name="A1c",
                fact="A1c was 8.6%.",
                retrieved_at=_now(),
            )
        ],
        tools=["get_recent_labs"],
    )

    async def fail_vector_search(**_kwargs: Any) -> EvidenceRetrievalResult:
        raise VectorStoreError("pgvector unavailable")

    monkeypatch.setattr("app.api._augment_with_vector_search", fail_vector_search)

    result = await _augment_with_vector_search_with_failover(
        settings=Settings(structured_logging_enabled=False),
        patient_id="patient-1",
        message="recent labs",
        retrieval=retrieval,
        service=None,
    )

    assert result.evidence == retrieval.evidence
    assert result.tools == ["get_recent_labs", "vector_search_unavailable"]
    assert "Vector search was unavailable" in result.limitations[0]


@pytest.mark.asyncio
async def test_evidence_cache_failure_falls_back_to_live_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = EvidenceObject(
        evidence_id="ev1",
        patient_id="patient-1",
        source_type="lab_result",
        source_id="lab-1",
        display_name="A1c",
        fact="A1c was 8.6%.",
        retrieved_at=_now(),
    )

    class FakeEvidenceService:
        async def collect_for_question(
            self,
            *,
            patient_id: str,
            message: str,
            quick_question_id: str | None = None,
        ) -> EvidenceRetrievalResult:
            assert patient_id == "patient-1"
            assert message == "recent labs"
            assert quick_question_id is None
            return EvidenceRetrievalResult(evidence=[evidence], tools=["get_recent_labs"])

    async def fail_cache_read(**_kwargs: Any) -> None:
        raise RuntimeError("cache read failed")

    async def fail_cache_write(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("cache write failed")

    monkeypatch.setattr("app.api.read_evidence_cache_record", fail_cache_read)
    monkeypatch.setattr("app.api.write_evidence_cache_record", fail_cache_write)

    result = await _collect_evidence_with_cache(
        settings=Settings(
            evidence_cache_enabled=True,
            database_url="postgresql://copilot:secret@db.example.test:5432/copilot",
            encryption_key=TEST_FERNET_KEY,
            structured_logging_enabled=False,
        ),
        user=RequestUser(user_id="doctor-1", role=Role.doctor),
        patient_id="patient-1",
        message="recent labs",
        quick_question_id=None,
        service=FakeEvidenceService(),  # type: ignore[arg-type]
    )

    assert result.evidence == [evidence]
    assert result.tools == ["get_recent_labs", "evidence_cache_unavailable"]
    assert "Evidence cache was unavailable" in result.limitations[0]


def test_evidence_cache_key_is_scoped_to_user_patient_and_question() -> None:
    user = RequestUser(user_id="doctor-1", role=Role.doctor, scopes=["user/Patient.read"])

    first = _evidence_cache_key(
        user=user,
        patient_id="patient-1",
        message="Recent labs?",
        quick_question_id="recent_labs",
    )
    second = _evidence_cache_key(
        user=user,
        patient_id="patient-2",
        message="Recent labs?",
        quick_question_id="recent_labs",
    )

    assert first != second
    assert "doctor-1" in first
    assert "patient-1" in first


def test_evidence_cache_payload_round_trips_retrieval_result() -> None:
    retrieval = EvidenceRetrievalResult(
        evidence=[
            EvidenceObject(
                evidence_id="ev1",
                patient_id="patient-1",
                source_type="lab_result",
                source_id="lab-1",
                display_name="A1c",
                fact="A1c was 8.6%.",
                retrieved_at=_now(),
                source_url="/api/source/openemr/Observation/lab-1?patient_id=patient-1",
            )
        ],
        tools=["get_recent_labs"],
        limitations=["No older labs were searched."],
    )

    restored = _retrieval_from_cache_payload(_retrieval_cache_payload(retrieval))

    assert restored.evidence[0].evidence_id == "ev1"
    assert restored.evidence[0].fact == "A1c was 8.6%."
    assert restored.tools == ["get_recent_labs"]
    assert restored.limitations == ["No older labs were searched."]


@respx.mock
def test_chat_can_use_openai_provider_after_evidence_retrieval() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url=None,
        llm_provider="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.openai.test/v1",
        openai_reasoning_effort="none",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.post("https://api.openai.test/v1/responses").mock(
        return_value=Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "answer": "Demo A1c was 8.6% on 2026-03-12.",
                        "evidence_ids": ["ev_demo_a1c"],
                        "reasoning_summary": "Used the cited demo lab evidence.",
                    }
                )
            },
        )
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "demo-diabetes-001", "message": "What were the recent labs?"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert final["answer"] == "Demo A1c was 8.6% on 2026-03-12."
    assert final["citations"][0]["evidence_id"] == "ev_demo_a1c"
    assert final["audit"]["provider"] == "openai"
    assert final["audit"]["verification"] == "passed"


@respx.mock
def test_chat_can_use_openrouter_provider_after_evidence_retrieval() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url=None,
        llm_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
        openrouter_demo_data_only=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.post("https://openrouter.test/api/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "answer": "Demo A1c was 8.6% on 2026-03-12.",
                                    "evidence_ids": ["ev_demo_a1c"],
                                    "reasoning_summary": "Used the cited demo lab evidence.",
                                }
                            ),
                        }
                    }
                ]
            },
        )
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "demo-diabetes-001", "message": "What were the recent labs?"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert final["answer"] == "Demo A1c was 8.6% on 2026-03-12."
    assert final["citations"][0]["evidence_id"] == "ev_demo_a1c"
    assert final["audit"]["provider"] == "openrouter"
    assert final["audit"]["verification"] == "passed"


@respx.mock
def test_chat_falls_back_to_source_backed_answer_when_model_output_is_invalid() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url=None,
        llm_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
        openrouter_demo_data_only=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.post("https://openrouter.test/api/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "The A1c was high, but this is not JSON.",
                        }
                    }
                ]
            },
        )
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "demo-diabetes-001", "message": "What were the recent labs?"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert "Demo A1c was 8.6%" in final["answer"]
    assert final["citations"][0]["evidence_id"] == "ev_demo_a1c"
    assert final["audit"]["provider"] == "source_backed_fallback"
    assert final["audit"]["llm_provider_failed"] == "openrouter"
    assert final["audit"]["verification"] == "passed"


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


def _now() -> datetime:
    return datetime.now(tz=UTC)
