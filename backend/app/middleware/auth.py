"""Firebase Authentication middleware for verifying ID tokens.

Provides an optional FastAPI dependency that verifies Firebase ID tokens
from the Authorization header. Falls back to allowing unauthenticated
requests for backward compatibility.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from app.constants import AppConstants

# Bearer token scheme — auto_error=False means the dependency
# won't raise if no Authorization header is present.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Verify Firebase ID token and return the user UID.

    If no Authorization header is provided, returns the anonymous sentinel
    value for backward compatibility with unauthenticated requests.

    Args:
        credentials: Optional Bearer token credentials extracted by FastAPI.

    Returns:
        The Firebase user UID string, or AppConstants.ANONYMOUS_USER_ID
        if no token is provided.

    Raises:
        HTTPException: 401 if the provided token is invalid or expired.
    """
    if credentials is None:
        # Allow unauthenticated requests for backward compatibility
        return AppConstants.ANONYMOUS_USER_ID

    try:
        token = credentials.credentials
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from None
