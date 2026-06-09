"""Simple Firestore-backed cache for AI-generated sustainability insights.

Caches Gemini responses using a hash of the input data as the key,
with a configurable TTL (default 24 hours).
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from firebase_admin import firestore
from google.cloud.firestore_v1.client import Client as FirestoreClient

from app.services.firebase_service import _get_firestore_client

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
    """Return a shared Firestore client via the centralised firebase_service module."""
    return _get_firestore_client()


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
        doc = db.collection(CACHE_COLLECTION).document(key).get()

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
                "cached_at": datetime.now(timezone.utc),
                "insight": insight,
                "cache_key_prefix": key[:8],
            }
        )
        logger.info("Cached insight key=%s", key[:8])
    except Exception as exc:
        logger.warning("Cache write failed, non-critical: %s", exc)
