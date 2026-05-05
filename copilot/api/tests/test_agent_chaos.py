import base64
import json
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.document_storage import reset_document_workflow_store
from app.main import app
from app.openemr_auth import clear_dev_password_token_cache


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


def _post_upload(payload: dict[str, str]) -> Any:
    return TestClient(app).post("/api/documents/attach-and-extract", json=payload)


def _document_payload(content: str) -> dict[str, str]:
    return {
        "patient_id": "p-chaos",
        "doc_type": "intake_form",
        "filename": "chaos-intake.txt",
        "content_type": "text/plain",
        "content_base64": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }


def _final_event(stream_text: str) -> dict[str, Any]:
    for event in stream_text.split("\n\n"):
        if event.startswith("event: final"):
            data_line = next(line for line in event.splitlines() if line.startswith("data: "))
            return json.loads(data_line.removeprefix("data: "))
    raise AssertionError("No final SSE event found")
