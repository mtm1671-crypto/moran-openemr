from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.models import RequestUser, Role


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

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OpenEMR JWT validation is not implemented yet",
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    return token or None
