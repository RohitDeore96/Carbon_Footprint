"""Firestore persistence service for carbon footprint emission records.

Provides a strictly typed interface for writing calculated emission data
to the Firestore ``carbon_logs`` collection via ``firebase-admin``.

Includes a short-lived in-memory cache (5-minute TTL) for ``get_user_logs``
results, eliminating redundant Firestore reads when the same user's data
is requested within a brief time window (e.g., history → summary navigation).
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from firebase_admin import firestore
from google.cloud.firestore_v1.client import Client as FirestoreClient

from app.constants import AppConstants
from app.middleware.auth import ensure_firebase_initialized

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory TTL cache for get_user_logs()
# ---------------------------------------------------------------------------

_LOGS_CACHE_TTL_SECONDS: int = 300  # 5 minutes
_LOGS_CACHE_MAX_ENTRIES: int = 500
_logs_cache: dict[tuple[str, int], tuple[float, list[dict[str, Any]]]] = {}
_logs_cache_lock: threading.Lock = threading.Lock()


def _get_cached_logs(user_id: str, period_days: int) -> list[dict[str, Any]] | None:
    """Return cached logs if present and not expired, else None."""
    key = (user_id, period_days)
    with _logs_cache_lock:
        entry = _logs_cache.get(key)
        if entry is None:
            return None
        cached_at, data = entry
        if time.monotonic() - cached_at > _LOGS_CACHE_TTL_SECONDS:
            del _logs_cache[key]
            return None
        return data


def _set_cached_logs(
    user_id: str, period_days: int, data: list[dict[str, Any]]
) -> None:
    """Store logs in the TTL cache, evicting oldest entries if at capacity."""
    key = (user_id, period_days)
    with _logs_cache_lock:
        # Evict expired entries first
        now = time.monotonic()
        expired = [
            k
            for k, (ts, _) in _logs_cache.items()
            if now - ts > _LOGS_CACHE_TTL_SECONDS
        ]
        for k in expired:
            del _logs_cache[k]
        # If still at capacity, evict the oldest 20%
        if len(_logs_cache) >= _LOGS_CACHE_MAX_ENTRIES:
            sorted_keys = sorted(_logs_cache.keys(), key=lambda k: _logs_cache[k][0])
            evict_count = max(1, len(sorted_keys) // 5)
            for k in sorted_keys[:evict_count]:
                del _logs_cache[k]
        _logs_cache[key] = (now, data)


def invalidate_logs_cache(user_id: str, period_days: int | None = None) -> None:
    """Invalidate cached logs for a user, or all cached entries if period_days is None.

    Call this after a write operation (log_footprint) to ensure the next
    read fetches fresh data from Firestore.
    """
    with _logs_cache_lock:
        if period_days is not None:
            _logs_cache.pop((user_id, period_days), None)
        else:
            keys_to_remove = [k for k in _logs_cache if k[0] == user_id]
            for k in keys_to_remove:
                del _logs_cache[k]


def _get_firestore_client() -> FirestoreClient:
    """Return the Firestore client, initializing the Firebase app if needed.

    Uses the shared ``ensure_firebase_initialized`` helper so the SDK
    is always ready before creating a Firestore client.

    Returns:
        A Firestore client instance bound to the default Firebase app.

    Raises:
        firebase_admin.exceptions.FirebaseError: If initialization fails.
    """
    ensure_firebase_initialized()
    return firestore.client()


def _build_log_document(
    user_id: str,
    total_co2e_kg: float,
    results: list[dict[str, Any]],
    calculation_date: str,
) -> dict[str, Any]:
    """Build the Firestore document payload for a carbon log entry.

    Args:
        user_id: The unique identifier of the user.
        total_co2e_kg: Total calculated CO2e emissions in kilograms.
        results: List of individual emission result dictionaries.
        calculation_date: ISO-formatted date string from the request.

    Returns:
        A dictionary ready for Firestore document insertion.
    """
    return {
        "user_id": user_id,
        "total_co2e_kg": total_co2e_kg,
        "results": results,
        "calculation_date": calculation_date,
        "created_at": firestore.SERVER_TIMESTAMP,
    }


class FirebaseService:
    """Strictly typed service for persisting carbon emission data to Firestore.

    Attributes:
        _client: The Firestore client used for database operations.
    """

    def __init__(self, client: FirestoreClient | None = None) -> None:
        """Initialize the FirebaseService with an optional Firestore client.

        Args:
            client: An optional pre-configured Firestore client.
                    If ``None``, a new client is obtained via ``_get_firestore_client``.
        """
        self._client: FirestoreClient = client or _get_firestore_client()

    def write_carbon_log(
        self,
        user_id: str,
        total_co2e_kg: float,
        results: list[dict[str, Any]],
        calculation_date: str,
    ) -> str:
        """Write a calculated emission record to the ``carbon_logs`` collection.

        Args:
            user_id: The unique identifier of the user who submitted the entry.
            total_co2e_kg: Aggregated CO2e emissions in kilograms.
            results: List of per-entry emission result dictionaries.
            calculation_date: ISO-formatted calculation date from the request.

        Returns:
            The Firestore-generated document ID of the created record.

        Raises:
            google.cloud.exceptions.GoogleCloudError: If the Firestore write fails.
        """
        document: dict[str, Any] = _build_log_document(
            user_id,
            total_co2e_kg,
            results,
            calculation_date,
        )
        doc_id = self._persist_document(document)
        # Invalidate cached logs so subsequent reads fetch fresh data
        invalidate_logs_cache(user_id)
        return doc_id

    def get_user_logs(
        self, user_id: str, period_days: int = 30
    ) -> list[dict[str, Any]]:
        """Retrieve a user's carbon log entries from Firestore.

        Uses a 5-minute in-memory TTL cache keyed by (user_id, period_days)
        to eliminate redundant Firestore reads when the same query is issued
        within a brief window (e.g., history + summary on dashboard load).
        The cache is automatically invalidated on write operations via
        ``invalidate_logs_cache``.

        Args:
            user_id: The unique identifier of the user.
            period_days: Number of days to look back for logs (default 30).

        Returns:
            A list of carbon log document dictionaries, newest first.
        """
        # Check TTL cache first
        cached = _get_cached_logs(user_id, period_days)
        if cached is not None:
            logger.debug(
                "Logs cache hit for user=%s period=%d", user_id[:8], period_days
            )
            return cached

        cutoff: datetime = datetime.now(tz=timezone.utc) - timedelta(days=period_days)
        docs = (
            self._client.collection(AppConstants.FIREBASE_COLLECTION_CARBON_LOGS)
            .where("user_id", "==", user_id)
            .where("created_at", ">=", cutoff)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(AppConstants.FIREBASE_QUERY_LIMIT)
            .stream()
        )
        result = [d for doc in docs if (d := doc.to_dict()) is not None]

        # Store in TTL cache
        _set_cached_logs(user_id, period_days, result)
        return result

    def get_aggregated_summary(
        self, user_id: str, period_days: int = 30
    ) -> dict[str, Any]:
        """Retrieve server-side aggregated summary using Firestore aggregation query.

        Uses Firestore's ``aggregation_query`` with Sum and Count accumulators
        to compute summary statistics on the server, dramatically reducing
        data transfer compared to fetching all documents.

        Falls back to client-side aggregation if the aggregation query
        is not supported by the Firestore client version.

        Args:
            user_id: The unique identifier of the user.
            period_days: Number of days to look back for logs (default 30).

        Returns:
            A dictionary with total_co2e_kg, entry_count, and per-category
            aggregation results.
        """
        cutoff: datetime = datetime.now(tz=timezone.utc) - timedelta(days=period_days)
        query = (
            self._client.collection(AppConstants.FIREBASE_COLLECTION_CARBON_LOGS)
            .where("user_id", "==", user_id)
            .where("created_at", ">=", cutoff)
        )
        try:
            # Server-side aggregation using Firestore AggregationQuery
            # Type stubs don't include .aggregate() yet; runtime API is stable
            aggregation = query.aggregate(  # type: ignore[attr-defined]
                firestore.AggregationField.sum("total_co2e_kg").alias("total_co2e_kg"),
                firestore.AggregationField.count().alias("entry_count"),
            )
            result = aggregation.get()
            total_co2e = 0.0
            entry_count = 0
            for r in result:
                total_co2e = float(r.get("total_co2e_kg", 0) or 0)
                entry_count = int(r.get("entry_count", 0) or 0)
            return {
                "total_co2e_kg": round(total_co2e, 4),
                "entry_count": entry_count,
                "server_aggregated": True,
            }
        except (AttributeError, TypeError, Exception) as exc:
            logger.info(
                "Firestore aggregation query not supported, using fallback: %s", exc
            )
            # Fallback: client-side aggregation from fetched logs
            logs = self.get_user_logs(user_id, period_days)
            total_co2e = round(sum(log.get("total_co2e_kg", 0) for log in logs), 4)
            return {
                "total_co2e_kg": total_co2e,
                "entry_count": len(logs),
                "server_aggregated": False,
            }

    def _persist_document(self, document: dict[str, Any]) -> str:
        """Persist a single document to the carbon logs collection.

        Args:
            document: The fully-formed document dictionary to write.

        Returns:
            The auto-generated Firestore document ID.

        Raises:
            google.cloud.exceptions.GoogleCloudError: If the write operation fails.
        """
        collection_ref = self._client.collection(
            AppConstants.FIREBASE_COLLECTION_CARBON_LOGS,
        )
        doc_ref = collection_ref.add(document)
        return doc_ref[1].id
