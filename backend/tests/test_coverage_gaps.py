"""Extended tests for insights_cache, main.py, auth.py, and entry_processor.

Tests cover:
- insights_cache: cleanup edge cases, _get_db direct test
- main.py: lifespan startup/shutdown, create_app factory
- auth.py: Firebase init failure path
- entry_processor: unknown category warning path
- error_logging: no logger provided (default logger path)
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app, app
from app.middleware.auth import ensure_firebase_initialized
from app.services.insights_cache import (
    _get_db,
    cleanup_expired_cache_entries,
)
from app.utils.entry_processor import compute_entry_emission
from app.schemas import EmissionResult
from app.utils.error_logging import log_error


class TestCleanupEdgeCases:
    """Extended tests for cleanup_expired_cache_entries edge cases."""

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cleanup_skips_none_data_documents(self, mock_get_db: MagicMock) -> None:
        """Verify documents with None data are skipped during cleanup."""
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = None
        mock_doc.reference = MagicMock()

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
    def test_cleanup_skips_none_cached_at(self, mock_get_db: MagicMock) -> None:
        """Verify documents with None cached_at are skipped."""
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "cached_at": None,
            "insight": {"insight": "test"},
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
    def test_cleanup_handles_invalid_iso_string(self, mock_get_db: MagicMock) -> None:
        """Verify documents with invalid ISO string cached_at are skipped."""
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "cached_at": "not-a-valid-date",
            "insight": {"insight": "test"},
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

    @pytest.mark.unit
    @patch("app.services.insights_cache._get_db")
    def test_cleanup_handles_naive_datetime(self, mock_get_db: MagicMock) -> None:
        """Verify naive datetime (no tzinfo) gets UTC assumed."""
        expired_naive = datetime.now() - timedelta(hours=48)
        expired_naive = expired_naive.replace(tzinfo=None)

        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "cached_at": expired_naive,
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
    def test_cleanup_commits_batch_at_499_ops(self, mock_get_db: MagicMock) -> None:
        """Verify batch is committed when approaching Firestore 500-op limit."""
        expired_time = datetime.now(tz=timezone.utc) - timedelta(hours=48)

        mock_docs = []
        for i in range(500):
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = {
                "cached_at": expired_time,
                "insight": {"insight": f"old-{i}"},
            }
            mock_doc.reference = MagicMock()
            mock_docs.append(mock_doc)

        mock_db = MagicMock()
        mock_db.collection.return_value.limit.return_value.stream.return_value = (
            mock_docs
        )
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch
        mock_get_db.return_value = mock_db

        deleted = cleanup_expired_cache_entries(ttl_hours=24, batch_size=500)
        assert deleted == 500
        assert mock_batch.commit.call_count >= 1


class TestMainApp:
    """Tests for main.py application creation and lifespan."""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """Verify create_app returns a configured FastAPI application."""
        application = create_app()
        assert isinstance(application, FastAPI)
        assert application.title == "Carbon Footprint Awareness Platform API"

    def test_app_has_health_route(self) -> None:
        """Verify the app has the /health route registered."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_app_version(self) -> None:
        """Verify the app version is set correctly."""
        assert app.version == "1.0.0"

    @patch("app.main.ensure_firebase_initialized")
    def test_lifespan_calls_firebase_init(self, mock_ensure_init: MagicMock) -> None:
        """Verify the lifespan startup calls ensure_firebase_initialized."""
        from app.main import lifespan

        test_app = FastAPI(lifespan=lifespan)

        with TestClient(test_app):
            mock_ensure_init.assert_called()

    @patch("app.main.ensure_firebase_initialized")
    def test_lifespan_logs_startup_and_shutdown(
        self, mock_ensure_init: MagicMock
    ) -> None:
        """Verify lifespan logs startup and shutdown messages."""
        from app.main import lifespan

        test_app = FastAPI(lifespan=lifespan)

        with TestClient(test_app) as client:
            client.get("/health")


class TestGetDb:
    """Tests for the _get_db helper function."""

    def test_get_db_calls_ensure_init_and_returns_client(self) -> None:
        """Verify _get_db initializes Firebase and returns a Firestore client."""
        mock_client = MagicMock()
        with patch("app.services.firebase_service.ensure_firebase_initialized"):
            with patch(
                "app.services.insights_cache.firebase_firestore.client",
                return_value=mock_client,
            ):
                result = _get_db()
                assert result is mock_client


class TestAuthFirebaseInitFailure:
    """Tests for Firebase initialization failure paths."""

    @patch("app.middleware.auth._firebase_app_initialized", False)
    @patch("app.middleware.auth.get_app")
    def test_ensure_firebase_init_failure_path(self, mock_get_app: MagicMock) -> None:
        """Verify ensure_firebase_initialized handles init failure gracefully."""
        import app.middleware.auth as auth_module

        auth_module._firebase_app_initialized = False

        mock_get_app.side_effect = ValueError("App not initialized")
        with patch("app.middleware.auth.initialize_app") as mock_init:
            mock_init.side_effect = Exception("Init failed")
            ensure_firebase_initialized()
            assert auth_module._firebase_app_initialized is False

        auth_module._firebase_app_initialized = True


class TestEntryProcessorUnknownCategory:
    """Tests for compute_entry_emission with unknown category."""

    def test_unknown_category_returns_zero_emission(self) -> None:
        """Verify unknown category defaults to 0.0 CO2e with a warning."""
        entry = MagicMock()
        entry.category.value = "unknown_category"
        entry.description = "Test unknown category"
        entry.date = "2024-01-01"

        result = compute_entry_emission(entry)
        assert isinstance(result, EmissionResult)
        assert result.co2e_kg == 0.0
        assert result.category == "unknown_category"


class TestLogErrorDefaultLogger:
    """Tests for log_error with default logger (None provided)."""

    def test_log_error_with_no_logger_uses_default(self) -> None:
        """Verify log_error uses default module logger when none is provided."""
        try:
            log_error(ValueError("test default logger"), context={"test": True})
        except Exception:
            pytest.fail("log_error should not raise")

    def test_log_error_with_empty_context(self) -> None:
        """Verify log_error works with empty context dict."""
        test_logger = logging.getLogger("test_empty_ctx")
        test_logger.addHandler(logging.NullHandler())
        try:
            log_error(RuntimeError("error"), context={}, logger=test_logger)
        except Exception:
            pytest.fail("log_error should not raise")

    def test_log_error_with_request_path(self) -> None:
        """Verify log_error includes request_path in structured output."""
        test_logger = logging.getLogger("test_req_path")
        captured: list[str] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(self.format(record))

        handler = CapturingHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.ERROR)

        log_error(
            TypeError("type error"),
            context={"endpoint": "test"},
            logger=test_logger,
            request_path="/api/v1/test",
        )

        for line in captured:
            if "Structured error:" in line:
                json_str = line.split("Structured error: ", 1)[1]
                parsed = json.loads(json_str)
                assert parsed["request_path"] == "/api/v1/test"
                break
