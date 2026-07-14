import os
import secrets

from fastapi import Header, HTTPException, status


INTERNAL_TOKEN_HEADER = "X-Internal-Token"
INTERNAL_TOKEN_ENV = "APP_AI_PYTHON_INTERNAL_TOKEN"
SHARED_INTERNAL_TOKEN_ENV = "APP_INTERNAL_API_TOKEN"


def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias=INTERNAL_TOKEN_HEADER),
) -> None:
    """Require a configured service credential for Java-to-Python business calls."""
    expected_token = (
        os.getenv(INTERNAL_TOKEN_ENV, "").strip()
        or os.getenv(SHARED_INTERNAL_TOKEN_ENV, "").strip()
    )
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "internal_auth_not_configured",
                "message": "Internal service authentication is unavailable.",
            },
        )

    if x_internal_token is None or not secrets.compare_digest(x_internal_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_internal_token",
                "message": "Valid internal service credentials are required.",
            },
            headers={"WWW-Authenticate": "InternalToken"},
        )
