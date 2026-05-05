import base64
import os
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_DOCS = REPO_ROOT / "example-documents"


@pytest.mark.skipif(
    os.getenv("RUN_STAGING_OCR") != "1",
    reason=(
        "Set RUN_STAGING_OCR=1, STAGING_COPILOT_API_BASE_URL, "
        "STAGING_COPILOT_BEARER_TOKEN, and STAGING_COPILOT_PATIENT_ID."
    ),
)
def test_staging_png_ocr_extracts_reviewable_facts() -> None:
    base_url = _required_env("STAGING_COPILOT_API_BASE_URL").rstrip("/")
    bearer_token = _required_env("STAGING_COPILOT_BEARER_TOKEN")
    patient_id = _required_env("STAGING_COPILOT_PATIENT_ID")
    document_path = Path(
        os.getenv(
            "STAGING_OCR_DOCUMENT_PATH",
            str(EXAMPLE_DOCS / "lab-results" / "p03-reyes-hba1c.png"),
        )
    )
    assert document_path.is_file(), f"Missing staging OCR document: {document_path}"

    headers = {"Authorization": f"Bearer {bearer_token}"}
    payload = {
        "patient_id": patient_id,
        "doc_type": "lab_pdf",
        "filename": document_path.name,
        "content_type": "image/png",
        "content_base64": base64.b64encode(document_path.read_bytes()).decode("ascii"),
    }
    with httpx.Client(timeout=90) as client:
        upload = client.post(
            f"{base_url}/api/documents/attach-and-extract",
            headers=headers,
            json=payload,
        )
        if upload.status_code == 422:
            raise AssertionError(
                "Staging OCR did not extract the PNG. OCR_PROVIDER is probably disabled, "
                "the configured OCR provider/model is misconfigured, or the OCR text did not produce supported facts. "
                f"Response: {upload.text}"
            )
        assert upload.status_code == 202, upload.text
        job_id = upload.json()["job"]["job_id"]
        review = client.get(f"{base_url}/api/documents/{job_id}/review", headers=headers)

    assert review.status_code == 200, review.text
    body = review.json()
    facts = body["facts"]
    assert facts, body
    labels = {fact["display_label"] for fact in facts if isinstance(fact, dict)}
    assert "Hemoglobin A1c" in labels


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is required for staging OCR smoke test")
    return value
