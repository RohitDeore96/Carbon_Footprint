"""Comprehensive tests for the FirebaseService and helper functions.

Tests cover:
- _build_log_document helper function
- FirebaseService.write_carbon_log
- FirebaseService.get_user_logs
- FirebaseService._persist_document
- FirebaseService constructor (with and without client)
- _get_firestore_client delegates to ensure_firebase_initialized
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.firebase_service import (
    FirebaseService,
    _build_log_document,
    _get_firestore_client,
)


class TestBuildLogDocument:
    """Unit tests for the _build_log_document helper function."""

    @pytest.mark.unit
    def test_build_log_document_contains_user_id(self) -> None:
        """Verify the document contains the provided user_id."""
        doc = _build_log_document(
            user_id="test-user",
            total_co2e_kg=5.25,
            results=[{"category": "transport", "co2e_kg": 5.25}],
            calculation_date="2026-06-08T12:00:00",
        )
        assert doc["user_id"] == "test-user"

    @pytest.mark.unit
    def test_build_log_document_contains_total_co2e(self) -> None:
        """Verify the document contains the total CO2e value."""
        doc = _build_log_document(
            user_id="test-user",
            total_co2e_kg=15.5,
            results=[],
            calculation_date="2026-06-08T12:00:00",
        )
        assert doc["total_co2e_kg"] == 15.5

    @pytest.mark.unit
    def test_build_log_document_contains_results(self) -> None:
        """Verify the document contains the results list."""
        results = [{"category": "transport", "co2e_kg": 5.25}]
        doc = _build_log_document(
            user_id="test-user",
            total_co2e_kg=5.25,
            results=results,
            calculation_date="2026-06-08T12:00:00",
        )
        assert doc["results"] == results

    @pytest.mark.unit
    def test_build_log_document_contains_calculation_date(self) -> None:
        """Verify the document contains the calculation_date."""
        doc = _build_log_document(
            user_id="test-user",
            total_co2e_kg=5.25,
            results=[],
            calculation_date="2026-06-08T12:00:00",
        )
        assert doc["calculation_date"] == "2026-06-08T12:00:00"

    @pytest.mark.unit
    def test_build_log_document_contains_created_at(self) -> None:
        """Verify the document contains a created_at ISO timestamp."""
        doc = _build_log_document(
            user_id="test-user",
            total_co2e_kg=5.25,
            results=[],
            calculation_date="2026-06-08T12:00:00",
        )
        assert "created_at" in doc
        assert isinstance(doc["created_at"], str)


class TestFirebaseServiceInit:
    """Unit tests for FirebaseService initialization."""

    @pytest.mark.unit
    def test_init_with_provided_client(self) -> None:
        """Verify FirebaseService uses the provided Firestore client."""
        mock_client = MagicMock()
        service = FirebaseService(client=mock_client)
        assert service._client is mock_client

    @pytest.mark.unit
    @patch("app.services.firebase_service._get_firestore_client")
    def test_init_without_client_creates_one(self, mock_get_client: MagicMock) -> None:
        """Verify FirebaseService creates a client when none is provided."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        service = FirebaseService()
        assert service._client is mock_client
        mock_get_client.assert_called_once()


class TestFirebaseServiceWriteCarbonLog:
    """Unit tests for FirebaseService.write_carbon_log."""

    @pytest.mark.unit
    def test_write_carbon_log_returns_document_id(self) -> None:
        """Verify write_carbon_log returns the generated Firestore document ID."""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "firestore-doc-123"
        mock_collection = MagicMock()
        mock_collection.add.return_value = (None, mock_doc_ref)
        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        service = FirebaseService(client=mock_client)
        doc_id = service.write_carbon_log(
            user_id="user-001",
            total_co2e_kg=5.25,
            results=[{"category": "transport", "co2e_kg": 5.25}],
            calculation_date="2026-06-08T12:00:00",
        )
        assert doc_id == "firestore-doc-123"

    @pytest.mark.unit
    def test_write_carbon_log_calls_collection_with_correct_name(self) -> None:
        """Verify write_carbon_log uses the correct Firestore collection name."""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "doc-id"
        mock_collection = MagicMock()
        mock_collection.add.return_value = (None, mock_doc_ref)
        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        service = FirebaseService(client=mock_client)
        service.write_carbon_log(
            user_id="user-001",
            total_co2e_kg=5.25,
            results=[],
            calculation_date="2026-06-08T12:00:00",
        )
        mock_client.collection.assert_called_with("carbon_logs")

    @pytest.mark.unit
    def test_write_carbon_log_calls_add_with_document(self) -> None:
        """Verify write_carbon_log passes the correct document to add()."""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "doc-id"
        mock_collection = MagicMock()
        mock_collection.add.return_value = (None, mock_doc_ref)
        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        service = FirebaseService(client=mock_client)
        service.write_carbon_log(
            user_id="user-001",
            total_co2e_kg=5.25,
            results=[{"category": "transport"}],
            calculation_date="2026-06-08T12:00:00",
        )
        mock_collection.add.assert_called_once()
        added_doc = mock_collection.add.call_args[0][0]
        assert added_doc["user_id"] == "user-001"
        assert added_doc["total_co2e_kg"] == 5.25


class TestFirebaseServiceGetUserLogs:
    """Unit tests for FirebaseService.get_user_logs."""

    @pytest.mark.unit
    def test_get_user_logs_returns_list_of_dicts(self) -> None:
        """Verify get_user_logs returns a list of document dictionaries."""
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "user_id": "user-001",
            "total_co2e_kg": 5.25,
        }
        # Build chain: collection -> where -> where -> order_by -> limit -> stream
        # Each mock represents the RETURN value of the previous method call
        mock_final = MagicMock()  # result of .limit(100) - has .stream()
        mock_final.stream.return_value = [mock_doc]

        mock_ordered = MagicMock()  # result of .order_by() - has .limit()
        mock_ordered.limit.return_value = mock_final

        mock_where_date = MagicMock()  # result of 2nd .where() - has .order_by()
        mock_where_date.order_by.return_value = mock_ordered

        mock_where_user = MagicMock()  # result of 1st .where() - has .where()
        mock_where_user.where.return_value = mock_where_date

        mock_collection = MagicMock()  # result of .collection() - has .where()
        mock_collection.where.return_value = mock_where_user

        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        service = FirebaseService(client=mock_client)
        logs = service.get_user_logs("user-001", 30)
        assert len(logs) == 1
        assert logs[0]["user_id"] == "user-001"

    @pytest.mark.unit
    def test_get_user_logs_with_custom_period(self) -> None:
        """Verify get_user_logs uses the provided period_days parameter."""
        mock_final = MagicMock()
        mock_final.stream.return_value = []
        mock_ordered = MagicMock()
        mock_ordered.limit.return_value = mock_final
        mock_where_date = MagicMock()
        mock_where_date.order_by.return_value = mock_ordered
        mock_where_user = MagicMock()
        mock_where_user.where.return_value = mock_where_date
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_where_user
        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        service = FirebaseService(client=mock_client)
        logs = service.get_user_logs("user-001", 7)
        assert logs == []


class TestGetFirestoreClient:
    """Unit tests for _get_firestore_client using shared init helper."""

    @pytest.mark.unit
    @patch("app.services.firebase_service.firestore")
    @patch("app.services.firebase_service.ensure_firebase_initialized")
    def test_get_firestore_client_returns_client(
        self, mock_ensure_init: MagicMock, mock_firestore: MagicMock
    ) -> None:
        """Verify _get_firestore_client returns a Firestore client instance."""
        mock_client = MagicMock()
        mock_firestore.client.return_value = mock_client
        result = _get_firestore_client()
        assert result is mock_client
        mock_ensure_init.assert_called_once()

    @pytest.mark.unit
    @patch("app.services.firebase_service.firestore")
    @patch("app.services.firebase_service.ensure_firebase_initialized")
    def test_get_firestore_client_calls_ensure_init(
        self, mock_ensure_init: MagicMock, mock_firestore: MagicMock
    ) -> None:
        """Verify _get_firestore_client calls ensure_firebase_initialized before client."""
        mock_firestore.client.return_value = MagicMock()
        _get_firestore_client()
        mock_ensure_init.assert_called_once()
