from collections.abc import Generator

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings, get_settings
from app.main import app
from app.openemr_auth import clear_dev_password_token_cache


@pytest.fixture(autouse=True)
def reset_app_overrides() -> Generator[None]:
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()
    yield
    app.dependency_overrides.clear()
    clear_dev_password_token_cache()


@respx.mock
def test_patient_search_uses_dev_password_token_for_local_openemr() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_base_url="http://openemr.test",
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
        openemr_dev_password_grant=True,
        openemr_client_id="client-id",
        openemr_client_secret="client-secret",
        openemr_dev_username="admin",
        openemr_dev_password="pass",
        openemr_dev_scopes="openid api:oemr api:fhir user/Patient.read",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    respx.post("http://openemr.test/oauth2/default/token").mock(
        return_value=Response(200, json={"access_token": "dev-token", "expires_in": 60})
    )
    patient_route = respx.get("http://openemr.test/apis/default/fhir/Patient").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p1",
                            "name": [{"given": ["Demo"], "family": "Patient"}],
                        }
                    }
                ],
            },
        )
    )

    response = TestClient(app).get("/api/patients?query=Demo")

    assert response.status_code == 200
    assert response.json() == [
        {
            "patient_id": "p1",
            "display_name": "Demo Patient",
            "birth_date": None,
            "gender": None,
            "source_system": "openemr",
        }
    ]
    assert patient_route.calls[0].request.headers["authorization"] == "Bearer dev-token"


@respx.mock
def test_patient_search_passes_through_user_bearer_token() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    patient_route = respx.get("http://openemr.test/apis/default/fhir/Patient").mock(
        return_value=Response(200, json={"resourceType": "Bundle", "entry": []})
    )

    response = TestClient(app).get(
        "/api/patients?query=Demo",
        headers={"Authorization": "Bearer user-token"},
    )

    assert response.status_code == 200
    assert patient_route.calls[0].request.headers["authorization"] == "Bearer user-token"


@respx.mock
def test_patient_roster_lists_authorized_patients_without_name_query() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    patient_route = respx.get("http://openemr.test/apis/default/fhir/Patient").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p1",
                            "name": [{"given": ["Elena"], "family": "Morrison"}],
                            "birthDate": "1972-09-18",
                            "gender": "female",
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p2",
                            "name": [{"given": ["Marcus"], "family": "Chen"}],
                            "birthDate": "1959-02-07",
                            "gender": "male",
                        }
                    },
                ],
            },
        )
    )

    response = TestClient(app).get(
        "/api/patients?count=50",
        headers={"Authorization": "Bearer user-token"},
    )

    assert response.status_code == 200
    assert [patient["display_name"] for patient in response.json()] == [
        "Elena Morrison",
        "Marcus Chen",
    ]
    assert patient_route.calls[0].request.headers["authorization"] == "Bearer user-token"
    assert "name" not in patient_route.calls[0].request.url.params
    assert patient_route.calls[0].request.url.params["_count"] == "50"


@respx.mock
def test_patient_search_returns_unauthorized_when_openemr_denies_access() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    respx.get("http://openemr.test/apis/default/fhir/Patient").mock(
        return_value=Response(401, json={"error": "unauthorized"})
    )

    response = TestClient(app).get("/api/patients?query=Demo")

    assert response.status_code == 401
    assert response.json()["detail"] == "OpenEMR FHIR access denied"


def test_me_does_not_echo_bearer_token() -> None:
    settings = Settings(app_env="local", dev_auth_bypass=True)
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get("/api/me", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
    assert "access_token" not in response.json()


def test_me_requires_bearer_token_when_dev_bypass_is_disabled() -> None:
    settings = Settings(app_env="production", dev_auth_bypass=False)
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get("/api/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_demo_patient_context_returns_summary_without_fhir() -> None:
    settings = Settings(app_env="local", dev_auth_bypass=True, openemr_fhir_base_url=None)
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get("/api/patients/demo-diabetes-001")

    assert response.status_code == 200
    assert response.json() == {
        "patient_id": "demo-diabetes-001",
        "display_name": "Demo Patient",
        "birth_date": "1975-04-12",
        "gender": "female",
        "source_system": "openemr",
    }


@respx.mock
def test_patient_context_reads_fhir_patient_with_user_bearer_token() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    route = respx.get("http://openemr.test/apis/default/fhir/Patient/p1").mock(
        return_value=Response(
            200,
            json={
                "resourceType": "Patient",
                "id": "p1",
                "name": [{"given": ["Jane"], "family": "Moran"}],
                "birthDate": "1975-04-12",
                "gender": "female",
            },
        )
    )

    response = TestClient(app).get(
        "/api/patients/p1",
        headers={"Authorization": "Bearer user-token"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Jane Moran"
    assert route.calls[0].request.headers["authorization"] == "Bearer user-token"


@respx.mock
def test_patient_context_returns_not_found_when_fhir_patient_missing() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        openemr_fhir_base_url="http://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    respx.get("http://openemr.test/apis/default/fhir/Patient/missing").mock(
        return_value=Response(404, json={"resourceType": "OperationOutcome"})
    )

    response = TestClient(app).get("/api/patients/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "OpenEMR patient was not found"
