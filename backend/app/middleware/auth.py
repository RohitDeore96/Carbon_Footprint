"""Firebase Authentication middleware for verifying ID tokens.

Provides a FastAPI dependency that verifies Firebase ID tokens
from the Authorization header. Generates a unique per-session
anonymous identity when no token is provided.
"""

import logging
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Verify Firebase ID token and return the user UID.

    If no Authorization header is provided, generates a unique anonymous
    identifier for this request cycle. This ensures data isolation even
    for unauthenticated users.

    Args:
        credentials: Optional Bearer token credentials extracted by FastAPI.

    Returns:
        The Firebase user UID string, or a unique anonymous identifier.

    Raises:
        HTTPException: 401 if the provided token is invalid, expired, or
            verification fails for any reason.
    """
    if credentials is None:
        anonymous_id = f"anon-{uuid.uuid4().hex[:12]}"
        logger.debug("No auth token provided; generated anonymous ID: %s", anonymous_id)
        return anonymous_id

    token = credentials.credentials
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except firebase_auth.ExpiredIdTokenError:
        logger.warning("Firebase token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please refresh the page.",
        ) from None
    except firebase_auth.InvalidIdTokenError as exc:
        logger.warning("Invalid ID token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token. Please refresh the page.",
        ) from None
    except ValueError as exc:
        logger.warning("Firebase token verification failed (ValueError): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token",
        ) from None
    except Exception as exc:
        # Catch-all for network errors, timeout, or any unexpected failure
        # during Firebase token verification. Return 401 so the frontend
        # can trigger a token refresh and retry.
        logger.error(
            "Unexpected error during Firebase token verification: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token verification failed. Please refresh and retry.",
        ) from None
