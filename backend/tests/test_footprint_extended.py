"""Extended tests for footprint.py — covers _sanitize_description, _write_to_firestore retry, and get_firebase_service singleton."""

import re
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.footprint import (
    _sanitize_description,
    _write_to_firestore,
    get_firebase_service,
    _firebase_service_instance,
    _singleton_lock,
)


class TestSanitizeDescription:
    """Tests for _sanitize_description XSS prevention."""

    def test_strips_html_tags(self) -> None:
        """Verify HTML tags are removed from description."""
        result = _sanitize_description('<script>alert("xss")</script>Hello')
        assert "<script>" not in result
        assert "</script>" not in result
        assert "Hello" in result

    def test_strips_img_tag(self) -> None:
        """Verify img onerror tags are removed."""
        result = _sanitize_description("<img src=x onerror=alert(1)>text")
        assert "<img" not in result
        assert "text" in result

    def test_preserves_plain_text(self) -> None:
        """Verify plain text is preserved unchanged."""
        text = "Drove to work today, 15km"
        result = _sanitize_description(text)
        assert result == text

    def test_strips_nested_tags(self) -> None:
        """Verify nested HTML tags are stripped."""
        result = _sanitize_description("<div><b>bold</b></div>")
        assert "<div>" not in result
        assert "<b>" not in result
        assert "bold" in result


class TestWriteToFirestoreRetry:
    """Tests for _write_to_firestore retry logic on transient errors."""

    @pytest.mark.unit
    def test_retries_on_transient_error(self) -> None:
        """Verify _write_to_firestore retries on transient errors."""
        mock_service = MagicMock()
        # First call: transient error, second call: success
        mock_service.write_carbon_log.side_effect = [
            Exception("Connection timeout"),
            "doc-id-success",
        ]
        mock_payload = MagicMock()
        mock_payload.calculation_date = "2024-01-01T10:00"

        # Patch time.sleep to avoid real delays
        with patch("time.sleep"):
            result = _write_to_firestore(mock_service, "user1", mock_payload, 5.0, [])
        assert result == "doc-id-success"
        assert mock_service.write_carbon_log.call_count == 2

    @pytest.mark.unit
    def test_raises_on_non_transient_error(self) -> None:
        """Verify _write_to_firestore raises immediately on non-transient errors."""
        from fastapi import HTTPException

        mock_service = MagicMock()
        mock_service.write_carbon_log.side_effect = Exception("Permission denied")
        mock_payload = MagicMock()
        mock_payload.calculation_date = "2024-01-01T10:00"

        with pytest.raises(HTTPException) as exc_info:
            _write_to_firestore(mock_service, "user1", mock_payload, 5.0, [])
        assert exc_info.value.status_code == 500

    @pytest.mark.unit
    def test_raises_after_max_retries(self) -> None:
        """Verify _write_to_firestore raises after exhausting all retries."""
        from fastapi import HTTPException

        mock_service = MagicMock()
        mock_service.write_carbon_log.side_effect = Exception("timeout error")
        mock_payload = MagicMock()
        mock_payload.calculation_date = "2024-01-01T10:00"

        with patch("time.sleep"):
            with pytest.raises(HTTPException) as exc_info:
                _write_to_firestore(mock_service, "user1", mock_payload, 5.0, [])
        assert exc_info.value.status_code == 500
        # Should have tried 4 times (initial + 3 retries)
        assert mock_service.write_carbon_log.call_count == 4


class TestGetFirebaseServiceSingleton:
    """Tests for get_firebase_service singleton pattern."""

    def setup_method(self) -> None:
        """Reset the singleton before each test."""
        import app.routes.footprint as fp_module

        fp_module._firebase_service_instance = None

    def teardown_method(self) -> None:
        """Reset the singleton after each test."""
        import app.routes.footprint as fp_module

        fp_module._firebase_service_instance = None

    @patch("app.routes.footprint.FirebaseService")
    def test_creates_service_on_first_call(self, mock_cls: MagicMock) -> None:
        """Verify get_firebase_service creates a new instance on first call."""
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        result = get_firebase_service()
        assert result is mock_instance

    @patch("app.routes.footprint.FirebaseService")
    def test_returns_same_instance_on_subsequent_calls(
        self, mock_cls: MagicMock
    ) -> None:
        """Verify get_firebase_service returns the same singleton instance."""
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        first = get_firebase_service()
        second = get_firebase_service()
        assert first is second
        # FirebaseService should only be instantiated once
        assert mock_cls.call_count == 1
