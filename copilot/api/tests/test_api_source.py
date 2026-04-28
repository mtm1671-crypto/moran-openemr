import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings, get_settings
from app.main import app
from app.openemr_auth import clear_dev_password_token_cache


@pytest.fixture(autouse=True)
def reset_app_overrides() -> None:
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    yield
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()


@respx.mock
def test_openemr_source_returns_raw_fhir_resource_with_user_bearer_token() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    route = respx.get("http://openemr.test/apis/default/fhir/Observation/o1").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Observation",
                "id": "o1",
                "code": {"text": "Hemoglobin A1c"},
            },
        )
    )

    response = TestClient(app).get(
        "/api/source/openemr/Observation/o1",
        headers={"Authorization": "Bearer user-token"},
    )

    assert response.status_code == 200
    assert response.json()["resourceType"] == "Observation"
    assert route.calls[0].request.headers["authorization"] == "Bearer user-token"


@respx.mock
def test_openemr_source_falls_back_to_id_search_when_direct_read_is_not_found() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/Observation/o1").mock(
        return_value=Response(404, json={"resourceType": "OperationOutcome"})
    )
    search_route = respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "id": "o1",
                            "code": {"text": "Hemoglobin A1c"},
                        }
                    }
                ],
            },
        )
    )

    response = TestClient(app).get("/api/source/openemr/Observation/o1")

    assert response.status_code == 200
    assert response.json()["id"] == "o1"
    assert search_route.calls[0].request.url.params["_id"] == "o1"
    assert search_route.calls[0].request.url.params["_count"] == "1"


@respx.mock
def test_openemr_source_falls_back_to_patient_scoped_search_when_id_search_misses() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/Observation/o1").mock(
        return_value=Response(404, json={"resourceType": "OperationOutcome"})
    )
    search_route = respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        side_effect=[
            Response(200, json={"resourceType": "Bundle", "entry": []}),
            Response(
                200,
                json={
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "id": "o1",
                                "subject": {"reference": "Patient/p1"},
                                "code": {"text": "Hemoglobin A1c"},
                            }
                        }
                    ],
                },
            ),
        ]
    )

    response = TestClient(app).get("/api/source/openemr/Observation/o1?patient_id=p1")

    assert response.status_code == 200
    assert response.json()["id"] == "o1"
    assert search_route.calls[0].request.url.params["_id"] == "o1"
    assert search_route.calls[1].request.url.params["patient"] == "p1"
    assert search_route.calls[1].request.url.params["_count"] == "100"


@respx.mock
def test_openemr_source_does_not_return_patient_scoped_resource_for_wrong_patient() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/Observation/o1").mock(
        return_value=Response(404, json={"resourceType": "OperationOutcome"})
    )
    respx.get("http://openemr.test/apis/default/fhir/Observation").mock(
        side_effect=[
            Response(200, json={"resourceType": "Bundle", "entry": []}),
            Response(
                200,
                json={
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "id": "o1",
                                "subject": {"reference": "Patient/other"},
                            }
                        }
                    ],
                },
            ),
        ]
    )

    response = TestClient(app).get("/api/source/openemr/Observation/o1?patient_id=p1")

    assert response.status_code == 404
    assert response.json()["detail"] == "OpenEMR source was not found"


def test_openemr_source_rejects_unsupported_resource_type() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get("/api/source/openemr/Medication/m1")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported OpenEMR source resource type"


def test_demo_source_returns_demo_observation() -> None:
    response = TestClient(app).get("/api/source/demo-lab-a1c")

    assert response.status_code == 200
    assert response.json()["resourceType"] == "Observation"
    assert response.json()["id"] == "demo-lab-a1c"
