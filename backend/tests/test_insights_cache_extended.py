"""Extended tests for insights_cache.py — covers set_cached_insight with count check."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.insights_cache import set_cached_insight


class TestSetCachedInsightCountCheck:
    """Tests for set_cached_insight with cache size check."""

    @patch("app.services.insights_cache._get_db")
    def test_set_cached_insight_skips_write_when_cache_full(self, mock_get_db: MagicMock) -> None:
        """Verify set_cached_insight skips write when cache exceeds MAX_CACHE_ENTRIES."""
        mock_db = MagicMock()
        mock_collection = MagicMock()

        # Mock count() query returning a count at the limit
        mock_count_result = MagicMock()
        mock_count_result.__iter__ = lambda self: iter([MagicMock()])
        # Make r[0].value return 10001
        mock_value = MagicMock()
        mock_value.value = 10001
        mock_row = [mock_value]
        mock_count_result.__iter__ = lambda self: iter([mock_row])

        mock_collection.count.return_value.get.return_value = mock_count_result
        mock_db.collection.return_value = mock_collection
        mock_get_db.return_value = mock_db

        # Should skip the write and not call .document().set()
        set_cached_insight(
            {"total_co2e_kg": 10, "period_days": 30, "emission_breakdown": []},
            {"insight": "test"},
        )
        # document().set() should NOT have been called
        mock_db.collection.return_value.document.assert_not_called()

    @patch("app.services.insights_cache._get_db")
    def test_set_cached_insight_writes_when_cache_has_room(self, mock_get_db: MagicMock) -> None:
        """Verify set_cached_insight writes when cache is below MAX_CACHE_ENTRIES."""
        mock_db = MagicMock()
        mock_collection = MagicMock()

        # Mock count() returning a small number
        mock_count_result = MagicMock()
        mock_value = MagicMock()
        mock_value.value = 50
        mock_count_result.__iter__ = lambda self: iter([[mock_value]])
        mock_collection.count.return_value.get.return_value = mock_count_result
        mock_db.collection.return_value = mock_collection
        mock_get_db.return_value = mock_db

        set_cached_insight(
            {"total_co2e_kg": 10, "period_days": 30, "emission_breakdown": []},
            {"insight": "test data"},
        )
        # document().set() should have been called
        mock_db.collection.return_value.document.assert_called_once()

    @patch("app.services.insights_cache._get_db")
    def test_set_cached_insight_handles_count_not_available(self, mock_get_db: MagicMock) -> None:
        """Verify set_cached_insight proceeds when count() is not available."""
        mock_db = MagicMock()
        mock_collection = MagicMock()

        # count() raises AttributeError (older client)
        mock_collection.count.side_effect = AttributeError("no count method")
        mock_db.collection.return_value = mock_collection
        mock_get_db.return_value = mock_db

        set_cached_insight(
            {"total_co2e_kg": 10, "period_days": 30, "emission_breakdown": []},
            {"insight": "fallback write"},
        )
        # Should still write to the cache
        mock_db.collection.return_value.document.assert_called_once()
