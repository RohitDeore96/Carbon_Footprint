"""Firestore persistence service for carbon footprint emission records.

Provides a strictly typed interface for writing calculated emission data
to the Firestore ``carbon_logs`` collection via ``firebase-admin``.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from firebase_admin import firestore
from google.cloud.firestore_v1.client import Client as FirestoreClient

from app.constants import AppConstants
from app.middleware.auth import ensure_firebase_initialized


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
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
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
        return self._persist_document(document)

    def get_user_logs(
        self, user_id: str, period_days: int = 30
    ) -> list[dict[str, Any]]:
        """Retrieve a user's carbon log entries from Firestore.

        Args:
            user_id: The unique identifier of the user.
            period_days: Number of days to look back for logs (default 30).

        Returns:
            A list of carbon log document dictionaries, newest first.
        """
        cutoff: str = (
            datetime.now(tz=timezone.utc) - timedelta(days=period_days)
        ).isoformat()
        docs = (
            self._client.collection(AppConstants.FIREBASE_COLLECTION_CARBON_LOGS)
            .where("user_id", "==", user_id)
            .where("created_at", ">=", cutoff)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(AppConstants.FIREBASE_QUERY_LIMIT)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

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
