import json
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.config import get_settings
from app.evidence_tools import FhirEvidenceService
from app.fhir_client import OpenEMRFhirClient
from app.main import app
from app.openemr_auth import clear_dev_password_token_cache
from app.openemr_auth import DevPasswordGrantTokenProvider


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OPENEMR") != "1",
    reason="Set RUN_LIVE_OPENEMR=1 and OpenEMR dev OAuth env vars to run live smoke test.",
)
async def test_live_openemr_metadata_and_patient_search() -> None:
    settings = _live_settings()
    token = await DevPasswordGrantTokenProvider().get_access_token(settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=token)

    metadata = await client.metadata()
    patients = await client.search_patients("a", count=1)

    assert metadata["resourceType"] == "CapabilityStatement"
    assert isinstance(patients, list)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OPENEMR") != "1",
    reason="Set RUN_LIVE_OPENEMR=1 and OpenEMR dev OAuth env vars to run live smoke test.",
)
async def test_live_evidence_service_reads_patient_demographics_when_sample_patient_exists() -> None:
    settings = _live_settings()
    token = await DevPasswordGrantTokenProvider().get_access_token(settings)
    client = OpenEMRFhirClient(settings=settings, bearer_token=token)
    patient_id = await _first_live_patient_id(client)
    if patient_id is None:
        pytest.skip("OpenEMR did not return a sample patient for the smoke-test search terms.")

    evidence = await FhirEvidenceService(client).get_patient_demographics(patient_id)

    assert evidence
    assert all(item.patient_id == patient_id for item in evidence)
    assert evidence[0].source_url == f"/api/source/openemr/Patient/{patient_id}"


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OPENEMR") != "1",
    reason="Set RUN_LIVE_OPENEMR=1 and OpenEMR dev OAuth env vars to run live smoke test.",
)
def test_live_api_patient_search_route() -> None:
    clear_dev_password_token_cache()
    app.dependency_overrides[get_settings] = _live_settings
    try:
        response = TestClient(app).get("/api/patients?query=ad")
    finally:
        app.dependency_overrides.clear()
        clear_dev_password_token_cache()

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OPENEMR") != "1",
    reason="Set RUN_LIVE_OPENEMR=1 and OpenEMR dev OAuth env vars to run live smoke test.",
)
def test_live_api_chat_route_returns_verified_final_event_when_sample_patient_exists() -> None:
    clear_dev_password_token_cache()
    app.dependency_overrides[get_settings] = _live_settings
    client = TestClient(app)
    try:
        patients = _search_live_patients(client)
        if not patients:
            pytest.skip("OpenEMR did not return a sample patient for the smoke-test search terms.")

        chat_response = client.post(
            "/api/chat",
            json={
                "patient_id": patients[0]["patient_id"],
                "message": "What is the patient's name and date of birth?",
            },
        )
        final = _final_event(chat_response.text)
    finally:
        app.dependency_overrides.clear()
        clear_dev_password_token_cache()

    assert chat_response.status_code == 200
    assert final["audit"]["verification"] == "passed"
    assert final["audit"]["tools"] == ["get_patient_demographics"]
    assert final["citations"]


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OPENEMR") != "1",
    reason="Set RUN_LIVE_OPENEMR=1 and OpenEMR dev OAuth env vars to run live smoke test.",
)
def test_live_api_observation_citation_source_opens_for_seeded_patient() -> None:
    clear_dev_password_token_cache()
    app.dependency_overrides[get_settings] = _live_settings
    client = TestClient(app)
    try:
        patient_response = client.get("/api/patients?query=mo")
        assert patient_response.status_code == 200
        patients = patient_response.json()
        if not patients:
            pytest.skip("Seeded MVP patient Elena Morrison was not found.")

        chat_response = client.post(
            "/api/chat",
            json={
                "patient_id": patients[0]["patient_id"],
                "message": "Show recent labs and abnormal results.",
            },
        )
        final = _final_event(chat_response.text)
        observation_source_url = next(
            (
                citation["source_url"]
                for citation in final["citations"]
                if citation["source_url"] and "/Observation/" in citation["source_url"]
            ),
            None,
        )
        if observation_source_url is None:
            pytest.skip("No Observation citation was returned for the seeded patient.")

        source_response = client.get(observation_source_url)
    finally:
        app.dependency_overrides.clear()
        clear_dev_password_token_cache()

    assert chat_response.status_code == 200
    assert final["audit"]["verification"] == "passed"
    assert source_response.status_code == 200
    assert source_response.json()["resourceType"] == "Observation"


async def _first_live_patient_id(client: OpenEMRFhirClient) -> str | None:
    for query in ["a", "e", "demo", "test", "smith", "ad"]:
        patients = await client.search_patients(query, count=1)
        if patients:
            return patients[0].patient_id
    return None


def _search_live_patients(client: TestClient) -> list[dict[str, Any]]:
    for query in ["mo", "ad", "de", "te", "sm"]:
        response = client.get(f"/api/patients?query={query}")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, list)
        if payload:
            return payload
    return []


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


def _live_settings() -> Settings:
    return Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_base_url=os.environ["OPENEMR_BASE_URL"],
        openemr_fhir_base_url=os.environ["OPENEMR_FHIR_BASE_URL"],
        openemr_dev_password_grant=True,
        openemr_client_id=os.environ["OPENEMR_CLIENT_ID"],
        openemr_client_secret=os.getenv("OPENEMR_CLIENT_SECRET"),
        openemr_dev_username=os.environ["OPENEMR_DEV_USERNAME"],
        openemr_dev_password=os.environ["OPENEMR_DEV_PASSWORD"],
        openemr_tls_verify=os.getenv("OPENEMR_TLS_VERIFY", "true").lower() == "true",
    )
