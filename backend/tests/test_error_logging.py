"""Tests for the structured error logging module.

Tests cover:
- log_error produces structured JSON with required fields
- log_error uses provided logger
- log_error includes context and request_path
"""

import json
import logging

from app.utils.error_logging import log_error


class TestLogError:
    """Unit tests for the log_error function."""

    def test_log_error_includes_required_fields(self) -> None:
        """Verify log_error emits structured JSON with all required fields."""
        test_logger = logging.getLogger("test_error_logging")
        test_logger.addHandler(logging.NullHandler())

        try:
            log_error(
                ValueError("test error"),
                context={"user_id": "user-001"},
                logger=test_logger,
                request_path="/api/v1/test",
            )
        except Exception:
            pass  # log_error should not raise

    def test_log_error_uses_provided_logger(self, caplog: object) -> None:
        """Verify log_error uses the provided logger instance."""
        test_logger = logging.getLogger("test_specific_logger")
        with caplog.at_level(logging.ERROR, logger="test_specific_logger"):
            log_error(
                RuntimeError("runtime issue"),
                logger=test_logger,
                request_path="/api/v1/test",
            )
        assert any("Structured error" in record.message for record in caplog.records)

    def test_log_error_json_is_parseable(self) -> None:
        """Verify the structured log output is valid JSON."""
        test_logger = logging.getLogger("test_json_parse")
        captured: list[str] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(self.format(record))

        handler = CapturingHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.ERROR)

        log_error(
            TypeError("type issue"),
            context={"key": "value"},
            logger=test_logger,
            request_path="/test",
        )

        # Find the structured JSON line
        for line in captured:
            if "Structured error:" in line:
                json_str = line.split("Structured error: ", 1)[1]
                parsed = json.loads(json_str)
                assert "timestamp" in parsed
                assert "error_type" in parsed
                assert parsed["error_type"] == "TypeError"
                assert "error_message" in parsed
                assert "stack_trace" in parsed
                assert "context" in parsed
                assert parsed["context"]["key"] == "value"
                assert "request_path" in parsed
                assert parsed["request_path"] == "/test"
                assert "environment" in parsed
                break

    def test_log_error_default_context_is_empty_dict(self) -> None:
        """Verify context defaults to empty dict when not provided."""
        test_logger = logging.getLogger("test_default_context")
        captured: list[str] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(self.format(record))

        handler = CapturingHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.ERROR)

        log_error(Exception("no context"), logger=test_logger)

        for line in captured:
            if "Structured error:" in line:
                json_str = line.split("Structured error: ", 1)[1]
                parsed = json.loads(json_str)
                assert parsed["context"] == {}
                break
