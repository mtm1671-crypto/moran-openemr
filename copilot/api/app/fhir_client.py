from typing import Any, cast

import httpx

from app.config import Settings
from app.models import PatientSummary


class OpenEMRFhirClient:
    def __init__(self, settings: Settings, bearer_token: str | None = None) -> None:
        if settings.openemr_fhir_base_url is None:
            raise ValueError("OPENEMR_FHIR_BASE_URL is required")
        self._base_url = str(settings.openemr_fhir_base_url).rstrip("/")
        self._bearer_token = bearer_token

    async def metadata(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/metadata",
                headers=self._headers(),
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def read_resource(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/{resource_type}/{resource_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def get_patient(self, patient_id: str) -> dict[str, Any]:
        return await self.read_resource("Patient", patient_id)

    async def search_patients(self, query: str, count: int = 20) -> list[PatientSummary]:
        params = {"name": query, "_count": str(count)}
        bundle = await self.search_bundle("Patient", params=params)

        patients: list[PatientSummary] = []
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") != "Patient":
                continue
            patients.append(_patient_from_fhir(resource))
        return patients

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

    async def search_bundle(self, resource_type: str, params: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/{resource_type}",
                params=params,
                headers=self._headers(),
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/fhir+json"}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return headers


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


def _resources_from_bundle(bundle: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
            resources.append(resource)
    return resources
