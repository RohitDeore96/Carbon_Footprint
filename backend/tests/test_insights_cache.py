"""Comprehensive tests for the insights cache module.

Tests cover:
- _compute_cache_key helper function
- get_cached_insight (cache hit, cache miss, expired, error)
- set_cached_insight (success, error)
- cleanup_expired_cache_entries (success, error)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.insights_cache import (
    CACHE_COLLECTION,
    _compute_cache_key,
    cleanup_expired_cache_entries,
    get_cached_insight,
    set_cached_insight,
)


class TestComputeCacheKey:
    """Unit tests for the _compute_cache_key helper function."""

    @pytest.mark.unit
    def test_cache_key_is_deterministic(self) -> None:
        """Verify the same input always produces the same cache key."""
        user_data = {
            "total_co2e_kg": 100.0,
            "period_days": 30,
            "emission_breakdown": [{"category": "transport"}],
        }
        key1 = _compute_cache_key(user_data)
        key2 = _compute_cache_key(user_data)
        assert key1 == key2

    @pytest.mark.unit
    def test_cache_key_differs_for_different_data(self) -> None:
        """Verify different input data produces different cache keys."""
        data_a = {"total_co2e_kg": 100.0, "period_days": 30, "emission_breakdown": []}
        data_b = {"total_co2e_kg": 50.0, "period_days": 7, "emission_breakdown": []}
        assert _compute_cache_key(data_a) != _compute_cache_key(data_b)

    @pytest.mark.unit
    def test_cache_key_is_sha256_hex(self) -> None:
        """Verify the cache key is a 64-character hex string (SHA-256)."""
        key = _compute_cache_key({"total_co2e_kg": 1.0, "period_days": 1})
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestGetCachedInsight:
    """Unit tests for get_cached_insight."""

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cache_miss_returns_none(self, mock_get_db: MagicMock) -> None:
        """Verify None is returned when no cached document exists."""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )
        mock_get_db.return_value = mock_db

        result = get_cached_insight({"total_co2e_kg": 10.0, "period_days": 7})
        assert result is None

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cache_hit_returns_insight(self, mock_get_db: MagicMock) -> None:
        """Verify cached insight is returned when found and not expired."""
        cached_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "cached_at": cached_time,
            "insight": {"insight": "test insight"},
        }
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )
        mock_get_db.return_value = mock_db

        result = get_cached_insight({"total_co2e_kg": 10.0, "period_days": 7})
        assert result == {"insight": "test insight"}

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_expired_cache_returns_none(self, mock_get_db: MagicMock) -> None:
        """Verify None is returned when cache entry has expired."""
        expired_time = datetime.now(tz=timezone.utc) - timedelta(hours=48)
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "cached_at": expired_time,
            "insight": {"insight": "old insight"},
        }
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )
        mock_get_db.return_value = mock_db

        result = get_cached_insight(
            {"total_co2e_kg": 10.0, "period_days": 7}, ttl_hours=24
        )
        assert result is None

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cache_with_none_data_returns_none(self, mock_get_db: MagicMock) -> None:
        """Verify None is returned when document to_dict returns None."""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = None
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )
        mock_get_db.return_value = mock_db

        result = get_cached_insight({"total_co2e_kg": 10.0, "period_days": 7})
        assert result is None

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cache_without_cached_at_returns_none(self, mock_get_db: MagicMock) -> None:
        """Verify None is returned when cached_at field is missing."""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"insight": {"insight": "test"}}
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )
        mock_get_db.return_value = mock_db

        result = get_cached_insight({"total_co2e_kg": 10.0, "period_days": 7})
        assert result is None

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cache_read_exception_returns_none(self, mock_get_db: MagicMock) -> None:
        """Verify None is returned when Firestore read throws an exception."""
        mock_get_db.side_effect = Exception("Firestore unavailable")

        result = get_cached_insight({"total_co2e_kg": 10.0, "period_days": 7})
        assert result is None


class TestSetCachedInsight:
    """Unit tests for set_cached_insight."""

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_set_cached_insight_stores_document(self, mock_get_db: MagicMock) -> None:
        """Verify set_cached_insight writes to the correct collection and document."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        user_data = {"total_co2e_kg": 10.0, "period_days": 7}
        insight = {"insight": "reduce driving", "actionable_steps": ["bike more"]}

        set_cached_insight(user_data, insight)

        mock_db.collection.assert_called_with(CACHE_COLLECTION)
        mock_db.collection.return_value.document.assert_called_once()
        mock_db.collection.return_value.document.return_value.set.assert_called_once()

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_set_cached_insight_exception_does_not_raise(
        self, mock_get_db: MagicMock
    ) -> None:
        """Verify set_cached_insight swallows exceptions gracefully."""
        mock_get_db.side_effect = Exception("Write failed")

        user_data = {"total_co2e_kg": 10.0, "period_days": 7}
        insight = {"insight": "test"}

        # Should not raise
        set_cached_insight(user_data, insight)

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_set_cached_insight_document_contains_required_fields(
        self, mock_get_db: MagicMock
    ) -> None:
        """Verify the cached document contains cached_at, insight, and cache_key_prefix."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        user_data = {"total_co2e_kg": 10.0, "period_days": 7}
        insight = {"insight": "test insight"}

        set_cached_insight(user_data, insight)

        set_call_args = (
            mock_db.collection.return_value.document.return_value.set.call_args
        )
        doc_data = set_call_args[0][0]
        assert "cached_at" in doc_data
        assert "insight" in doc_data
        assert "cache_key_prefix" in doc_data
        assert doc_data["insight"] == insight


class TestCleanupExpiredCacheEntries:
    """Unit tests for cleanup_expired_cache_entries."""

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cleanup_deletes_expired_entries(self, mock_get_db: MagicMock) -> None:
        """Verify expired cache entries are deleted."""
        expired_time = datetime.now(tz=timezone.utc) - timedelta(hours=48)
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "cached_at": expired_time,
            "insight": {"insight": "old"},
        }
        mock_doc.reference = MagicMock()

        mock_db = MagicMock()
        mock_db.collection.return_value.limit.return_value.stream.return_value = [
            mock_doc
        ]
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch
        mock_get_db.return_value = mock_db

        deleted = cleanup_expired_cache_entries(ttl_hours=24)
        assert deleted == 1
        mock_batch.delete.assert_called_once_with(mock_doc.reference)
        mock_batch.commit.assert_called_once()

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cleanup_keeps_non_expired_entries(self, mock_get_db: MagicMock) -> None:
        """Verify non-expired cache entries are kept."""
        recent_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "cached_at": recent_time,
            "insight": {"insight": "recent"},
        }

        mock_db = MagicMock()
        mock_db.collection.return_value.limit.return_value.stream.return_value = [
            mock_doc
        ]
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch
        mock_get_db.return_value = mock_db

        deleted = cleanup_expired_cache_entries(ttl_hours=24)
        assert deleted == 0
        mock_batch.delete.assert_not_called()

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cleanup_handles_iso_string_cached_at(self, mock_get_db: MagicMock) -> None:
        """Verify cleanup handles cached_at stored as ISO string."""
        expired_time = datetime.now(tz=timezone.utc) - timedelta(hours=48)
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "cached_at": expired_time.isoformat(),
            "insight": {"insight": "old"},
        }
        mock_doc.reference = MagicMock()

        mock_db = MagicMock()
        mock_db.collection.return_value.limit.return_value.stream.return_value = [
            mock_doc
        ]
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch
        mock_get_db.return_value = mock_db

        deleted = cleanup_expired_cache_entries(ttl_hours=24)
        assert deleted == 1

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cleanup_exception_returns_zero(self, mock_get_db: MagicMock) -> None:
        """Verify cleanup returns 0 when an exception occurs."""
        mock_get_db.side_effect = Exception("Firestore unavailable")
        deleted = cleanup_expired_cache_entries()
        assert deleted == 0
