"""Simple Firestore-backed cache for AI-generated sustainability insights.

Caches Gemini responses using a hash of the input data as the key,
with a configurable TTL (default 24 hours).

Reuses the centralized ``ensure_firebase_initialized`` from
firebase_service to avoid duplicating Firebase initialization logic.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from firebase_admin import firestore as firebase_firestore
from google.cloud.firestore_v1.client import Client as FirestoreClient
from google.cloud.firestore_v1.document import DocumentSnapshot

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_HOURS: int = 24
CACHE_COLLECTION: str = "ai_insights_cache"


def _compute_cache_key(user_data: dict[str, Any]) -> str:
    """Compute a deterministic cache key from user emission data.

    Args:
        user_data: Dictionary with total_co2e_kg, period_days, emission_breakdown.

    Returns:
        SHA-256 hex digest of the sorted JSON representation.
    """
    canonical = json.dumps(user_data, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _get_db() -> FirestoreClient:
    """Return a shared Firestore client via the centralized Firebase initialization."""
    from app.services.firebase_service import ensure_firebase_initialized

    ensure_firebase_initialized()
    return firebase_firestore.client()


def get_cached_insight(
    user_data: dict[str, Any],
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
) -> dict[str, Any] | None:
    """Check Firestore for a cached insight matching the user data.

    Args:
        user_data: The emission data used as cache key input.
        ttl_hours: Cache entry time-to-live in hours.

    Returns:
        Cached insight dict if found and not expired, else None.
    """
    try:
        key = _compute_cache_key(user_data)
        db = _get_db()
        doc: DocumentSnapshot = db.collection(CACHE_COLLECTION).document(key).get()  # type: ignore[assignment]

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data is None:
            return None

        cached_at = data.get("cached_at")
        if cached_at is None:
            return None

        if isinstance(cached_at, datetime):
            expiry = cached_at + timedelta(hours=ttl_hours)
            if datetime.now(timezone.utc) > expiry:
                return None

        logger.info("Cache hit for insight key=%s", key[:8])
        return data.get("insight")

    except Exception as exc:
        logger.warning("Cache read failed, proceeding without cache: %s", exc)
        return None


def set_cached_insight(
    user_data: dict[str, Any],
    insight: dict[str, Any],
) -> None:
    """Store a generated insight in Firestore cache.

    Args:
        user_data: The emission data used as cache key input.
        insight: The AI-generated insight dictionary to cache.
    """
    try:
        key = _compute_cache_key(user_data)
        db = _get_db()
        db.collection(CACHE_COLLECTION).document(key).set(
            {
                "cached_at": firebase_firestore.SERVER_TIMESTAMP,
                "insight": insight,
                "cache_key_prefix": key[:8],
            }
        )
        logger.info("Cached insight key=%s", key[:8])
    except Exception as exc:
        logger.warning("Cache write failed, non-critical: %s", exc)


def cleanup_expired_cache_entries(
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    batch_size: int = 100,
) -> int:
    """Delete expired entries from the ai_insights_cache Firestore collection.

    This function should be called periodically (e.g., via a Cloud Scheduler
    job or a lightweight cron task) to prevent unbounded cache growth.

    Documents are considered expired when their ``cached_at`` timestamp
    plus ``ttl_hours`` is older than the current UTC time.

    Args:
        ttl_hours: The TTL in hours used to determine expiry. Defaults to
            DEFAULT_CACHE_TTL_HOURS (24).
        batch_size: Maximum number of documents to delete in a single call.
            Firestore batch writes support up to 500 operations.

    Returns:
        The number of expired documents deleted.
    """
    try:
        db = _get_db()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)

        # Query all cache documents — since cached_at is not always a native
        # Firestore timestamp (it may be stored as an ISO string), we fetch
        # and filter in Python to avoid index requirements.
        docs = db.collection(CACHE_COLLECTION).limit(batch_size).stream()

        deleted_count = 0
        batch = db.batch()
        ops_in_batch = 0

        for doc in docs:
            data = doc.to_dict()
            if data is None:
                continue

            cached_at = data.get("cached_at")
            if cached_at is None:
                continue

            # Handle both datetime objects and ISO string representations
            if isinstance(cached_at, str):
                try:
                    cached_at = datetime.fromisoformat(cached_at)
                except (ValueError, TypeError):
                    continue

            if isinstance(cached_at, datetime):
                # Ensure timezone-aware comparison
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
                if cached_at < cutoff:
                    batch.delete(doc.reference)
                    ops_in_batch += 1
                    deleted_count += 1

                    # Firestore batches support max 500 operations
                    if ops_in_batch >= 499:
                        batch.commit()
                        batch = db.batch()
                        ops_in_batch = 0

        # Commit any remaining deletions
        if ops_in_batch > 0:
            batch.commit()

        if deleted_count > 0:
            logger.info(
                "Cleaned up %d expired cache entries from %s",
                deleted_count,
                CACHE_COLLECTION,
            )
        return deleted_count

    except Exception as exc:
        logger.warning("Cache cleanup failed, non-critical: %s", exc)
        return 0
