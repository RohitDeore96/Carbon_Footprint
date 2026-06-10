"""Firebase Authentication middleware for verifying ID tokens.

Provides a FastAPI dependency that verifies Firebase ID tokens
from the Authorization header. Generates a unique per-request
anonymous ID when no token is provided, ensuring data isolation
even for unauthenticated users.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError


_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Verify Firebase ID token and return the user UID.

    If no Authorization header is provided, generates a unique anonymous
    ID for this request to ensure data isolation. Each unauthenticated
    request gets a distinct ID, preventing cross-user data access.

    Args:
        credentials: Optional Bearer token credentials extracted by FastAPI.

    Returns:
        The Firebase user UID string, or a unique anonymous ID.

    Raises:
        HTTPException: 401 if the provided token is invalid or expired.
    """
    if credentials is None:
        # Generate a unique anonymous ID per request for data isolation
        return f"anon-{uuid.uuid4().hex[:12]}"

    try:
        token = credentials.credentials
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except FirebaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {exc.code}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token",
        ) from exc
