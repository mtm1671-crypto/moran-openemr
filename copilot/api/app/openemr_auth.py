from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import Settings
from app.http_retry import RetryPolicy, request_with_retries
from app.models import RequestUser


class OpenEMRTokenError(RuntimeError):
    pass


class DevPasswordGrantTokenProvider:
    """Local-only token provider for the OpenEMR development stack.

    Production should use SMART authorization code flow in the browser and pass
    the user's OpenEMR access token to the API. This provider exists so local
    integration tests can exercise real FHIR endpoints without completing the
    browser OAuth flow first.
    """

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._expires_at: datetime | None = None

    def clear(self) -> None:
        self._access_token = None
        self._expires_at = None

    async def get_access_token(self, settings: Settings) -> str:
        if self._access_token and self._expires_at and self._expires_at > datetime.now(tz=UTC):
            return self._access_token

        token_url = _token_url(settings)
        if (
            token_url is None
            or settings.openemr_client_id is None
            or settings.openemr_dev_username is None
            or settings.openemr_dev_password is None
        ):
            raise OpenEMRTokenError("OpenEMR dev password grant is not fully configured")

        data: dict[str, str] = {
            "grant_type": "password",
            "client_id": settings.openemr_client_id,
            "scope": settings.openemr_dev_scopes,
            "user_role": "users",
            "username": settings.openemr_dev_username,
            "password": settings.openemr_dev_password.get_secret_value(),
        }
        if settings.openemr_client_secret is not None:
            data["client_secret"] = settings.openemr_client_secret.get_secret_value()

        try:
            async with httpx.AsyncClient(
                timeout=settings.openemr_request_timeout_seconds,
                verify=settings.openemr_tls_verify,
            ) as client:
                response = await request_with_retries(
                    client,
                    "POST",
                    token_url,
                    policy=_openemr_retry_policy(settings),
                    data=data,
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPStatusError as exc:
            raise OpenEMRTokenError(_token_error_message(exc.response)) from exc
        except httpx.HTTPError as exc:
            raise OpenEMRTokenError("OpenEMR token endpoint request failed") from exc

        if response.status_code >= 400:
            raise OpenEMRTokenError(_token_error_message(response))

        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise OpenEMRTokenError("OpenEMR token response did not include access_token")

        expires_in = int(payload.get("expires_in") or 60)
        self._access_token = access_token
        self._expires_at = datetime.now(tz=UTC) + timedelta(seconds=max(expires_in - 10, 1))
        return access_token


_dev_password_provider = DevPasswordGrantTokenProvider()


class ServiceAccountTokenProvider:
    """Backend-only OpenEMR token provider for worker/reindex jobs.

    This path is intentionally separate from clinician OAuth sessions. It uses
    either a configured static service bearer token or client credentials.
    """

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._expires_at: datetime | None = None

    def clear(self) -> None:
        self._access_token = None
        self._expires_at = None

    async def get_access_token(self, settings: Settings) -> str:
        if settings.openemr_service_bearer_token is not None:
            return settings.openemr_service_bearer_token.get_secret_value()
        if self._access_token and self._expires_at and self._expires_at > datetime.now(tz=UTC):
            return self._access_token

        token_url = _service_token_url(settings)
        if (
            token_url is None
            or settings.openemr_service_client_id is None
            or settings.openemr_service_client_secret is None
        ):
            raise OpenEMRTokenError("OpenEMR service account is not fully configured")

        data = {
            "grant_type": "client_credentials",
            "client_id": settings.openemr_service_client_id,
            "client_secret": settings.openemr_service_client_secret.get_secret_value(),
            "scope": settings.openemr_service_scopes,
        }
        try:
            async with httpx.AsyncClient(
                timeout=settings.openemr_request_timeout_seconds,
                verify=settings.openemr_tls_verify,
            ) as client:
                response = await request_with_retries(
                    client,
                    "POST",
                    token_url,
                    policy=_openemr_retry_policy(settings),
                    data=data,
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPStatusError as exc:
            raise OpenEMRTokenError(_token_error_message(exc.response)) from exc
        except httpx.HTTPError as exc:
            raise OpenEMRTokenError("OpenEMR service token endpoint request failed") from exc

        if response.status_code >= 400:
            raise OpenEMRTokenError(_token_error_message(response))

        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise OpenEMRTokenError("OpenEMR service token response did not include access_token")

        expires_in = int(payload.get("expires_in") or 60)
        self._access_token = access_token
        self._expires_at = datetime.now(tz=UTC) + timedelta(seconds=max(expires_in - 10, 1))
        return access_token


_service_account_provider = ServiceAccountTokenProvider()


def clear_dev_password_token_cache() -> None:
    _dev_password_provider.clear()
    _service_account_provider.clear()


async def resolve_fhir_bearer_token(user: RequestUser, settings: Settings) -> str | None:
    if user.access_token:
        return user.access_token

    if settings.app_env == "local" and settings.openemr_dev_password_grant:
        try:
            return await _dev_password_provider.get_access_token(settings)
        except OpenEMRTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenEMR dev token request failed: {exc}",
            ) from exc

    return None


async def resolve_service_fhir_bearer_token(settings: Settings) -> str:
    if not settings.openemr_service_account_enabled:
        raise OpenEMRTokenError("OpenEMR service account is disabled")
    return await _service_account_provider.get_access_token(settings)


def _token_url(settings: Settings) -> str | None:
    if settings.openemr_oauth_token_url is not None:
        return str(settings.openemr_oauth_token_url)
    if settings.openemr_base_url is None:
        return None
    return f"{str(settings.openemr_base_url).rstrip('/')}/oauth2/{settings.openemr_site}/token"


def _service_token_url(settings: Settings) -> str | None:
    if settings.openemr_service_token_url is not None:
        return str(settings.openemr_service_token_url)
    return _token_url(settings)


def _openemr_retry_policy(settings: Settings) -> RetryPolicy:
    return RetryPolicy(
        attempts=settings.openemr_retry_attempts,
        backoff_seconds=settings.openemr_retry_backoff_seconds,
    )


def _token_error_message(response: httpx.Response) -> str:
    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    message = payload.get("error_description") or payload.get("message") or payload.get("error")
    if isinstance(message, str) and message:
        return message
    return f"HTTP {response.status_code}"
