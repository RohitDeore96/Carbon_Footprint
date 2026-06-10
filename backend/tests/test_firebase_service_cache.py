"""Tests for firebase_service.py — cache helpers and get_aggregated_summary.

Covers:
- _get_cached_logs / _set_cached_logs / invalidate_logs_cache
- FirebaseService.get_aggregated_summary (both server-side and fallback)
- _get_firestore_client
- Cache eviction when at capacity
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.firebase_service import (
    _get_cached_logs,
    _set_cached_logs,
    invalidate_logs_cache,
    _get_firestore_client,
    _logs_cache,
    _logs_cache_lock,
    FirebaseService,
)


class TestLogsCacheHelpers:
    """Tests for the in-memory TTL cache helper functions."""

    def setup_method(self) -> None:
        """Clear the logs cache before each test."""
        with _logs_cache_lock:
            _logs_cache.clear()

    def test_get_cached_logs_returns_none_for_missing_key(self) -> None:
        """Verify cache miss returns None."""
        result = _get_cached_logs("user1", 30)
        assert result is None

    def test_set_and_get_cached_logs(self) -> None:
        """Verify setting and getting cached logs works."""
        data = [{"total_co2e_kg": 5.0, "user_id": "u1"}]
        _set_cached_logs("u1", 30, data)
        result = _get_cached_logs("u1", 30)
        assert result == data

    def test_cached_logs_expire_after_ttl(self) -> None:
        """Verify expired cache entries return None."""
        with _logs_cache_lock:
            # Manually insert an expired entry
            _logs_cache[("u1", 30)] = (time.monotonic() - 600, [{"old": True}])

        result = _get_cached_logs("u1", 30)
        assert result is None

    def test_different_period_days_are_separate_entries(self) -> None:
        """Verify cache keys differentiate by period_days."""
        data_30 = [{"period": 30}]
        data_7 = [{"period": 7}]
        _set_cached_logs("u1", 30, data_30)
        _set_cached_logs("u1", 7, data_7)
        assert _get_cached_logs("u1", 30) == data_30
        assert _get_cached_logs("u1", 7) == data_7

    def test_different_users_are_separate_entries(self) -> None:
        """Verify cache keys differentiate by user_id."""
        _set_cached_logs("u1", 30, [{"user": "u1"}])
        _set_cached_logs("u2", 30, [{"user": "u2"}])
        assert _get_cached_logs("u1", 30) == [{"user": "u1"}]
        assert _get_cached_logs("u2", 30) == [{"user": "u2"}]


class TestInvalidateLogsCache:
    """Tests for invalidate_logs_cache function."""

    def setup_method(self) -> None:
        """Clear the logs cache before each test."""
        with _logs_cache_lock:
            _logs_cache.clear()

    def test_invalidate_specific_period(self) -> None:
        """Verify invalidation with period_days removes only that entry."""
        _set_cached_logs("u1", 30, [{"data": 30}])
        _set_cached_logs("u1", 7, [{"data": 7}])
        invalidate_logs_cache("u1", 30)
        assert _get_cached_logs("u1", 30) is None
        assert _get_cached_logs("u1", 7) == [{"data": 7}]

    def test_invalidate_all_periods_for_user(self) -> None:
        """Verify invalidation without period_days removes all entries for user."""
        _set_cached_logs("u1", 30, [{"data": 30}])
        _set_cached_logs("u1", 7, [{"data": 7}])
        _set_cached_logs("u2", 30, [{"data": "other_user"}])
        invalidate_logs_cache("u1")
        assert _get_cached_logs("u1", 30) is None
        assert _get_cached_logs("u1", 7) is None
        assert _get_cached_logs("u2", 30) == [{"data": "other_user"}]


class TestCacheEviction:
    """Tests for cache eviction when at capacity."""

    def setup_method(self) -> None:
        """Clear the logs cache before each test."""
        with _logs_cache_lock:
            _logs_cache.clear()

    @patch("app.services.firebase_service._LOGS_CACHE_MAX_ENTRIES", 5)
    def test_eviction_when_over_limit(self) -> None:
        """Verify oldest entries are evicted when cache exceeds max entries."""
        # Fill cache beyond max
        for i in range(7):
            _set_cached_logs(f"user_{i}", 30, [{"idx": i}])
        # After eviction, cache should still have entries but not exceed max by much
        # The most recent entries should be present
        assert _get_cached_logs("user_6", 30) is not None


class TestGetFirestoreClient:
    """Tests for the _get_firestore_client helper."""

    @pytest.mark.unit
    @patch("app.services.firebase_service.ensure_firebase_initialized")
    @patch("app.services.firebase_service.firestore")
    def test_returns_firestore_client(
        self, mock_firestore: MagicMock, mock_ensure: MagicMock
    ) -> None:
        """Verify _get_firestore_client returns a Firestore client."""
        mock_client = MagicMock()
        mock_firestore.client.return_value = mock_client
        result = _get_firestore_client()
        assert result is mock_client
        mock_ensure.assert_called_once()


class TestGetAggregatedSummary:
    """Tests for FirebaseService.get_aggregated_summary."""

    @pytest.mark.unit
    @patch("app.services.firebase_service.firestore")
    def test_server_aggregation_success(self, mock_firestore: MagicMock) -> None:
        """Verify server-side aggregation path returns correct summary."""
        mock_client = MagicMock()
        mock_row = {"total_co2e_kg": 12.5, "entry_count": 3}

        mock_aggregation = MagicMock()
        mock_aggregation.get.return_value = [mock_row]
        mock_query = MagicMock()
        mock_query.aggregate.return_value = mock_aggregation
        mock_client.collection.return_value.where.return_value.where.return_value = (
            mock_query
        )

        # Mock AggregationField to avoid real Firestore calls
        mock_firestore.AggregationField.sum.return_value.alias.return_value = (
            MagicMock()
        )
        mock_firestore.AggregationField.count.return_value.alias.return_value = (
            MagicMock()
        )

        service = FirebaseService(client=mock_client)
        result = service.get_aggregated_summary("user1", 30)
        assert result["total_co2e_kg"] == 12.5
        assert result["entry_count"] == 3
        assert result["server_aggregated"] is True

    @pytest.mark.unit
    def test_fallback_to_client_side_aggregation(self) -> None:
        """Verify fallback to client-side aggregation when server aggregation fails."""
        mock_client = MagicMock()
        # Make server aggregation raise an error
        mock_query = MagicMock()
        mock_query.aggregate.side_effect = AttributeError("aggregate not available")
        mock_client.collection.return_value.where.return_value.where.return_value = (
            mock_query
        )

        # Mock get_user_logs to return data for fallback
        logs = [
            {"total_co2e_kg": 5.0},
            {"total_co2e_kg": 3.5},
        ]

        service = FirebaseService(client=mock_client)
        with patch.object(service, "get_user_logs", return_value=logs):
            result = service.get_aggregated_summary("user1", 30)

        assert result["total_co2e_kg"] == 8.5
        assert result["entry_count"] == 2
        assert result["server_aggregated"] is False

    @pytest.mark.unit
    def test_fallback_with_empty_logs(self) -> None:
        """Verify fallback aggregation with no logs returns zeros."""
        mock_client = MagicMock()
        mock_query = MagicMock()
        mock_query.aggregate.side_effect = TypeError("unsupported")
        mock_client.collection.return_value.where.return_value.where.return_value = (
            mock_query
        )

        service = FirebaseService(client=mock_client)
        with patch.object(service, "get_user_logs", return_value=[]):
            result = service.get_aggregated_summary("user1", 30)

        assert result["total_co2e_kg"] == 0.0
        assert result["entry_count"] == 0
        assert result["server_aggregated"] is False

    @pytest.mark.unit
    def test_get_user_logs_cache_hit(self) -> None:
        """Verify get_user_logs returns cached data when available."""
        mock_client = MagicMock()
        cached_data = [{"total_co2e_kg": 5.0, "user_id": "u1"}]

        service = FirebaseService(client=mock_client)
        # Pre-populate cache
        _set_cached_logs("u1", 30, cached_data)

        result = service.get_user_logs("u1", 30)
        assert result == cached_data
        # Firestore should NOT be called when cache hits
        mock_client.collection.assert_not_called()

        # Clean up
        invalidate_logs_cache("u1", 30)

    @pytest.mark.unit
    def test_get_user_logs_cache_miss_queries_firestore(self) -> None:
        """Verify get_user_logs queries Firestore on cache miss."""
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {"total_co2e_kg": 3.0, "user_id": "u1"}

        mock_client = MagicMock()
        mock_client.collection.return_value.where.return_value.where.return_value.order_by.return_value.limit.return_value.stream.return_value = [
            mock_doc
        ]

        # Clear any cached data
        invalidate_logs_cache("u1", 30)

        service = FirebaseService(client=mock_client)
        result = service.get_user_logs("u1", 30)
        assert len(result) == 1
        assert result[0]["total_co2e_kg"] == 3.0
        mock_client.collection.assert_called_once()

        # Clean up
        invalidate_logs_cache("u1", 30)

    @pytest.mark.unit
    def test_get_user_logs_skips_none_dicts(self) -> None:
        """Verify get_user_logs filters out None to_dict() results."""
        mock_doc_none = MagicMock()
        mock_doc_none.to_dict.return_value = None
        mock_doc_valid = MagicMock()
        mock_doc_valid.to_dict.return_value = {"total_co2e_kg": 2.0}

        mock_client = MagicMock()
        mock_client.collection.return_value.where.return_value.where.return_value.order_by.return_value.limit.return_value.stream.return_value = [
            mock_doc_none,
            mock_doc_valid,
        ]

        invalidate_logs_cache("u2", 30)

        service = FirebaseService(client=mock_client)
        result = service.get_user_logs("u2", 30)
        assert len(result) == 1
        assert result[0]["total_co2e_kg"] == 2.0

        # Clean up
        invalidate_logs_cache("u2", 30)
