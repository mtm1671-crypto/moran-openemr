import base64
import json
from collections.abc import Generator
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings, get_settings
from app.document_storage import reset_document_workflow_store
from app.api import _retrieve_evidence
from app.main import app
from app.models import ChatRequest, EvidenceObject, RequestUser, Role
from app.openemr_auth import clear_dev_password_token_cache


@pytest.fixture(autouse=True)
def reset_app_state() -> Generator[None]:
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    reset_document_workflow_store()
    settings = Settings(app_env="local", dev_auth_bypass=True)
    app.dependency_overrides[get_settings] = lambda: settings
    yield
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    reset_document_workflow_store()


def test_attach_review_and_write_lab_document() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="lab_pdf",
            content="""
            Patient: Synthetic Demo
            Collection Date: 2026-03-12
            Hemoglobin A1c 8.6 % reference range 4.0-5.6 H
            LDL Cholesterol 142 mg/dL reference range 0-99 H
            """,
        ),
    )

    assert response.status_code == 202
    body = response.json()
    job_id = body["job"]["job_id"]
    assert body["job"]["status"] == "review_required"
    assert body["fact_counts"] == {"review_required": 2}

    review = client.get(f"/api/documents/{job_id}/review").json()
    fact_ids = [fact["fact_id"] for fact in review["facts"]]
    assert review["facts"][0]["citation"]["bbox"]["page"] == 1

    decision_response = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact_id, "action": "approve"} for fact_id in fact_ids]},
    )

    assert decision_response.status_code == 200
    assert decision_response.json()["job"]["status"] == "ready_to_write"
    assert decision_response.json()["fact_counts"] == {"approved": 2}

    write_response = client.post(f"/api/documents/{job_id}/write")

    assert write_response.status_code == 200
    write_body = write_response.json()
    assert write_body["written_count"] == 2
    assert write_body["failed_count"] == 0
    assert write_body["job"]["status"] == "completed"
    assert all(fact["status"] == "written" for fact in write_body["facts"])
    assert all(fact["written_resource_id"].startswith("demo-observation-") for fact in write_body["facts"])


@respx.mock
def test_write_failure_reports_missing_observation_write_scope() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(200, json={"resourceType": "Patient", "id": "p1"})
    )
    observation_route = respx.post("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(
            403,
            json={
                "resourceType": "OperationOutcome",
                "issue": [{"code": "forbidden", "diagnostics": "insufficient_scope"}],
            },
        )
    )
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="lab_pdf",
            content="Hemoglobin A1c 8.6 % reference range 4.0-5.6 H",
        ),
        headers={"Authorization": "Bearer user-token"},
    )
    job_id = upload.json()["job"]["job_id"]
    fact_id = client.get(
        f"/api/documents/{job_id}/review",
        headers={"Authorization": "Bearer user-token"},
    ).json()["facts"][0]["fact_id"]
    client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact_id, "action": "approve"}]},
        headers={"Authorization": "Bearer user-token"},
    )

    write = client.post(
        f"/api/documents/{job_id}/write",
        headers={"Authorization": "Bearer user-token"},
    )

    assert write.status_code == 200
    body = write.json()
    assert body["written_count"] == 0
    assert body["failed_count"] == 1
    assert body["facts"][0]["status"] == "write_failed"
    assert body["facts"][0]["write_error"] == (
        "OpenEMR write denied (HTTP 403): "
        "re-authorize with user/Observation.write scope: insufficient_scope"
    )
    assert observation_route.calls[0].request.headers["authorization"] == "Bearer user-token"

    observation_route.mock(return_value=Response(201, json={"resourceType": "Observation", "id": "obs-retry"}))
    retry = client.post(
        f"/api/documents/{job_id}/write",
        headers={"Authorization": "Bearer user-token"},
    )

    assert retry.status_code == 200
    retry_body = retry.json()
    assert retry_body["written_count"] == 1
    assert retry_body["failed_count"] == 0
    assert retry_body["facts"][0]["status"] == "written"
    assert retry_body["facts"][0]["written_resource_id"] == "obs-retry"


def test_unassigned_document_can_extract_but_not_approve_or_write() -> None:
    client = TestClient(app)
    payload = _document_payload(
        doc_type="lab_pdf",
        content="""
        Patient: Unmatched Example
        Collection Date: 2026-04-18
        Hemoglobin A1c 8.2 % reference range 4.0-5.6 H
        """,
    )
    payload.pop("patient_id")

    response = client.post("/api/documents/attach-and-extract", json=payload)

    assert response.status_code == 202
    body = response.json()
    job_id = body["job"]["job_id"]
    assert body["job"]["patient_id"] is None
    assert body["job"]["status"] == "review_required"

    review = client.get(f"/api/documents/{job_id}/review")
    assert review.status_code == 200
    facts = review.json()["facts"]
    assert facts[0]["patient_id"] is None
    assert facts[0]["display_label"] == "Hemoglobin A1c"

    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": facts[0]["fact_id"], "action": "approve"}]},
    )
    assert approve.status_code == 422
    assert approve.json()["detail"] == "Assign the document to a patient before approving extracted facts"

    write = client.post(f"/api/documents/{job_id}/write")
    assert write.status_code == 422
    assert write.json()["detail"] == "Assign the document to a patient before writing extracted facts"

    evidence = client.get("/api/documents/patients/p1/approved-evidence")
    assert evidence.status_code == 200
    assert evidence.json()["evidence_count"] == 0


def test_unassigned_document_can_be_rejected_to_close_review() -> None:
    client = TestClient(app)
    payload = _document_payload(
        doc_type="lab_pdf",
        content="Hemoglobin A1c 8.2 % reference range 4.0-5.6 H",
    )
    payload.pop("patient_id")
    upload = client.post("/api/documents/attach-and-extract", json=payload)
    job_id = upload.json()["job"]["job_id"]
    fact_id = client.get(f"/api/documents/{job_id}/review").json()["facts"][0]["fact_id"]

    reject = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact_id, "action": "reject"}]},
    )

    assert reject.status_code == 200
    assert reject.json()["job"]["status"] == "completed"
    assert reject.json()["facts"][0]["status"] == "rejected"


def test_approved_intake_facts_are_available_as_source_backed_chat_evidence() -> None:
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="intake_form",
            filename="intake.txt",
            content="""
            Chief Concern: Follow up for diabetes and fatigue
            Medications: Metformin 1000 mg twice daily
            Allergies: Penicillin - rash
            Social History: Misses doses when work shifts change
            """,
        ),
    )
    assert upload.status_code == 202
    job_id = upload.json()["job"]["job_id"]
    review = client.get(f"/api/documents/{job_id}/review").json()
    social_fact = next(
        fact for fact in review["facts"] if fact["display_label"] == "Social history"
    )

    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": social_fact["fact_id"], "action": "approve"}]},
    )
    assert approve.status_code == 200

    evidence = client.get("/api/documents/patients/p1/approved-evidence").json()
    assert evidence["evidence_count"] == 1
    assert "Misses doses when work shifts change" in evidence["evidence"][0]["fact"]

    chat = client.post(
        "/api/chat",
        json={"patient_id": "p1", "message": "What social barriers are documented?"},
    )
    final = _final_event(chat.text)

    assert chat.status_code == 200
    assert "Misses doses when work shifts change" in final["answer"]
    assert "approved_document_evidence" in final["audit"]["tools"]


@respx.mock
def test_document_upload_requires_openemr_patient_access() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    patient_route = respx.get("http://openemr.test/apis/default/fhir/Patient/p-denied").mock(
        return_value=Response(403, json={"error": "forbidden"})
    )

    response = TestClient(app).post(
        "/api/documents/attach-and-extract",
        json={
            **_document_payload(doc_type="lab_pdf", content="Hemoglobin A1c 8.6 % H"),
            "patient_id": "p-denied",
        },
        headers={"Authorization": "Bearer user-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "OpenEMR patient access denied"
    assert patient_route.calls[0].request.headers["authorization"] == "Bearer user-token"


@pytest.mark.asyncio
async def test_approved_document_evidence_is_included_in_vector_index_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="intake_form",
            filename="intake.txt",
            content="Social History: Misses doses when work shifts change",
        ),
    )
    job_id = upload.json()["job"]["job_id"]
    review = client.get(f"/api/documents/{job_id}/review").json()
    fact_id = review["facts"][0]["fact_id"]
    client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact_id, "action": "approve"}]},
    )

    captured: dict[str, list[EvidenceObject]] = {}

    async def fake_search_patient_evidence(**_kwargs: object) -> list[EvidenceObject]:
        return []

    async def fake_index_and_search_evidence(**kwargs: object) -> list[EvidenceObject]:
        evidence = kwargs["evidence"]
        assert isinstance(evidence, list)
        captured["evidence"] = evidence
        return evidence

    monkeypatch.setattr("app.api.search_patient_evidence", fake_search_patient_evidence)
    monkeypatch.setattr("app.api.index_and_search_evidence", fake_index_and_search_evidence)

    retrieval = await _retrieve_evidence(
        request=ChatRequest(patient_id="p1", message="What social barriers are documented?"),
        user=RequestUser(user_id="dev-doctor", role=Role.doctor),
        settings=Settings(app_env="local", dev_auth_bypass=True, vector_search_enabled=True),
    )

    assert "index_patient_evidence" in retrieval.tools
    assert any(
        "Misses doses when work shifts change" in item.fact
        for item in captured["evidence"]
    )


def _document_payload(
    *,
    doc_type: str,
    content: str,
    filename: str = "synthetic.txt",
) -> dict[str, str]:
    return {
        "patient_id": "p1",
        "doc_type": doc_type,
        "filename": filename,
        "content_type": "text/plain",
        "content_base64": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }


def _final_event(stream_text: str) -> dict[str, Any]:
    for event in stream_text.split("\n\n"):
        if event.startswith("event: final"):
            data_line = next(line for line in event.splitlines() if line.startswith("data: "))
            payload = json.loads(data_line.removeprefix("data: "))
            assert isinstance(payload, dict)
            return payload
    raise AssertionError("No final SSE event found")
