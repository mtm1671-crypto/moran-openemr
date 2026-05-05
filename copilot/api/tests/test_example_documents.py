import base64
import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings, get_settings
from app.document_storage import reset_document_workflow_store
from app.main import app
from app.openemr_auth import clear_dev_password_token_cache

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_DOCS = REPO_ROOT / "example-documents"


@pytest.fixture(autouse=True)
def reset_app_state() -> Generator[None]:
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    reset_document_workflow_store()
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url=None,
    )
    yield
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    reset_document_workflow_store()


@pytest.mark.parametrize(
    ("relative_path", "doc_type", "expected_labels"),
    [
        (
            "intake-forms/p01-chen-intake-typed.pdf",
            "intake_form",
            {"Chief concern", "Patient-reported medication", "Patient-reported allergy"},
        ),
        (
            "intake-forms/p02-whitaker-intake.pdf",
            "intake_form",
            {"Chief concern", "Patient-reported medication", "Family history"},
        ),
        (
            "lab-results/p01-chen-lipid-panel.pdf",
            "lab_pdf",
            {"Total Cholesterol", "HDL Cholesterol", "LDL Cholesterol", "Triglycerides"},
        ),
        (
            "lab-results/p02-whitaker-cbc.pdf",
            "lab_pdf",
            {"WBC", "RBC", "Hemoglobin", "Hematocrit", "MCV", "Platelets"},
        ),
        (
            "lab-results/p04-kowalski-cmp.pdf",
            "lab_pdf",
            {"Glucose", "Creatinine", "eGFR", "Potassium", "ALT", "AST"},
        ),
    ],
)
def test_example_pdf_documents_extract_through_api(
    relative_path: str,
    doc_type: str,
    expected_labels: set[str],
) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(EXAMPLE_DOCS / relative_path, doc_type=doc_type),
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job"]["job_id"]

    review = client.get(f"/api/documents/{job_id}/review")
    assert review.status_code == 200
    facts = review.json()["facts"]
    labels = {fact["display_label"] for fact in facts}

    assert expected_labels <= labels
    assert all(fact["status"] == "review_required" for fact in facts)
    assert all(fact["citation"]["bbox"]["page"] == 1 for fact in facts)


@pytest.mark.parametrize(
    ("relative_path", "doc_type"),
    [
        ("intake-forms/p03-reyes-intake.png", "intake_form"),
        ("intake-forms/p04-kowalski-intake.png", "intake_form"),
        ("lab-results/p03-reyes-hba1c.png", "lab_pdf"),
    ],
)
def test_example_image_documents_fail_closed_without_local_ocr(
    relative_path: str,
    doc_type: str,
) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(EXAMPLE_DOCS / relative_path, doc_type=doc_type),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Document extraction failed"


@respx.mock
def test_example_image_document_extracts_when_openai_ocr_is_enabled() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url=None,
        ocr_provider="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.openai.test/v1",
        openai_ocr_model="gpt-4.1-mini",
        openai_ocr_detail="high",
    )
    route = respx.post("https://api.openai.test/v1/responses").mock(
        return_value=Response(
            200,
            json={
                "output_text": "\n".join(
                    [
                        "Southwest Reference Laboratory",
                        "Collection Date: 2026-04-20",
                        "TEST RESULT FLAG REFERENCE RANGE UNITS",
                        "Hemoglobin A1c 7.4 H 4.0-5.6 %",
                    ]
                )
            },
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(EXAMPLE_DOCS / "lab-results/p03-reyes-hba1c.png", doc_type="lab_pdf"),
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job"]["job_id"]
    review = client.get(f"/api/documents/{job_id}/review").json()
    request_body = json.loads(route.calls[0].request.content)

    assert request_body["model"] == "gpt-4.1-mini"
    image_item = request_body["input"][0]["content"][1]
    assert image_item["type"] == "input_image"
    assert image_item["detail"] == "high"
    assert image_item["image_url"].startswith("data:image/png;base64,")
    assert review["facts"][0]["display_label"] == "Hemoglobin A1c"
    assert review["facts"][0]["normalized_value"] == "7.4 % on 2026-04-20 (high)"


@respx.mock
def test_example_image_document_extracts_when_openrouter_ocr_is_enabled() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url=None,
        ocr_provider="openrouter",
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
        openrouter_demo_data_only=True,
        openrouter_ocr_model="baidu/qianfan-ocr-fast:free",
    )
    route = respx.post("https://openrouter.test/api/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "\n".join(
                                [
                                    "Southwest Reference Laboratory",
                                    "Collection Date: 2026-04-20",
                                    "TEST RESULT FLAG REFERENCE RANGE UNITS",
                                    "Hemoglobin A1c 7.4 H 4.0-5.6 %",
                                ]
                            ),
                        }
                    }
                ]
            },
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(EXAMPLE_DOCS / "lab-results/p03-reyes-hba1c.png", doc_type="lab_pdf"),
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job"]["job_id"]
    review = client.get(f"/api/documents/{job_id}/review").json()
    request_body = json.loads(route.calls[0].request.content)

    assert request_body["model"] == "baidu/qianfan-ocr-fast:free"
    assert request_body["max_tokens"] == 2500
    image_item = request_body["messages"][0]["content"][1]
    assert image_item["type"] == "image_url"
    assert image_item["image_url"]["url"].startswith("data:image/png;base64,")
    assert review["facts"][0]["display_label"] == "Hemoglobin A1c"
    assert review["facts"][0]["normalized_value"] == "7.4 % on 2026-04-20 (high)"


def test_approved_example_pdf_evidence_is_queryable_in_chat() -> None:
    client = TestClient(app)
    upload = client.post(
        "/api/documents/attach-and-extract",
        json=_document_payload(EXAMPLE_DOCS / "lab-results/p01-chen-lipid-panel.pdf", doc_type="lab_pdf"),
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
    assert approve.status_code == 200

    chat = client.post(
        "/api/chat",
        json={"patient_id": "p1", "message": "What lab results are documented?"},
    )
    final = _final_event(chat.text)

    assert chat.status_code == 200
    assert "LDL Cholesterol: 158 mg/dL on 2026-04-23 (high)." in final["answer"]
    assert "approved_document_evidence" in final["audit"]["tools"]
    assert any(citation["source_url"].endswith("/review") for citation in final["citations"])


def _document_payload(path: Path, *, doc_type: str) -> dict[str, str]:
    assert path.is_file(), f"Missing example document: {path}"
    content_type = "application/pdf" if path.suffix.lower() == ".pdf" else "image/png"
    return {
        "patient_id": "p1",
        "doc_type": doc_type,
        "filename": path.name,
        "content_type": content_type,
        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def _final_event(stream_text: str) -> dict[str, Any]:
    for event in stream_text.split("\n\n"):
        if event.startswith("event: final"):
            data_line = next(line for line in event.splitlines() if line.startswith("data: "))
            payload = json.loads(data_line.removeprefix("data: "))
            assert isinstance(payload, dict)
            return payload
    raise AssertionError("No final SSE event found")
