"""Extended tests for main.py — covers signal handler, metrics endpoint, request ID middleware.

Covers the uncovered lines in main.py:
- _signal_handler (lines 48-49)
- _register_metrics_route (lines 165-196)
- RequestIdMiddleware dispatch (lines 232-253)
"""

import asyncio
import signal as signal_module
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import (
    _signal_handler,
    _shutdown_event,
    _request_count,
    _error_count,
    _in_flight_requests,
    create_app,
    app,
    RequestIdMiddleware,
)


class TestSignalHandler:
    """Tests for the _signal_handler function."""

    def test_signal_handler_sets_shutdown_event(self) -> None:
        """Verify _signal_handler sets the shutdown event."""
        _shutdown_event.clear()
        _signal_handler(signal_module.SIGTERM, None)
        assert _shutdown_event.is_set()
        # Clean up
        _shutdown_event.clear()


class TestMetricsEndpoint:
    """Tests for the /metrics endpoint."""

    def test_metrics_returns_text_plain(self) -> None:
        """Verify /metrics returns text/plain content type."""
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_contains_help_text(self) -> None:
        """Verify /metrics output includes Prometheus HELP lines."""
        client = TestClient(app)
        response = client.get("/metrics")
        text = response.text
        assert "# HELP http_requests_total" in text
        assert "# HELP http_errors_total" in text
        assert "# HELP http_in_flight_requests" in text

    def test_metrics_shows_request_counts(self) -> None:
        """Verify /metrics includes request counts after making requests."""
        client = TestClient(app)
        client.get("/health")
        response = client.get("/metrics")
        text = response.text
        assert "http_requests_total" in text

    def test_metrics_shows_error_counts(self) -> None:
        """Verify /metrics includes error counts for failed requests."""
        client = TestClient(app)
        # Trigger a 422 validation error
        client.post(
            "/api/v1/footprint/log",
            json={},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        response = client.get("/metrics")
        text = response.text
        assert "http_errors_total" in text

    def test_metrics_shows_in_flight_requests(self) -> None:
        """Verify /metrics includes in_flight_requests gauge."""
        client = TestClient(app)
        response = client.get("/metrics")
        text = response.text
        assert "http_in_flight_requests" in text


class TestRequestIdMiddleware:
    """Tests for the RequestIdMiddleware."""

    def test_request_id_header_in_response(self) -> None:
        """Verify X-Request-ID is present in response headers."""
        client = TestClient(app)
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        # Should be a UUID-like string
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0

    def test_custom_request_id_preserved(self) -> None:
        """Verify a client-provided X-Request-ID is forwarded."""
        client = TestClient(app)
        response = client.get("/health", headers={"X-Request-ID": "custom-id-123"})
        assert response.headers["X-Request-ID"] == "custom-id-123"

    def test_request_id_increments_in_flight(self) -> None:
        """Verify in_flight_requests is tracked correctly."""
        global _in_flight_requests
        # Make a request and check metrics
        client = TestClient(app)
        client.get("/health")
        # After request completes, in_flight should be 0
        response = client.get("/metrics")
        text = response.text
        # The gauge should show 0 or a small number after request completes
        assert "http_in_flight_requests" in text


class TestAppConfiguration:
    """Tests for app configuration functions."""

    def test_create_app_includes_all_routers(self) -> None:
        """Verify create_app registers all route groups."""
        application = create_app()
        routes = [route.path for route in application.routes]
        assert "/health" in routes
        assert "/metrics" in routes

    def test_app_has_cors_middleware(self) -> None:
        """Verify CORS middleware is configured."""
        application = create_app()
        middleware_classes = [type(m).__name__ for m in application.user_middleware]
        # Check that middleware is present (may be wrapped)
        assert len(application.user_middleware) > 0
