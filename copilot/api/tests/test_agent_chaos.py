import asyncio
import base64
import json
from collections import Counter
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.auth import get_request_user
from app.config import Settings, get_settings
from app.document_storage import reset_document_workflow_store
from app.main import app
from app.models import Citation, RequestUser, Role, VerifiedAnswer
from app.openemr_auth import clear_dev_password_token_cache

TEST_FERNET_KEY = "PAAhZkguTNgLSk3R268DyJ-Lu6c_M4_87k7s2Prrt_8="


@pytest.fixture(autouse=True)
def reset_app_state() -> Generator[None]:
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    reset_document_workflow_store()
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="local", dev_auth_bypass=True)
    yield
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    reset_document_workflow_store()


def test_agent_document_flow_survives_bad_inputs_duplicates_and_chat_pressure() -> None:
    client = TestClient(app)

    bad_base64 = client.post(
        "/api/documents/attach-and-extract",
        json={
            "patient_id": "p-chaos",
            "doc_type": "intake_form",
            "filename": "bad.txt",
            "content_type": "text/plain",
            "content_base64": "not-base64",
        },
    )
    unsupported_type = client.post(
        "/api/documents/attach-and-extract",
        json={
            **_document_payload("Social History: Misses doses when work shifts change"),
            "content_type": "image/png",
        },
    )
    unreadable_doc = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload("   \n   "),
    )

    assert bad_base64.status_code == 400
    assert unsupported_type.status_code == 422
    assert unreadable_doc.status_code == 422

    upload_payload = _document_payload("Social History: Misses doses when work shifts change")
    with ThreadPoolExecutor(max_workers=8) as executor:
        uploads = list(executor.map(_post_upload, [upload_payload] * 24))

    assert {response.status_code for response in uploads} == {202}
    job_ids = {response.json()["job"]["job_id"] for response in uploads}
    assert len(job_ids) == 1
    job_id = next(iter(job_ids))

    review = client.get(f"/api/documents/{job_id}/review")
    assert review.status_code == 200
    review_body = review.json()
    facts = review_body["facts"]
    assert len(facts) == 1
    assert facts[0]["blocking_reasons"] == []
    assert review_body["trace"].count("extracting_started") == 1

    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": facts[0]["fact_id"], "action": "approve"}]},
    )
    assert approve.status_code == 200

    for index in range(20):
        chat = client.post(
            "/api/chat",
            json={
                "patient_id": "p-chaos",
                "message": f"What social barriers are documented? run {index}",
            },
        )
        final = _final_event(chat.text)
        assert chat.status_code == 200
        assert final["audit"]["verification"] == "passed"
        assert "approved_document_evidence" in final["audit"]["tools"]
        assert "Misses doses when work shifts change" in final["answer"]


def test_agent_document_review_blocks_low_confidence_or_uncited_writes() -> None:
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload("Chief Concern: Needs a quick visit summary"),
    )
    assert upload.status_code == 202
    job_id = upload.json()["job"]["job_id"]
    fact = client.get(f"/api/documents/{job_id}/review").json()["facts"][0]

    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact["fact_id"], "action": "approve"}]},
    )
    assert approve.status_code == 200

    write = client.post(f"/api/documents/{job_id}/write")
    body = write.json()

    assert write.status_code == 200
    assert body["written_count"] == 0
    assert body["skipped_count"] == 1
    assert body["failed_count"] == 0
    assert body["job"]["status"] == "completed"


def test_agent_chat_pressure_does_not_cross_patient_document_evidence() -> None:
    client = TestClient(app)
    _upload_and_approve_intake(
        client,
        patient_id="p-chaos-a",
        content="Social History: Cannot fill insulin when weekend shifts are cut",
    )
    _upload_and_approve_intake(
        client,
        patient_id="p-chaos-b",
        content="Social History: Relies on neighbor for rides to appointments",
    )

    requests = [
        ("p-chaos-a", "What social barriers are documented?")
        for _index in range(16)
    ] + [
        ("p-chaos-b", "What social barriers are documented?")
        for _index in range(16)
    ]
    with ThreadPoolExecutor(max_workers=12) as executor:
        responses = list(executor.map(_post_chat, requests))

    assert len(responses) == 32
    for patient_id, final in responses:
        assert final["audit"]["verification"] == "passed"
        assert "approved_document_evidence" in final["audit"]["tools"]
        if patient_id == "p-chaos-a":
            assert "weekend shifts are cut" in final["answer"]
            assert "neighbor for rides" not in final["answer"]
        else:
            assert "neighbor for rides" in final["answer"]
            assert "weekend shifts are cut" not in final["answer"]


def test_agent_verifier_suppresses_hallucinated_provider_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HallucinatingProvider:
        async def answer(
            self,
            *,
            patient_id: str,
            user_message: str,
            evidence: list[Any],
        ) -> VerifiedAnswer:
            return VerifiedAnswer(
                answer="The patient has undocumented sepsis and needs escalation.",
                citations=[
                    Citation(
                        evidence_id="ev_not_in_context",
                        label="Nonexistent source",
                        source_url="/api/source/openemr/Observation/not-real",
                    )
                ],
                audit={
                    "patient_id": patient_id,
                    "provider": "hallucination_probe",
                    "verification": "pending",
                    "requested": user_message,
                },
            )

    monkeypatch.setattr("app.api._provider_for_settings", lambda _settings: HallucinatingProvider())

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "demo-diabetes-001", "message": "What were the recent labs?"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert final["answer"] == (
        "I could not verify the answer against selected-patient evidence, so I am not showing it."
    )
    assert final["citations"] == []
    assert final["audit"]["verification"] == "failed"
    assert "undocumented sepsis" not in final["answer"]


@respx.mock
def test_agent_retries_transient_openemr_failures_then_recovers() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
        openemr_retry_attempts=2,
        openemr_retry_backoff_seconds=0,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/Patient/p-retry").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Patient",
                "id": "p-retry",
                "name": [{"given": ["Retry"], "family": "Patient"}],
            },
        )
    )
    condition_route = respx.get("http://openemr.test/apis/default/fhir/Condition").mock(
        side_effect=[
            Response(500, json={"resourceType": "OperationOutcome"}),
            Response(
                200,
                json={
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Condition",
                                "id": "c-retry",
                                "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
                                "code": {"text": "Type 2 diabetes mellitus"},
                            }
                        }
                    ],
                },
            ),
        ]
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "p-retry", "message": "Summarize problem history."},
        headers={"Authorization": "Bearer user-token"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert condition_route.call_count == 2
    assert final["audit"]["verification"] == "passed"
    assert "Type 2 diabetes mellitus" in final["answer"]


@respx.mock
def test_agent_returns_safe_failure_after_openemr_timeout() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
        openemr_retry_attempts=1,
        openemr_retry_backoff_seconds=0,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/Patient/p-timeout").mock(
        side_effect=httpx.ReadTimeout("synthetic timeout")
    )

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "p-timeout", "message": "Summarize problem history."},
        headers={"Authorization": "Bearer user-token"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert final["answer"] == "I could not retrieve source-backed OpenEMR evidence for this patient."
    assert final["citations"] == []
    assert final["audit"]["verification"] == "failed"
    assert final["audit"]["error"] == "fhir_retrieval_failed"


def test_agent_document_write_is_idempotent_under_concurrent_pressure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            """
            Patient: Synthetic Demo
            Collection Date: 2026-03-12
            Hemoglobin A1c 8.6 % reference range 4.0-5.6 H
            """,
            doc_type="lab_pdf",
        ),
    )
    assert upload.status_code == 202
    job_id = upload.json()["job"]["job_id"]
    facts = client.get(f"/api/documents/{job_id}/review").json()["facts"]
    client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact["fact_id"], "action": "approve"} for fact in facts]},
    )

    call_count = 0
    call_lock = Lock()

    async def slow_write_lab_fact_observation(**_kwargs: Any) -> str:
        nonlocal call_count
        await asyncio.sleep(0.05)
        with call_lock:
            call_count += 1
            return f"obs-pressure-{call_count}"

    monkeypatch.setattr(
        "app.document_ingestion.write_lab_fact_observation",
        slow_write_lab_fact_observation,
    )

    barrier = Barrier(8)
    with ThreadPoolExecutor(max_workers=8) as executor:
        writes = list(executor.map(_post_write_with_barrier, [(job_id, barrier)] * 8))

    statuses = Counter(response.status_code for response in writes)
    successful_writes = [response.json() for response in writes if response.status_code == 200]

    assert set(statuses).issubset({200, 409})
    assert statuses[409] >= 1
    assert sum(body["written_count"] for body in successful_writes) == 1
    assert call_count == 1

    final_review = client.get(f"/api/documents/{job_id}/review").json()
    assert final_review["job"]["status"] == "completed"
    assert final_review["facts"][0]["status"] == "written"
    assert final_review["facts"][0]["written_resource_id"] == "obs-pressure-1"


@respx.mock
def test_source_link_direct_read_does_not_leak_wrong_patient_resource() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/Observation/o-other").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Observation",
                "id": "o-other",
                "subject": {"reference": "Patient/p-other"},
                "code": {"text": "Hemoglobin A1c"},
            },
        )
    )

    response = TestClient(app).get("/api/source/openemr/Observation/o-other?patient_id=p1")

    assert response.status_code == 404
    assert response.json()["detail"] == "OpenEMR source was not found"


def test_phi_audit_persistence_failure_hides_verified_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        app_env="phi",
        phi_mode=True,
        dev_auth_bypass=False,
        database_url="postgresql://copilot:secret@db.example.test:5432/copilot",
        encryption_key=TEST_FERNET_KEY,
        conversation_persistence_enabled=False,
        audit_persistence_required=True,
        openemr_fhir_base_url=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_request_user] = lambda: RequestUser(
        user_id="doctor-1",
        role=Role.doctor,
        scopes=["user/Patient.read"],
    )

    async def fail_audit_write(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr("app.api.write_audit_event", fail_audit_write)

    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": "demo-diabetes-001", "message": "What were the recent labs?"},
    )
    final = _final_event(response.text)

    assert response.status_code == 200
    assert "Demo A1c" not in final["answer"]
    assert final["citations"] == []
    assert final["audit"]["verification"] == "failed"
    assert final["audit"]["error"] == "audit_persistence_failed"


def _post_upload(payload: dict[str, str]) -> Any:
    return TestClient(app).post("/api/documents/attach-and-extract", json=payload)


def _post_chat(request: tuple[str, str]) -> tuple[str, dict[str, Any]]:
    patient_id, message = request
    response = TestClient(app).post(
        "/api/chat",
        json={"patient_id": patient_id, "message": message},
    )
    assert response.status_code == 200
    return patient_id, _final_event(response.text)


def _post_write_with_barrier(request: tuple[str, Barrier]) -> Any:
    job_id, barrier = request
    barrier.wait(timeout=5)
    return TestClient(app).post(f"/api/documents/{job_id}/write")


def _upload_and_approve_intake(
    client: TestClient,
    *,
    patient_id: str,
    content: str,
) -> str:
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(content, patient_id=patient_id, filename=f"{patient_id}.txt"),
    )
    assert upload.status_code == 202
    job_id = upload.json()["job"]["job_id"]
    facts = client.get(f"/api/documents/{job_id}/review").json()["facts"]
    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact["fact_id"], "action": "approve"} for fact in facts]},
    )
    assert approve.status_code == 200
    return job_id


def _document_payload(
    content: str,
    *,
    patient_id: str = "p-chaos",
    doc_type: str = "intake_form",
    filename: str = "chaos-intake.txt",
) -> dict[str, str]:
    return {
        "patient_id": patient_id,
        "doc_type": doc_type,
        "filename": filename,
        "content_type": "text/plain",
        "content_base64": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }


def _final_event(stream_text: str) -> dict[str, Any]:
    for event in stream_text.split("\n\n"):
        if event.startswith("event: final"):
            data_line = next(line for line in event.splitlines() if line.startswith("data: "))
            return json.loads(data_line.removeprefix("data: "))
    raise AssertionError("No final SSE event found")
