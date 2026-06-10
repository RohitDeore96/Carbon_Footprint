"""Firebase Authentication middleware for verifying ID tokens.

Provides a FastAPI dependency that verifies Firebase ID tokens
from the Authorization header. Generates a unique per-session
anonymous identity when no token is provided.

Also provides a shared ``verify_user_access`` function used by
route handlers to enforce data-isolation (users can only access
their own data, including anonymous users).

Ensures the Firebase Admin SDK is initialized before attempting
token verification — handles the common deployment issue where
the SDK is not initialized at startup.

**Anonymous User Data Persistence**:

The frontend uses Firebase Anonymous Auth, which provides a persistent
UID stored in localStorage. When the frontend sends this UID as a Bearer
token, the backend verifies it via Firebase Auth and uses the verified UID
for all operations — ensuring data continuity across page refreshes and
browser sessions.

If NO token is provided (e.g., direct API call without Firebase Auth),
the backend generates a new ephemeral ``anon-{uuid}`` ID for that request
only. Data created under this ephemeral ID is not recoverable across
sessions — this is by design for API-only usage.

**Recovery mechanism**: If the Firebase anonymous session expires (default
30 days) or localStorage is cleared, the user's previously logged data
remains in Firestore under the old anonymous UID. To recover it, the user
can sign in with the same Firebase anonymous credentials before the session
expires, or an admin can look up data by the old UID in the Firestore
console. Future enhancement: add an account linking flow to merge anonymous
data into a permanent authenticated account.
"""

import logging
import os
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, initialize_app, get_app

from app.constants import AppConstants

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

_firebase_app_initialized = False


def ensure_firebase_initialized() -> None:
    """Ensure the Firebase Admin SDK is initialized before token verification.

    This is called on every authenticated request to guarantee the SDK
    is ready. On Cloud Run with Application Default Credentials, this
    is idempotent — subsequent calls are no-ops after the first init.
    """
    global _firebase_app_initialized
    if _firebase_app_initialized:
        return
    try:
        get_app()
        _firebase_app_initialized = True
        logger.info("Firebase Admin SDK already initialized")
    except ValueError:
        try:
            options = {
                "projectId": os.environ.get(
                    "GOOGLE_CLOUD_PROJECT", "carbon-footprint-12"
                ),
            }
            initialize_app(credential=credentials.ApplicationDefault(), options=options)
            _firebase_app_initialized = True
            logger.info(
                "Firebase Admin SDK initialized successfully (project=%s)",
                options["projectId"],
            )
        except Exception as exc:
            logger.error("Failed to initialize Firebase Admin SDK: %s", exc)
            # Don't set _firebase_app_initialized — retry on next request


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
            malformed.
        HTTPException: 503 if the Firebase Auth service is unreachable or
            the SDK is not properly configured (transient server-side issue).
    """
    if credentials is None:
        anonymous_id = f"{AppConstants.ANONYMOUS_ID_PREFIX}{uuid.uuid4().hex[:12]}"
        logger.debug("No auth token provided; generated anonymous ID: %s", anonymous_id)
        return anonymous_id

    # Ensure Firebase Admin SDK is initialized before verification
    ensure_firebase_initialized()

    token = credentials.credentials
    try:
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
        return decoded["uid"]
    except firebase_auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked. Please sign in again.",
        ) from None
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
        # ValueError can mean either a malformed token OR the Firebase
        # Admin SDK is not initialized. Distinguish by checking the message.
        msg = str(exc)
        if "does not exist" in msg or "initialize" in msg:
            logger.error(
                "Firebase Admin SDK not initialized during token verification: %s",
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is not ready. Please retry in a moment.",
            ) from None
        logger.warning("Firebase token verification failed (ValueError): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token",
        ) from None
    except (
        ConnectionError,
        TimeoutError,
        OSError,
    ) as exc:
        # Network / connectivity issues reaching Firebase Auth — these are
        # server-side transient problems, NOT client authentication errors.
        logger.error("Firebase Auth service unreachable: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable. Please retry.",
        ) from None
    except Exception as exc:
        # Catch-all for any other unexpected failure during Firebase token
        # verification. Return 503 (not 401) so the frontend does NOT
        # treat this as a credentials issue or trigger token refresh.
        logger.error(
            "Unexpected error during Firebase token verification: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service error. Please refresh and retry.",
        ) from None


def verify_user_access(
    authenticated_uid: str,
    requested_user_id: str,
    context: str = "",
) -> str:
    """Verify the authenticated user has access to the requested user's data.

    Users can only access their own data. Anonymous IDs (prefixed with
    ``ANONYMOUS_ID_PREFIX``) are restricted to accessing only data that
    matches their own auto-generated anonymous identifier — they cannot
    access data belonging to any other user_id.

    Args:
        authenticated_uid: UID from Firebase ID token, or generated anonymous ID.
        requested_user_id: The user_id from the URL path or request payload.
        context: Optional label identifying the calling route (e.g. "footprint"
            or "ai") for structured logging.

    Returns:
        The effective user_id to use for the query.

    Raises:
        HTTPException: 403 if the user tries to access another user's data.
    """
    if authenticated_uid.startswith(AppConstants.ANONYMOUS_ID_PREFIX):
        if authenticated_uid != requested_user_id:
            logger.warning(
                "Anonymous user %s attempted to access data for user_id %s%s",
                authenticated_uid,
                requested_user_id,
                f" (context: {context})" if context else "",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: users can only access their own data",
            )
        return authenticated_uid
    if authenticated_uid != requested_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: users can only access their own data",
        )
    return authenticated_uid
