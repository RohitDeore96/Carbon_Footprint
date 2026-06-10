"""Tests for the error_tracker module — structured error reporting service.

Covers report_error with all three provider paths (logging, sentry, cloud)
and the internal _report_to_sentry / _report_to_cloud_error_reporting helpers.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from app.services.error_tracker import (
    report_error,
    _report_to_sentry,
    _report_to_cloud_error_reporting,
)


class TestReportErrorLoggingProvider:
    """Test report_error with the default 'logging' provider."""

    @pytest.mark.unit
    @patch("app.services.error_tracker._ERROR_TRACKING_PROVIDER", "logging")
    def test_report_error_calls_log_error(self) -> None:
        """Verify report_error delegates to log_error for the default logging provider."""
        with patch("app.utils.error_logging.log_error") as mock_log:
            exc = ValueError("test logging provider")
            report_error(
                exc, context={"key": "val"}, request_path="/test", user_id="u1"
            )
            mock_log.assert_called_once()

    @pytest.mark.unit
    @patch("app.services.error_tracker._ERROR_TRACKING_PROVIDER", "logging")
    def test_report_error_with_no_context(self) -> None:
        """Verify report_error works with None context."""
        with patch("app.utils.error_logging.log_error"):
            exc = RuntimeError("no context")
            report_error(exc)

    @pytest.mark.unit
    @patch("app.services.error_tracker._ERROR_TRACKING_PROVIDER", "logging")
    def test_report_error_does_not_call_sentry_or_cloud(self) -> None:
        """Verify that the logging provider does not invoke sentry or cloud helpers."""
        with patch("app.utils.error_logging.log_error"):
            with patch("app.services.error_tracker._report_to_sentry") as mock_sentry:
                with patch(
                    "app.services.error_tracker._report_to_cloud_error_reporting"
                ) as mock_cloud:
                    report_error(ValueError("logging only"))
                    mock_sentry.assert_not_called()
                    mock_cloud.assert_not_called()


class TestReportErrorSentryProvider:
    """Test report_error with the 'sentry' provider."""

    @pytest.mark.unit
    @patch("app.services.error_tracker._ERROR_TRACKING_PROVIDER", "sentry")
    def test_sentry_provider_calls_report_to_sentry(self) -> None:
        """Verify the sentry provider calls _report_to_sentry."""
        with patch("app.utils.error_logging.log_error"):
            with patch("app.services.error_tracker._report_to_sentry") as mock_sentry:
                exc = ValueError("sentry test")
                report_error(exc, context={"k": "v"}, request_path="/api", user_id="u2")
                mock_sentry.assert_called_once_with(exc, {"k": "v"}, "/api", "u2")


class TestReportErrorCloudProvider:
    """Test report_error with the 'cloud' provider."""

    @pytest.mark.unit
    @patch("app.services.error_tracker._ERROR_TRACKING_PROVIDER", "cloud")
    def test_cloud_provider_calls_report_to_cloud(self) -> None:
        """Verify the cloud provider calls _report_to_cloud_error_reporting."""
        with patch("app.utils.error_logging.log_error"):
            with patch(
                "app.services.error_tracker._report_to_cloud_error_reporting"
            ) as mock_cloud:
                exc = RuntimeError("cloud test")
                report_error(exc, context={"x": 1}, request_path="/r", user_id="u3")
                mock_cloud.assert_called_once_with(exc, {"x": 1}, "/r", "u3")


class TestReportToSentry:
    """Test the _report_to_sentry helper function."""

    @pytest.mark.unit
    def test_sentry_handles_import_error(self) -> None:
        """Verify _report_to_sentry gracefully handles missing sentry-sdk."""
        # The function has `import sentry_sdk` inside a try/except ImportError
        # We need to make the import fail
        import sys

        original = sys.modules.get("sentry_sdk")
        sys.modules["sentry_sdk"] = None
        try:
            # Should not raise
            _report_to_sentry(ValueError("no sdk"), None, "/test", "u1")
        finally:
            if original is not None:
                sys.modules["sentry_sdk"] = original
            else:
                sys.modules.pop("sentry_sdk", None)

    @pytest.mark.unit
    def test_sentry_handles_general_exception(self) -> None:
        """Verify _report_to_sentry handles unexpected exceptions from sentry_sdk."""
        # Mock sentry_sdk at the point where it's imported inside the function
        mock_sdk = MagicMock()
        mock_sdk.set_context.side_effect = Exception("sentry broke")
        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            # Should not raise, just log warning
            _report_to_sentry(RuntimeError("inner"), None, "/p", "u")


class TestReportToCloudErrorReporting:
    """Test the _report_to_cloud_error_reporting helper function."""

    @pytest.mark.unit
    def test_cloud_report_logs_error_payload(self) -> None:
        """Verify _report_to_cloud_error_reporting logs a structured JSON payload."""
        captured: list[str] = []
        test_logger = logging.getLogger("test_cloud_report")

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(self.format(record))

        handler = CapturingHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.ERROR)

        with patch("app.services.error_tracker.logger", test_logger):
            exc = ValueError("cloud report test")
            _report_to_cloud_error_reporting(
                exc,
                context={"file": "main.py", "function": "handler"},
                request_path="/api/v1/test",
                user_id="user1",
            )

        # Find the Cloud Error Report line and verify it's valid JSON
        for line in captured:
            if "Cloud Error Report:" in line:
                json_str = line.split("Cloud Error Report: ", 1)[1]
                payload = json.loads(json_str)
                assert payload["serviceContext"]["service"] == "carbon-footprint-api"
                assert "ValueError" in payload["message"]
                assert payload["context"]["httpRequest"]["url"] == "/api/v1/test"
                assert payload["context"]["user"] == "user1"
                assert payload["context"]["reportLocation"]["filePath"] == "main.py"
                assert payload["context"]["reportLocation"]["functionName"] == "handler"
                break
        else:
            pytest.fail("Cloud Error Report not found in captured logs")

    @pytest.mark.unit
    def test_cloud_report_with_none_context(self) -> None:
        """Verify cloud reporting works when context is None."""
        captured: list[str] = []
        test_logger = logging.getLogger("test_cloud_none_ctx")

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(self.format(record))

        handler = CapturingHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.ERROR)

        with patch("app.services.error_tracker.logger", test_logger):
            _report_to_cloud_error_reporting(
                RuntimeError("err"), context=None, request_path="/", user_id=""
            )

        for line in captured:
            if "Cloud Error Report:" in line:
                json_str = line.split("Cloud Error Report: ", 1)[1]
                payload = json.loads(json_str)
                assert payload["context"]["reportLocation"]["filePath"] == ""
                assert payload["context"]["reportLocation"]["functionName"] == ""
                break
        else:
            pytest.fail("Cloud Error Report not found")

    @pytest.mark.unit
    def test_cloud_report_contains_event_time(self) -> None:
        """Verify cloud report payload includes an ISO-formatted eventTime."""
        captured: list[str] = []
        test_logger = logging.getLogger("test_cloud_time")

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(self.format(record))

        handler = CapturingHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.ERROR)

        with patch("app.services.error_tracker.logger", test_logger):
            _report_to_cloud_error_reporting(
                Exception("time check"), context=None, request_path="", user_id=""
            )

        for line in captured:
            if "Cloud Error Report:" in line:
                json_str = line.split("Cloud Error Report: ", 1)[1]
                payload = json.loads(json_str)
                assert "eventTime" in payload
                # Verify it's parseable as ISO format
                from datetime import datetime

                datetime.fromisoformat(payload["eventTime"])
                break
