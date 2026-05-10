import base64
import json
from collections.abc import Generator
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings, get_settings
from app.document_models import W2DocType, W2JobStatus
from app.document_storage import (
    create_document_workflow,
    document_workflow_snapshot,
    reset_document_workflow_store,
    update_document_job,
)
from app.api import _retrieve_evidence
from app.main import app
from app.models import ChatRequest, EvidenceObject, RequestUser, Role
from app.openemr_auth import clear_dev_password_token_cache


@pytest.fixture(autouse=True)
def reset_app_state() -> Generator[None]:
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    reset_document_workflow_store()
    settings = Settings(app_env="local", dev_auth_bypass=True, demo_auth_bypass=True)
    app.dependency_overrides[get_settings] = lambda: settings
    yield
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    reset_document_workflow_store()


def test_document_attach_fails_closed_without_fhir_when_demo_mode_is_disabled() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=False,
        openemr_fhir_base_url=None,
    )
    response = TestClient(app).post(
        "/api/documents/attach-and-extract",
        json=_document_payload(doc_type="lab_pdf", content="Hemoglobin A1c 8.6 % H"),
    )

    assert response.status_code == 503
    assert "real patient access cannot be verified" in response.json()["detail"]


def test_production_demo_document_routes_are_rejected() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="production",
        dev_auth_bypass=False,
        demo_auth_bypass=True,
        openemr_fhir_base_url=None,
    )
    response = TestClient(app).get("/api/documents/patients/demo-diabetes-001/approved-evidence")

    assert response.status_code == 503
    assert response.json()["detail"] == "DEMO_AUTH_BYPASS is local-only and cannot be used in production"


@respx.mock
def test_attach_review_and_write_lab_document() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=False,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    respx.get("http://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=True))
    )
    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(200, json={"resourceType": "Patient", "id": "p1"})
    )
    respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(200, json={"resourceType": "Bundle", "entry": []})
    )
    observation_create = respx.post("http://openemr.test/apis/default/fhir/Observation").mock(
        side_effect=[
            Response(201, json={"resourceType": "Observation", "id": "obs-a1c"}),
            Response(201, json={"resourceType": "Observation", "id": "obs-ldl"}),
        ]
    )
    client = TestClient(app)
    response = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="lab_pdf",
            content="""
            Patient: Margaret Chen
            Collection Date: 2026-03-12
            Hemoglobin A1c 8.6 % reference range 4.0-5.6 H
                LDL Cholesterol 142 mg/dL reference range 0-99 H
                """,
        ),
        headers={"Authorization": "Bearer user-token"},
    )

    assert response.status_code == 202
    body = response.json()
    job_id = body["job"]["job_id"]
    assert body["job"]["status"] == "review_required"
    assert body["fact_counts"] == {"review_required": 2}

    review = client.get(
        f"/api/documents/{job_id}/review",
        headers={"Authorization": "Bearer user-token"},
    ).json()
    fact_ids = [fact["fact_id"] for fact in review["facts"]]
    respx.get("http://openemr.test/apis/default/fhir/Observation/obs-a1c").mock(
        return_value=Response(200, json=_observation_resource("obs-a1c", "p1", fact_ids[0]))
    )
    respx.get("http://openemr.test/apis/default/fhir/Observation/obs-ldl").mock(
        return_value=Response(200, json=_observation_resource("obs-ldl", "p1", fact_ids[1]))
    )
    assert review["facts"][0]["citation"]["bbox"]["page"] == 1
    source = client.get(
        f"/api/documents/{job_id}/source-file",
        headers={"Authorization": "Bearer user-token"},
    )
    assert source.status_code == 200
    assert source.headers["content-type"].startswith("text/plain")
    assert b"Hemoglobin A1c 8.6" in source.content
    assert source.headers["x-document-source-sha256"] == body["job"]["source"]["source_sha256"]

    decision_response = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact_id, "action": "approve"} for fact_id in fact_ids]},
        headers={"Authorization": "Bearer user-token"},
    )

    assert decision_response.status_code == 200
    assert decision_response.json()["job"]["status"] == "ready_to_write"
    assert decision_response.json()["fact_counts"] == {"approved": 2}

    write_response = client.post(
        f"/api/documents/{job_id}/write",
        headers={"Authorization": "Bearer user-token"},
    )

    assert write_response.status_code == 200
    write_body = write_response.json()
    assert write_body["written_count"] == 2
    assert write_body["failed_count"] == 0
    assert write_body["job"]["status"] == "completed"
    assert all(fact["status"] == "written" for fact in write_body["facts"])
    assert [fact["written_resource_id"] for fact in write_body["facts"]] == ["obs-a1c", "obs-ldl"]
    assert observation_create.call_count == 2
    assert observation_create.calls[0].request.headers["authorization"] == "Bearer user-token"


@respx.mock
def test_observation_duplicate_search_404_allows_first_time_write() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=False,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    respx.get("http://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=True))
    )
    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(200, json={"resourceType": "Patient", "id": "p1"})
    )
    duplicate_search = respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(404, json=[])
    )
    observation_create = respx.post("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(201, json={"resourceType": "Observation", "id": "obs-total-cholesterol"})
    )
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="lab_pdf",
            content="Total Cholesterol 244 mg/dL reference range 0-199 H",
        ),
        headers={"Authorization": "Bearer user-token"},
    )
    assert upload.status_code == 202
    job_id = upload.json()["job"]["job_id"]
    fact_id = client.get(
        f"/api/documents/{job_id}/review",
        headers={"Authorization": "Bearer user-token"},
    ).json()["facts"][0]["fact_id"]
    respx.get("http://openemr.test/apis/default/fhir/Observation/obs-total-cholesterol").mock(
        return_value=Response(200, json=_observation_resource("obs-total-cholesterol", "p1", fact_id))
    )

    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact_id, "action": "approve"}]},
        headers={"Authorization": "Bearer user-token"},
    )
    write = client.post(
        f"/api/documents/{job_id}/write",
        headers={"Authorization": "Bearer user-token"},
    )

    assert approve.status_code == 200
    assert write.status_code == 200
    body = write.json()
    assert body["written_count"] == 1
    assert body["failed_count"] == 0
    assert body["facts"][0]["written_resource_id"] == "obs-total-cholesterol"
    assert duplicate_search.call_count == 1
    assert observation_create.call_count == 1


@respx.mock
def test_observation_create_404_recovers_inserted_observation_by_identifier() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=False,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    respx.get("http://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=True))
    )
    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(200, json={"resourceType": "Patient", "id": "p1"})
    )
    observation_create = respx.post("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(404, json=[])
    )
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="lab_pdf",
            content="Glucose 142 mg/dL reference range 70-99 H",
        ),
        headers={"Authorization": "Bearer user-token"},
    )
    assert upload.status_code == 202
    job_id = upload.json()["job"]["job_id"]
    fact_id = client.get(
        f"/api/documents/{job_id}/review",
        headers={"Authorization": "Bearer user-token"},
    ).json()["facts"][0]["fact_id"]
    observation = _observation_resource("obs-glucose", "p1", fact_id)
    duplicate_search = respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        side_effect=[
            Response(200, json={"resourceType": "Bundle", "entry": []}),
            Response(200, json={"resourceType": "Bundle", "entry": [{"resource": observation}]}),
        ]
    )
    respx.get("http://openemr.test/apis/default/fhir/Observation/obs-glucose").mock(
        return_value=Response(200, json=observation)
    )

    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact_id, "action": "approve"}]},
        headers={"Authorization": "Bearer user-token"},
    )
    write = client.post(
        f"/api/documents/{job_id}/write",
        headers={"Authorization": "Bearer user-token"},
    )

    assert approve.status_code == 200
    assert write.status_code == 200
    body = write.json()
    assert body["written_count"] == 1
    assert body["failed_count"] == 0
    assert body["facts"][0]["written_resource_id"] == "obs-glucose"
    assert duplicate_search.call_count == 2
    assert observation_create.call_count == 1


def test_demo_auth_bypass_fails_closed_on_chart_write_without_openemr_token() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=True,
        openemr_fhir_base_url="https://openemr.test/apis/default/fhir",
    )
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="lab_pdf",
            content="LDL Cholesterol 158 mg/dL reference range 0-99 H",
        ),
    )
    assert upload.status_code == 202
    job_id = upload.json()["job"]["job_id"]
    review = client.get(f"/api/documents/{job_id}/review").json()

    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": review["facts"][0]["fact_id"], "action": "approve"}]},
    )
    assert approve.status_code == 200

    write = client.post(f"/api/documents/{job_id}/write")

    assert write.status_code == 200
    body = write.json()
    assert body["written_count"] == 0
    assert body["failed_count"] == 1
    assert body["facts"][0]["status"] == "write_failed"
    assert "Observation writeback is disabled while demo auth bypass is active" in body["facts"][0]["write_error"]

    approved = client.get("/api/documents/patients/p1/approved-evidence")
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["evidence_count"] == 1
    assert approved_body["evidence"][0]["metadata"]["review_status"] == "write_failed"
    assert "Observation writeback is disabled" in approved_body["evidence"][0]["metadata"]["write_error"]


@respx.mock
def test_profile_patient_chart_write_uses_seeded_openemr_patient_uuid() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=True,
        openemr_fhir_base_url="https://openemr.test/apis/default/fhir",
    )
    patient_uuid = "5b8f4d2a-5e0a-4a7d-91f6-e507321f6d02"
    respx.get("https://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=True))
    )
    respx.get("https://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(200, json={"resourceType": "Bundle", "entry": []})
    )
    observation_create = respx.post("https://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(201, json={"resourceType": "Observation", "id": "obs-demo"})
    )
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="lab_pdf",
            content="LDL Cholesterol 158 mg/dL reference range 0-99 H",
        ),
        headers={"Authorization": "Bearer user-token"},
    )
    assert upload.status_code == 202
    job_id = upload.json()["job"]["job_id"]
    review = client.get(
        f"/api/documents/{job_id}/review",
        headers={"Authorization": "Bearer user-token"},
    ).json()
    fact_id = review["facts"][0]["fact_id"]
    respx.get("https://openemr.test/apis/default/fhir/Observation/obs-demo").mock(
        return_value=Response(200, json=_observation_resource("obs-demo", patient_uuid, fact_id))
    )

    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={"decisions": [{"fact_id": fact_id, "action": "approve"}]},
        headers={"Authorization": "Bearer user-token"},
    )
    assert approve.status_code == 200

    write = client.post(
        f"/api/documents/{job_id}/write",
        headers={"Authorization": "Bearer user-token"},
    )

    assert write.status_code == 200
    body = write.json()
    assert body["written_count"] == 1
    assert body["failed_count"] == 0
    assert body["facts"][0]["status"] == "written"
    assert observation_create.call_count >= 1
    created_payload = json.loads(observation_create.calls[0].request.content)
    assert created_payload["subject"]["reference"] == f"Patient/{patient_uuid}"


@respx.mock
def test_capabilities_report_observation_create_when_demo_auth_uses_openemr_metadata() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="production",
        dev_auth_bypass=False,
        demo_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    metadata_route = respx.get("http://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=True))
    )
    client = TestClient(app)

    response = client.get("/api/capabilities")

    assert response.status_code == 200
    assert response.json()["providers"]["openemr_observation_create_supported"] is True
    assert metadata_route.called


@respx.mock
def test_write_failure_reports_missing_observation_write_scope() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=True))
    )
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
    respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(200, json={"resourceType": "Bundle", "entry": []})
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
    respx.get("http://openemr.test/apis/default/fhir/Observation/obs-retry").mock(
        return_value=Response(200, json=_observation_resource("obs-retry", "p1", fact_id))
    )
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


@respx.mock
def test_write_failure_reports_openemr_validation_errors() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=False,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=True))
    )
    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(200, json={"resourceType": "Patient", "id": "p1"})
    )
    respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(200, json={"resourceType": "Bundle", "entry": []})
    )
    observation_route = respx.post("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(
            400,
            json={"validationErrors": {"subject": "Patient reference was not found"}},
        )
    )
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(
            doc_type="lab_pdf",
            content="Glucose 141 mg/dL reference range 70-99 H",
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
    assert body["facts"][0]["write_error"] == (
        "OpenEMR rejected the Observation payload (HTTP 400): "
        "subject: Patient reference was not found"
    )
    assert observation_route.call_count == 1


@respx.mock
def test_write_reports_when_openemr_observation_create_is_unavailable() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=False))
    )
    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(200, json={"resourceType": "Patient", "id": "p1"})
    )
    observation_create = respx.post("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(201, json={"resourceType": "Observation", "id": "should-not-create"})
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
    assert "Observation.create is not exposed" in body["facts"][0]["write_error"]
    assert observation_create.call_count == 0


@respx.mock
def test_reextract_after_write_failure_returns_clean_review_state() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/metadata").mock(
        return_value=Response(200, json=_capability_statement(create_observation=False))
    )
    respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(200, json={"resourceType": "Patient", "id": "p1"})
    )
    client = TestClient(app)
    payload = _document_payload(
        doc_type="lab_pdf",
        content="Hemoglobin A1c 8.6 % reference range 4.0-5.6 H",
    )
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=payload,
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
    assert write.json()["facts"][0]["status"] == "write_failed"

    reextract = client.post(
        "/api/documents/attach-and-extract",
        json=payload,
        headers={"Authorization": "Bearer user-token"},
    )

    assert reextract.status_code == 202
    reextract_body = reextract.json()
    assert reextract_body["job"]["job_id"] == job_id
    assert reextract_body["job"]["status"] == "review_required"
    assert reextract_body["fact_counts"] == {"review_required": 1}
    assert "reextracting_after_write_failure" in reextract_body["job"]["trace"]

    review = client.get(
        f"/api/documents/{job_id}/review",
        headers={"Authorization": "Bearer user-token"},
    ).json()
    assert review["facts"][0]["status"] == "review_required"
    assert review["facts"][0]["reviewed_by"] is None
    assert review["facts"][0]["reviewed_at"] is None
    assert review["facts"][0]["write_error"] is None


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


def test_chief_concern_question_uses_single_approved_document_fact() -> None:
    client = TestClient(app)
    _upload_approve_all(
        client,
        doc_type="intake_form",
        content="""
        Chief Concern: Follow up for diabetes and fatigue
        Medications: Metformin 1000 mg twice daily
        Allergies: Penicillin - rash
        Social History: Misses doses when work shifts change
        """,
    )

    chat = client.post(
        "/api/chat",
        json={"patient_id": "p1", "message": "Tell me Chen's chief concern and nothing else"},
    )
    final = _final_event(chat.text)

    assert chat.status_code == 200
    assert "Follow up for diabetes and fatigue" in final["answer"]
    assert "Misses doses when work shifts change" not in final["answer"]
    assert "Demo A1c" not in final["answer"]
    assert final["audit"]["retrieval_hits"] == 1
    assert final["audit"]["retrieval_plan"]["intent"] == "chief_concern_lookup"
    assert final["audit"]["retrieval_plan"]["evidence_limit"] == 1
    assert "approved_document_evidence" in final["audit"]["tools"]
    assert "demo_evidence" not in final["audit"]["tools"]
    assert "guideline_rag" not in final["audit"]["tools"]
    assert "search_patient_evidence" not in final["audit"]["tools"]


def test_recreational_drug_question_uses_approved_social_history() -> None:
    client = TestClient(app)
    _upload_approve_all(
        client,
        doc_type="intake_form",
        content="""
        Chief Concern: RUQ pain x 2 days
        Social History: Tobacco: Never Alcohol: None (in remission) Recreational drugs: Never
        """,
    )

    chat = client.post(
        "/api/chat",
        json={"patient_id": "p1", "message": "Has this patient ever taken recreational drugs?"},
    )
    final = _final_event(chat.text)

    assert chat.status_code == 200
    assert "Recreational drugs: Never" in final["answer"]
    assert final["audit"]["retrieval_plan"]["intent"] == "document_context_lookup"
    assert "approved_document_evidence" in final["audit"]["tools"]
    assert "demo_evidence" not in final["audit"]["tools"]
    assert "guideline_rag" not in final["audit"]["tools"]


def test_newly_uploaded_lab_fact_beats_stale_cholesterol_cluster_in_chat() -> None:
    client = TestClient(app)

    _upload_approve_all(
        client,
        doc_type="lab_pdf",
        content="""
        Collection Date: 2026-04-23
        Total Cholesterol 244 mg/dL reference range 0-199 H
        HDL Cholesterol 39 mg/dL reference range 40-60 L
        LDL Cholesterol 158 mg/dL reference range 0-99 H
        Triglycerides 224 mg/dL reference range 0-149 H
        """,
    )
    _upload_approve_all(
        client,
        doc_type="lab_pdf",
        content="""
        Collection Date: 2026-05-02
        Creatinine 1.6 mg/dL reference range 0.6-1.2 H
        eGFR 48 mL/min reference range 60-120 L
        """,
    )

    chat = client.post(
        "/api/chat",
        json={"patient_id": "p1", "message": "What creatinine or kidney abnormalities are in the new lab report?"},
    )
    final = _final_event(chat.text)

    assert chat.status_code == 200
    assert "Creatinine" in final["answer"]
    assert "1.6 mg/dL" in final["answer"]
    assert "sparse_evidence_search" in final["audit"]["tools"]
    assert "evidence_reranker" in final["audit"]["tools"]


def test_durable_source_lookup_reuses_persisted_document_after_cache_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"Hemoglobin A1c 8.6 % reference range 4.0-5.6 H"
    persisted_job, _source, _created = create_document_workflow(
        patient_id="p1",
        doc_type=W2DocType.lab_pdf,
        filename="example.txt",
        content_type="text/plain",
        content=content,
        actor_user_id="dev-doctor",
    )
    update_document_job(
        persisted_job.job_id,
        status=W2JobStatus.review_required,
        trace="extracted_0_facts",
    )
    snapshot = document_workflow_snapshot(persisted_job.job_id)
    reset_document_workflow_store()

    async def fake_lookup(**_kwargs: object) -> object:
        return snapshot

    async def fail_if_extraction_runs(**_kwargs: object) -> object:
        raise AssertionError("persisted document should not be extracted again")

    async def fake_persist(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.document_ingestion.document_workflow_persistence_configured", lambda _settings: True)
    monkeypatch.setattr("app.document_ingestion.read_document_workflow_snapshot_by_source_key", fake_lookup)
    monkeypatch.setattr("app.document_ingestion.extract_document_facts_async", fail_if_extraction_runs)
    monkeypatch.setattr("app.document_ingestion.upsert_document_workflow_snapshot", fake_persist)

    response = TestClient(app).post(
        "/api/documents/attach-and-extract",
        json={
            "patient_id": "p1",
            "doc_type": "lab_pdf",
            "filename": "example.txt",
            "content_type": "text/plain",
            "content_base64": base64.b64encode(content).decode("ascii"),
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["job"]["job_id"] == persisted_job.job_id
    assert body["job"]["status"] == "review_required"


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
        settings=Settings(
            app_env="local",
            dev_auth_bypass=True,
            demo_auth_bypass=True,
            vector_search_enabled=True,
        ),
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
    filename: str = "example.txt",
) -> dict[str, str]:
    return {
        "patient_id": "p1",
        "doc_type": doc_type,
        "filename": filename,
        "content_type": "text/plain",
        "content_base64": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }


def _upload_approve_all(client: TestClient, *, doc_type: str, content: str) -> str:
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(doc_type=doc_type, content=content),
    )
    assert upload.status_code == 202, upload.text
    job_id = upload.json()["job"]["job_id"]
    review = client.get(f"/api/documents/{job_id}/review").json()
    approve = client.post(
        f"/api/documents/{job_id}/review/decisions",
        json={
            "decisions": [
                {"fact_id": fact["fact_id"], "action": "approve"}
                for fact in review["facts"]
            ]
        },
    )
    assert approve.status_code == 200, approve.text
    return job_id


def _capability_statement(*, create_observation: bool) -> dict[str, Any]:
    interactions = [{"code": "search-type"}, {"code": "read"}]
    if create_observation:
        interactions.append({"code": "create"})
    return {
        "resourceType": "CapabilityStatement",
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {
                        "type": "Observation",
                        "interaction": interactions,
                    }
                ],
            }
        ],
    }


def _observation_resource(observation_id: str, patient_id: str, fact_id: str) -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "subject": {"reference": f"Patient/{patient_id}"},
        "identifier": [
            {
                "system": "https://agentforge.dev/fhir/identifier/document-fact",
                "value": fact_id,
            }
        ],
    }


def _final_event(stream_text: str) -> dict[str, Any]:
    for event in stream_text.split("\n\n"):
        if event.startswith("event: final"):
            data_line = next(line for line in event.splitlines() if line.startswith("data: "))
            payload = json.loads(data_line.removeprefix("data: "))
            assert isinstance(payload, dict)
            return payload
    raise AssertionError("No final SSE event found")
