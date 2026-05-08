from typing import Any, cast

import httpx

from app.config import Settings
from app.http_retry import RetryPolicy, request_with_retries
from app.models import PatientSummary


class OpenEMRFhirClient:
    def __init__(self, settings: Settings, bearer_token: str | None = None) -> None:
        if settings.openemr_fhir_base_url is None:
            raise ValueError("OPENEMR_FHIR_BASE_URL is required")
        self._base_url = str(settings.openemr_fhir_base_url).rstrip("/")
        self._bearer_token = bearer_token
        self._tls_verify = settings.openemr_tls_verify
        self._timeout_seconds = settings.openemr_request_timeout_seconds
        self._retry_policy = RetryPolicy(
            attempts=settings.openemr_retry_attempts,
            backoff_seconds=settings.openemr_retry_backoff_seconds,
        )

    async def metadata(self) -> dict[str, Any]:
        return await self._request_json("GET", "/metadata")

    async def supports_create(self, resource_type: str) -> bool:
        return capability_statement_supports_create(await self.metadata(), resource_type)

    async def read_resource(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        return await self._request_json("GET", f"/{resource_type}/{resource_id}")

    async def create_resource(self, resource_type: str, resource: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json("POST", f"/{resource_type}", json_body=resource)

    async def get_patient(self, patient_id: str) -> dict[str, Any]:
        return await self.read_resource("Patient", patient_id)

    async def get_patient_summary(self, patient_id: str) -> PatientSummary:
        return _patient_from_fhir(await self.get_patient(patient_id))

    async def list_patients(self, count: int = 100) -> list[PatientSummary]:
        bundle = await self.search_bundle("Patient", params={"_count": str(count)})
        return _patients_from_bundle(bundle)

    async def search_patients(self, query: str, count: int = 20) -> list[PatientSummary]:
        params = {"name": query, "_count": str(count)}
        bundle = await self.search_bundle("Patient", params=params)
        return _patients_from_bundle(bundle)

    async def search_active_conditions(self, patient_id: str, count: int = 20) -> list[dict[str, Any]]:
        bundle = await self.search_bundle(
            "Condition",
            params={"patient": patient_id, "_count": str(count)},
        )
        return _resources_from_bundle(bundle, "Condition")

    async def search_lab_observations(self, patient_id: str, count: int = 15) -> list[dict[str, Any]]:
        bundle = await self.search_bundle(
            "Observation",
            params={
                "patient": patient_id,
                "category": "laboratory",
                "_sort": "-date",
                "_count": str(count),
            },
        )
        return _resources_from_bundle(bundle, "Observation")

    async def search_observations_by_identifier(
        self,
        *,
        patient_id: str,
        system: str,
        value: str,
        count: int = 1,
    ) -> list[dict[str, Any]]:
        bundle = await self.search_bundle(
            "Observation",
            params={
                "patient": patient_id,
                "identifier": f"{system}|{value}",
                "_count": str(count),
            },
        )
        return _resources_from_bundle(bundle, "Observation")

    async def search_medication_requests(self, patient_id: str, count: int = 20) -> list[dict[str, Any]]:
        bundle = await self.search_bundle(
            "MedicationRequest",
            params={"patient": patient_id, "status": "active", "_count": str(count)},
        )
        return _resources_from_bundle(bundle, "MedicationRequest")

    async def search_allergy_intolerances(self, patient_id: str, count: int = 20) -> list[dict[str, Any]]:
        bundle = await self.search_bundle(
            "AllergyIntolerance",
            params={"patient": patient_id, "_count": str(count)},
        )
        return _resources_from_bundle(bundle, "AllergyIntolerance")

    async def search_document_references(self, patient_id: str, count: int = 10) -> list[dict[str, Any]]:
        bundle = await self.search_bundle(
            "DocumentReference",
            params={"patient": patient_id, "category": "clinical-note", "_count": str(count)},
        )
        return _resources_from_bundle(bundle, "DocumentReference")

    async def search_bundle(self, resource_type: str, params: dict[str, str]) -> dict[str, Any]:
        return await self._request_json("GET", f"/{resource_type}", params=params)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/fhir+json"}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return headers

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            verify=self._tls_verify,
        ) as client:
            response = await request_with_retries(
                client,
                method,
                f"{self._base_url}/{path.lstrip('/')}",
                policy=self._retry_policy,
                headers=self._headers(),
                params=params,
                json=json_body,
            )
            return cast(dict[str, Any], response.json())


def _patient_from_fhir(resource: dict[str, Any]) -> PatientSummary:
    patient_id = resource.get("id")
    if not isinstance(patient_id, str) or not patient_id:
        patient_id = "unknown"

    names = resource.get("name") or []
    display_name = patient_id
    if names:
        first = names[0]
        given = " ".join(first.get("given") or [])
        family = first.get("family") or ""
        display_name = " ".join(part for part in [given, family] if part).strip() or display_name

    return PatientSummary(
        patient_id=patient_id,
        display_name=display_name,
        birth_date=resource.get("birthDate"),
        gender=resource.get("gender"),
    )


def _patients_from_bundle(bundle: dict[str, Any]) -> list[PatientSummary]:
    patients: list[PatientSummary] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if not isinstance(resource, dict) or resource.get("resourceType") != "Patient":
            continue
        patients.append(_patient_from_fhir(resource))
    return patients


def _resources_from_bundle(bundle: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
            resources.append(resource)
    return resources


def capability_statement_supports_create(metadata: dict[str, Any], resource_type: str) -> bool:
    rest_entries = metadata.get("rest", [])
    if not isinstance(rest_entries, list):
        return False
    for rest_entry in rest_entries:
        if not isinstance(rest_entry, dict):
            continue
        resources = rest_entry.get("resource", [])
        if not isinstance(resources, list):
            continue
        for resource in resources:
            if not isinstance(resource, dict) or resource.get("type") != resource_type:
                continue
            interactions = resource.get("interaction", [])
            if not isinstance(interactions, list):
                return False
            return any(
                isinstance(interaction, dict) and interaction.get("code") == "create"
                for interaction in interactions
            )
    return False
