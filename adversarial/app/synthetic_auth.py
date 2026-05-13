"""Synthetic clinician auth for deployed adversarial target runs."""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class SyntheticAuthError(RuntimeError):
    pass


async def resolve_synthetic_clinician_token(settings: Settings) -> str | None:
    if settings.synthetic_clinician_token:
        return settings.synthetic_clinician_token
    if not settings.has_synthetic_clinician_auth:
        return None

    assert settings.synthetic_clinician_token_url is not None
    assert settings.synthetic_clinician_client_id is not None
    assert settings.synthetic_clinician_username is not None
    assert settings.synthetic_clinician_password is not None

    data: dict[str, str] = {
        "grant_type": "password",
        "client_id": settings.synthetic_clinician_client_id,
        "scope": settings.synthetic_clinician_scopes,
        "user_role": "users",
        "username": settings.synthetic_clinician_username,
        "password": settings.synthetic_clinician_password.get_secret_value(),
    }
    if settings.synthetic_clinician_client_secret is not None:
        data["client_secret"] = settings.synthetic_clinician_client_secret.get_secret_value()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.synthetic_clinician_token_url,
                data=data,
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise SyntheticAuthError("synthetic clinician token request failed") from exc

    if response.status_code >= 400:
        raise SyntheticAuthError(_token_error_message(response))

    try:
        payload = response.json()
    except ValueError as exc:
        raise SyntheticAuthError("synthetic clinician token response was not JSON") from exc

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise SyntheticAuthError("synthetic clinician token response did not include access_token")
    return access_token


def _token_error_message(response: httpx.Response) -> str:
    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        return f"synthetic clinician token request returned HTTP {response.status_code}"
    message = payload.get("error_description") or payload.get("message") or payload.get("error")
    if isinstance(message, str) and message:
        return message
    return f"synthetic clinician token request returned HTTP {response.status_code}"
