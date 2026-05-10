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
                            "name": [{"given": ["Margaret"], "family": "Chen"}],
                            "birthDate": "1967-08-14",
                            "gender": "female",
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
        "Margaret Chen",
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


def test_production_demo_auth_bypass_is_rejected_without_bearer_token() -> None:
    settings = Settings(app_env="production", dev_auth_bypass=False, demo_auth_bypass=True)
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get("/api/me")

    assert response.status_code == 503
    assert response.json()["detail"] == "DEMO_AUTH_BYPASS is local-only and cannot be used in production"


def test_production_demo_auth_bypass_is_rejected_with_bearer_token() -> None:
    settings = Settings(app_env="production", dev_auth_bypass=False, demo_auth_bypass=True)
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get("/api/me", headers={"Authorization": "Bearer demo-token"})

    assert response.status_code == 503
    assert response.json()["detail"] == "DEMO_AUTH_BYPASS is local-only and cannot be used in production"


def test_demo_auth_bypass_returns_locked_margaret_chen_roster() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=True,
        openemr_fhir_base_url="https://openemr.test/apis/default/fhir",
    )
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get(
        "/api/patients?query=chen",
        headers={"Authorization": "Bearer demo-token"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "patient_id": "5b8f4d2a-5e0a-4a7d-91f6-e507321f6d02",
            "display_name": "Margaret Chen",
            "birth_date": "1967-08-14",
            "gender": "female",
            "source_system": "openemr",
        }
    ]


def test_demo_auth_bypass_returns_example_document_patient_profiles() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=True,
        openemr_fhir_base_url=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    roster = client.get("/api/patients")
    reyes = client.get("/api/patients/p3")

    assert roster.status_code == 200
    profiles = {patient["display_name"]: patient["patient_id"] for patient in roster.json()}
    assert profiles["Margaret Chen"] == "5b8f4d2a-5e0a-4a7d-91f6-e507321f6d02"
    assert profiles["James Whitaker"] == "19d0e928-5953-474e-b8ee-0f50b731a662"
    assert profiles["Sofia Reyes"] == "6c3ef6a6-7b81-4e4d-bb76-92f5dcf72103"
    assert profiles["Robert Kowalski"] == "8b08c918-a991-41d8-82ce-6c0c98dbdb58"
    assert reyes.status_code == 200
    assert reyes.json() == {
        "patient_id": "6c3ef6a6-7b81-4e4d-bb76-92f5dcf72103",
        "display_name": "Sofia Reyes",
        "birth_date": "1983-12-19",
        "gender": "female",
        "source_system": "openemr",
    }


def test_demo_patient_context_returns_summary_without_fhir() -> None:
    settings = Settings(
        app_env="local",
        dev_auth_bypass=True,
        demo_auth_bypass=True,
        openemr_fhir_base_url=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get("/api/patients/demo-diabetes-001")

    assert response.status_code == 200
    assert response.json() == {
        "patient_id": "0f5c8cf1-0a22-4b70-9e83-3275d67cd901",
        "display_name": "Demo Patient",
        "birth_date": "1975-04-12",
        "gender": "female",
        "source_system": "openemr",
    }


def test_patient_routes_fail_closed_without_fhir_when_demo_mode_is_disabled() -> None:
    settings = Settings(app_env="local", dev_auth_bypass=True, openemr_fhir_base_url=None)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    patient_list = client.get("/api/patients")
    patient_detail = client.get("/api/patients/demo-diabetes-001")

    assert patient_list.status_code == 503
    assert "real patient search is unavailable" in patient_list.json()["detail"]
    assert patient_detail.status_code == 503
    assert "real patient lookup is unavailable" in patient_detail.json()["detail"]


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
