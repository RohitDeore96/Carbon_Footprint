"""Admin routes for the Carbon Footprint Awareness Platform.

Provides internal operations such as scheduled cache cleanup,
intended to be called by Cloud Scheduler or similar automation.
All admin endpoints require an ``X-Admin-Key`` header matching
the ``ADMIN_API_KEY`` environment variable.
"""

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, status

from app.services.insights_cache import cleanup_expired_cache_entries
from app.services.migration import get_migration_status

router: APIRouter = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _verify_admin_key(admin_key: str | None) -> None:
    """Validate the admin API key from the request header.

    Args:
        admin_key: The value of the X-Admin-Key header, or None if missing.

    Raises:
        HTTPException: 503 if no key is configured on the server.
        HTTPException: 401 if the provided key does not match.
    """
    configured_key = os.environ.get("ADMIN_API_KEY", "")
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints not configured. Set ADMIN_API_KEY environment variable.",
        )
    if not hmac.compare_digest(admin_key or "", configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key.",
        )


@router.post(
    "/cleanup-cache",
    status_code=status.HTTP_200_OK,
)
async def trigger_cache_cleanup(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
) -> dict:
    """Trigger cleanup of expired cache entries in Firestore.

    Intended to be called by Cloud Scheduler on a periodic basis.
    Requires the ``X-Admin-Key`` header to match the ``ADMIN_API_KEY``
    environment variable.

    Args:
        x_admin_key: The admin API key from the request header.

    Returns:
        A dictionary containing the number of expired entries deleted.

    Raises:
        HTTPException: 503 if ADMIN_API_KEY is not configured.
        HTTPException: 401 if the admin key does not match.
    """
    _verify_admin_key(x_admin_key)
    deleted_count: int = cleanup_expired_cache_entries()
    return {"deleted_count": deleted_count}


@router.get(
    "/migration-status",
    status_code=status.HTTP_200_OK,
)
async def get_schema_migration_status(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
) -> dict:
    """Retrieve the current Firestore schema migration status.

    Returns the current schema version and list of registered migrations.
    Requires the ``X-Admin-Key`` header for authentication.

    Args:
        x_admin_key: The admin API key from the request header.

    Returns:
        A dictionary with schema version and migration details.

    Raises:
        HTTPException: 503 if ADMIN_API_KEY is not configured.
        HTTPException: 401 if the admin key does not match.
    """
    _verify_admin_key(x_admin_key)
    return get_migration_status()
