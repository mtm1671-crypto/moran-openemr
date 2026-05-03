from datetime import UTC, datetime
from typing import Any

import pytest

from app.config import Settings
from app.evidence_tools import EvidenceRetrievalResult
from app.jobs import run_nightly_maintenance, run_patient_reindex
from app.models import EvidenceObject
from app.scheduler import seconds_until_next_hour

TEST_FERNET_KEY = "PAAhZkguTNgLSk3R268DyJ-Lu6c_M4_87k7s2Prrt_8="


@pytest.mark.asyncio
async def test_nightly_maintenance_skips_when_persistent_storage_is_disabled() -> None:
    result = await run_nightly_maintenance(Settings(app_env="local"))

    assert result["ok"] is True
    assert result["job"] == "nightly_maintenance"
    assert result["skipped"] is True


def test_seconds_until_next_hour_rolls_to_next_day_after_target_hour() -> None:
    now = datetime(2026, 5, 3, 9, 30, tzinfo=UTC)

    assert seconds_until_next_hour(now, 8) == pytest.approx(22.5 * 60 * 60)


def test_seconds_until_next_hour_uses_same_day_before_target_hour() -> None:
    now = datetime(2026, 5, 3, 7, 30, tzinfo=UTC)

    assert seconds_until_next_hour(now, 8) == pytest.approx(30 * 60)


@pytest.mark.asyncio
async def test_patient_reindex_uses_service_account_and_indexes_relationships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}
    settings = Settings(
        app_env="local",
        openemr_fhir_base_url="https://openemr.test/apis/default/fhir",
        vector_search_enabled=True,
        database_url="postgresql://copilot:secret@db.example.test:5432/copilot",
        encryption_key=TEST_FERNET_KEY,
        openemr_service_account_enabled=True,
        openemr_service_bearer_token="service-token",
    )

    evidence = EvidenceObject(
        evidence_id="ev-lab-1",
        patient_id="p1",
        source_type="lab_result",
        source_id="o1",
        display_name="Hemoglobin A1c",
        fact="Hemoglobin A1c was 8.6%.",
        retrieved_at=datetime.now(tz=UTC),
    )

    async def fake_initialize_phi_schema(_settings: Settings) -> None:
        calls["initialized"] = True

    async def fake_create_job_run(_settings: Settings, record: dict[str, Any]) -> str:
        calls["created_job"] = record
        return "job-1"

    async def fake_update_job_run(**kwargs: Any) -> None:
        calls["updated_job"] = kwargs

    async def fake_resolve_service_token(_settings: Settings) -> str:
        calls["service_token"] = True
        return "service-token"

    async def fake_index_patient_evidence(**kwargs: Any) -> int:
        calls["indexed_evidence"] = kwargs["evidence"]
        return len(kwargs["evidence"])

    async def fake_upsert_relationships(_settings: Settings, records: list[dict[str, Any]]) -> None:
        calls["relationships"] = records

    class FakeFhirClient:
        def __init__(self, **kwargs: Any) -> None:
            calls["client_token"] = kwargs["bearer_token"]

    class FakeEvidenceService:
        def __init__(self, _client: FakeFhirClient) -> None:
            pass

        async def collect_patient_index_evidence(self, patient_id: str) -> EvidenceRetrievalResult:
            assert patient_id == "p1"
            return EvidenceRetrievalResult(evidence=[evidence], tools=["get_recent_labs"])

    monkeypatch.setattr("app.jobs.initialize_phi_schema", fake_initialize_phi_schema)
    monkeypatch.setattr("app.jobs.create_job_run", fake_create_job_run)
    monkeypatch.setattr("app.jobs.update_job_run", fake_update_job_run)
    monkeypatch.setattr("app.jobs.resolve_service_fhir_bearer_token", fake_resolve_service_token)
    monkeypatch.setattr("app.jobs.index_patient_evidence", fake_index_patient_evidence)
    monkeypatch.setattr("app.jobs.upsert_semantic_relationship_records", fake_upsert_relationships)
    monkeypatch.setattr("app.jobs.OpenEMRFhirClient", FakeFhirClient)
    monkeypatch.setattr("app.jobs.FhirEvidenceService", FakeEvidenceService)

    result = await run_patient_reindex(settings=settings, patient_id="p1", actor_user_id="doctor-1")

    assert result["ok"] is True
    assert result["job_id"] == "job-1"
    assert result["indexed_evidence_count"] == 1
    assert calls["initialized"] is True
    assert calls["service_token"] is True
    assert calls["client_token"] == "service-token"
    assert calls["indexed_evidence"] == [evidence]
    assert calls["relationships"]
    assert calls["updated_job"]["status"] == "succeeded"
