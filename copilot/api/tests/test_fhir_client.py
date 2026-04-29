import pytest
import respx
from httpx import Response

from app.config import Settings
from app.fhir_client import OpenEMRFhirClient


@pytest.mark.asyncio
@respx.mock
async def test_search_patients_maps_fhir_bundle_and_sends_bearer_token() -> None:
    route = respx.get("http://openemr.test/apis/default/fhir/Patient").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p1",
                            "name": [{"given": ["Jane"], "family": "Moran"}],
                            "birthDate": "1975-04-12",
                            "gender": "female",
                        }
                    },
                    {"resource": {"resourceType": "Observation", "id": "ignored"}},
                ],
            },
        )
    )
    settings = Settings(openemr_fhir_base_url="http://openemr.test/apis/default/fhir")
    client = OpenEMRFhirClient(settings=settings, bearer_token="token-123")

    patients = await client.search_patients("Jane", count=7)

    assert len(patients) == 1
    assert patients[0].patient_id == "p1"
    assert patients[0].display_name == "Jane Moran"
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer token-123"
    assert request.url.params["name"] == "Jane"
    assert request.url.params["_count"] == "7"


@pytest.mark.asyncio
@respx.mock
async def test_get_patient_reads_patient_resource() -> None:
    route = respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Patient",
                "id": "p1",
                "name": [{"given": ["Jane"], "family": "Moran"}],
            },
        )
    )
    settings = Settings(openemr_fhir_base_url="http://openemr.test/apis/default/fhir")
    client = OpenEMRFhirClient(settings=settings, bearer_token="token-123")

    patient = await client.get_patient("p1")

    assert patient["id"] == "p1"
    assert route.calls[0].request.headers["authorization"] == "Bearer token-123"


@pytest.mark.asyncio
@respx.mock
async def test_search_active_conditions_filters_bundle_resources() -> None:
    route = respx.get("http://openemr.test/apis/default/fhir/Condition").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Condition", "id": "c1"}},
                    {"resource": {"resourceType": "Observation", "id": "ignored"}},
                ],
            },
        )
    )
    settings = Settings(openemr_fhir_base_url="http://openemr.test/apis/default/fhir")
    client = OpenEMRFhirClient(settings=settings, bearer_token="token-123")

    conditions = await client.search_active_conditions("p1", count=3)

    assert conditions == [{"resourceType": "Condition", "id": "c1"}]
    request = route.calls[0].request
    assert request.url.params["patient"] == "p1"
    assert request.url.params["_count"] == "3"


@pytest.mark.asyncio
@respx.mock
async def test_search_lab_observations_filters_and_sorts_recent_labs() -> None:
    route = respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Observation", "id": "o1"}},
                    {"resource": {"resourceType": "Condition", "id": "ignored"}},
                ],
            },
        )
    )
    settings = Settings(openemr_fhir_base_url="http://openemr.test/apis/default/fhir")
    client = OpenEMRFhirClient(settings=settings, bearer_token="token-123")

    observations = await client.search_lab_observations("p1", count=4)

    assert observations == [{"resourceType": "Observation", "id": "o1"}]
    request = route.calls[0].request
    assert request.url.params["patient"] == "p1"
    assert request.url.params["category"] == "laboratory"
    assert request.url.params["_sort"] == "-date"
    assert request.url.params["_count"] == "4"


@pytest.mark.asyncio
@respx.mock
async def test_search_medication_requests_filters_active_medications() -> None:
    route = respx.get("http://openemr.test/apis/default/fhir/MedicationRequest").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "MedicationRequest", "id": "m1"}},
                    {"resource": {"resourceType": "Observation", "id": "ignored"}},
                ],
            },
        )
    )
    settings = Settings(openemr_fhir_base_url="http://openemr.test/apis/default/fhir")
    client = OpenEMRFhirClient(settings=settings, bearer_token="token-123")

    medications = await client.search_medication_requests("p1", count=2)

    assert medications == [{"resourceType": "MedicationRequest", "id": "m1"}]
    request = route.calls[0].request
    assert request.url.params["patient"] == "p1"
    assert request.url.params["status"] == "active"
    assert request.url.params["_count"] == "2"


@pytest.mark.asyncio
@respx.mock
async def test_search_allergy_intolerances_filters_bundle_resources() -> None:
    route = respx.get("http://openemr.test/apis/default/fhir/AllergyIntolerance").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "AllergyIntolerance", "id": "a1"}},
                    {"resource": {"resourceType": "Condition", "id": "ignored"}},
                ],
            },
        )
    )
    settings = Settings(openemr_fhir_base_url="http://openemr.test/apis/default/fhir")
    client = OpenEMRFhirClient(settings=settings, bearer_token="token-123")

    allergies = await client.search_allergy_intolerances("p1", count=3)

    assert allergies == [{"resourceType": "AllergyIntolerance", "id": "a1"}]
    request = route.calls[0].request
    assert request.url.params["patient"] == "p1"
    assert request.url.params["_count"] == "3"
