from typing import Annotated
from typing import Any
from typing import cast

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt  # type: ignore[import-untyped]

from app.config import Settings, get_settings
from app.models import RequestUser, Role

_ALLOWED_JWT_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}


async def get_request_user(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> RequestUser:
    """Return the authenticated request user.

    The scaffold supports a local bypass so frontend/API work can start before
    SMART token validation is wired. Production must validate OpenEMR JWTs
    against JWKS on every request.
    """

    bearer_token = _extract_bearer_token(authorization)

    if settings.dev_auth_bypass and settings.app_env == "local":
        return RequestUser(
            user_id="dev-doctor",
            role=Role.doctor,
            scopes=["patient/*.read", "user/Practitioner.read"],
            practitioner_id="dev-practitioner",
            access_token=bearer_token,
        )

    if bearer_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    return await validate_openemr_jwt(bearer_token, settings)


async def validate_openemr_jwt(token: str, settings: Settings) -> RequestUser:
    if settings.openemr_jwks_url is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OpenEMR JWKS URL is not configured",
        )

    header = _unverified_header(token)
    algorithm = header.get("alg")
    if not isinstance(algorithm, str) or algorithm not in _ALLOWED_JWT_ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported bearer token algorithm",
        )

    jwks = await _fetch_jwks(settings)
    key = _matching_jwk(header, jwks)
    options = {"verify_aud": settings.openemr_jwt_audience is not None}

    try:
        claims = cast(
            dict[str, Any],
            jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=settings.openemr_jwt_audience,
                issuer=settings.openemr_jwt_issuer,
                options=options,
            ),
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OpenEMR bearer token",
        ) from exc

    return RequestUser(
        user_id=_claim_string(claims, "sub") or _claim_string(claims, "preferred_username") or "unknown",
        role=_role_from_claims(claims, settings),
        scopes=_scopes_from_claims(claims),
        practitioner_id=_practitioner_id_from_claims(claims),
        organization_id=_claim_string(claims, "organization_id"),
        access_token=token,
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    return token or None


def _unverified_header(token: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], jwt.get_unverified_header(token))
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token header",
        ) from exc


async def _fetch_jwks(settings: Settings) -> dict[str, Any]:
    assert settings.openemr_jwks_url is not None
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=settings.openemr_tls_verify) as client:
            response = await client.get(str(settings.openemr_jwks_url))
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenEMR JWKS retrieval failed",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenEMR JWKS response was not valid JSON",
        ) from exc


def _matching_jwk(header: dict[str, Any], jwks: dict[str, Any]) -> dict[str, Any]:
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not keys:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenEMR JWKS did not include signing keys",
        )

    token_kid = header.get("kid")
    if isinstance(token_kid, str) and token_kid:
        for key in keys:
            if isinstance(key, dict) and key.get("kid") == token_kid:
                return cast(dict[str, Any], key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token signing key was not found",
        )

    if len(keys) == 1 and isinstance(keys[0], dict):
        return cast(dict[str, Any], keys[0])

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bearer token did not include a key id",
    )


def _role_from_claims(claims: dict[str, Any], settings: Settings) -> Role:
    role_claims = [
        settings.openemr_role_claim,
        "role",
        "roles",
        "groups",
        "user_role",
        "acl_role",
    ]
    candidates: list[str] = []
    for claim_name in role_claims:
        candidates.extend(_claim_values(claims.get(claim_name)))

    for candidate in candidates:
        normalized = candidate.lower().strip()
        if normalized in {"doctor", "physician", "provider", "clinician"}:
            return Role.doctor
        if normalized in {"np_pa", "np/pa", "np", "pa", "nurse practitioner", "physician assistant"}:
            return Role.np_pa
        if normalized == "nurse":
            return Role.nurse
        if normalized in {"ma", "medical assistant"}:
            return Role.ma
        if normalized in {"admin", "administrator"}:
            return Role.admin

    if settings.openemr_default_role is not None:
        return settings.openemr_default_role

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="OpenEMR token role is not mapped to a Co-Pilot role",
    )


def _scopes_from_claims(claims: dict[str, Any]) -> list[str]:
    scopes: list[str] = []
    for claim_name in ["scope", "scp"]:
        scopes.extend(_claim_values(claims.get(claim_name)))
    return scopes


def _claim_values(value: Any) -> list[str]:
    if isinstance(value, str):
        if " " in value:
            return [item for item in value.split(" ") if item]
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _claim_string(claims: dict[str, Any], claim_name: str) -> str | None:
    value = claims.get(claim_name)
    return value if isinstance(value, str) and value else None


def _practitioner_id_from_claims(claims: dict[str, Any]) -> str | None:
    direct = _claim_string(claims, "practitioner_id")
    if direct is not None:
        return direct

    fhir_user = _claim_string(claims, "fhirUser")
    if fhir_user is None:
        return None

    marker = "Practitioner/"
    if marker not in fhir_user:
        return None
    return fhir_user.split(marker, 1)[1].split("/", 1)[0]
