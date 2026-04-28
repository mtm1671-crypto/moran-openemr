import pytest
import respx
from httpx import Response

from app.config import Settings
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
