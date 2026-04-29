from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import Response
from jose import jwt
from jose.utils import base64url_encode

from app.config import Settings
from app.auth import validate_openemr_jwt
from app.openemr_auth import DevPasswordGrantTokenProvider


@pytest.mark.asyncio
@respx.mock
async def test_dev_password_grant_requests_openemr_token() -> None:
    route = respx.post("http://openemr.test/oauth2/default/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "dev-token",
                "expires_in": 60,
                "token_type": "Bearer",
            },
        )
    )
    provider = DevPasswordGrantTokenProvider()
    settings = Settings(
        openemr_base_url="http://openemr.test",
        openemr_client_id="client-id",
        openemr_client_secret="client-secret",
        openemr_dev_username="admin",
        openemr_dev_password="pass",
        openemr_dev_scopes="openid api:oemr api:fhir user/Patient.read",
    )

    token = await provider.get_access_token(settings)

    assert token == "dev-token"
    form = route.calls[0].request.content.decode()
    assert "grant_type=password" in form
    assert "client_id=client-id" in form
    assert "client_secret=client-secret" in form
    assert "username=admin" in form
    assert "password=pass" in form


@pytest.mark.asyncio
@respx.mock
async def test_dev_password_grant_caches_token() -> None:
    route = respx.post("http://openemr.test/oauth2/default/token").mock(
        return_value=Response(200, json={"access_token": "cached-token", "expires_in": 60})
    )
    provider = DevPasswordGrantTokenProvider()
    settings = Settings(
        openemr_base_url="http://openemr.test",
        openemr_client_id="client-id",
        openemr_dev_username="admin",
        openemr_dev_password="pass",
    )

    assert await provider.get_access_token(settings) == "cached-token"
    assert await provider.get_access_token(settings) == "cached-token"
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_validate_openemr_jwt_uses_jwks_and_maps_request_user() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _signed_token(
        private_key,
        {
            "sub": "openemr-user-1",
            "iss": "https://openemr.test",
            "aud": "clinical-copilot",
            "exp": int((datetime.now(tz=UTC) + timedelta(minutes=5)).timestamp()),
            "role": "Physician",
            "scope": "patient/*.read user/Practitioner.read",
            "fhirUser": "https://openemr.test/apis/default/fhir/Practitioner/practitioner-1",
            "organization_id": "org-1",
        },
    )
    respx.get("https://openemr.test/oauth2/default/jwks").mock(
        return_value=Response(200, json={"keys": [_public_jwk(private_key)]})
    )
    settings = Settings(
        app_env="production",
        dev_auth_bypass=False,
        openemr_jwks_url="https://openemr.test/oauth2/default/jwks",
        openemr_jwt_issuer="https://openemr.test",
        openemr_jwt_audience="clinical-copilot",
    )

    user = await validate_openemr_jwt(token, settings)

    assert user.user_id == "openemr-user-1"
    assert user.role == "doctor"
    assert user.scopes == ["patient/*.read", "user/Practitioner.read"]
    assert user.practitioner_id == "practitioner-1"
    assert user.organization_id == "org-1"


@pytest.mark.asyncio
@respx.mock
async def test_validate_openemr_jwt_rejects_unmapped_role_without_default() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _signed_token(
        private_key,
        {
            "sub": "openemr-user-1",
            "exp": int((datetime.now(tz=UTC) + timedelta(minutes=5)).timestamp()),
            "role": "Billing",
        },
    )
    respx.get("https://openemr.test/oauth2/default/jwks").mock(
        return_value=Response(200, json={"keys": [_public_jwk(private_key)]})
    )
    settings = Settings(
        app_env="production",
        dev_auth_bypass=False,
        openemr_jwks_url="https://openemr.test/oauth2/default/jwks",
    )

    with pytest.raises(Exception) as exc:
        await validate_openemr_jwt(token, settings)

    assert getattr(exc.value, "status_code") == 403


def _signed_token(private_key: rsa.RSAPrivateKey, claims: dict[str, object]) -> str:
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": "test-key"})


def _public_jwk(private_key: rsa.RSAPrivateKey) -> dict[str, str]:
    public_numbers = private_key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "kid": "test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _base64url_uint(public_numbers.n),
        "e": _base64url_uint(public_numbers.e),
    }


def _base64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64url_encode(value.to_bytes(length, "big")).decode("ascii")
