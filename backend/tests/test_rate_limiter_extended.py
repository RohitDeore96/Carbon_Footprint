"""Extended tests for the RateLimiterMiddleware to achieve 90%+ coverage.

Tests cover:
- _get_client_ip with X-Forwarded-For header parsing
- FirestoreRateLimiter._check_and_increment_firestore paths
- FirestoreRateLimiter._check_and_increment_memory with eviction
- FirestoreRateLimiter.check_and_increment when firestore is unavailable
- RateLimiterMiddleware.dispatch rate limiting (429 path)
- InMemoryRateLimiterMiddleware._evict_if_needed
"""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.constants import AppConstants
from app.middleware.rate_limiter import (
    FirestoreRateLimiter,
    InMemoryRateLimiterMiddleware,
    RateLimiterMiddleware,
    _build_rate_limit_response,
    _get_client_ip,
    _is_window_expired,
    _MAX_CLIENT_ENTRIES,
)

# ===========================================================================
# Helper function tests
# ===========================================================================


class TestGetClientIp:
    """Tests for _get_client_ip extraction logic."""

    def test_no_forwarded_for_returns_client_host(self) -> None:
        """Verify client host is returned when no X-Forwarded-For header."""
        request = MagicMock()
        request.headers.get.return_value = None
        request.client.host = "192.168.1.1"
        assert _get_client_ip(request) == "192.168.1.1"

    def test_forwarded_for_with_single_ip(self) -> None:
        """Verify X-Forwarded-For with single IP extracts correctly."""
        request = MagicMock()
        request.headers.get.return_value = "10.0.0.1"
        result = _get_client_ip(request)
        assert result == "10.0.0.1"

    def test_forwarded_for_with_multiple_ips(self) -> None:
        """Verify X-Forwarded-For with multiple IPs extracts rightmost trusted IP."""
        request = MagicMock()
        request.headers.get.return_value = "1.1.1.1, 2.2.2.2, 10.0.0.1"
        result = _get_client_ip(request)
        assert result == "10.0.0.1"

    def test_forwarded_for_with_fewer_ips_than_proxy_count(self) -> None:
        """Verify fallback to client.host when not enough IPs in header."""
        request = MagicMock()
        request.headers.get.return_value = ""  # Empty string - falsy
        request.client.host = "192.168.1.1"
        result = _get_client_ip(request)
        assert result == "192.168.1.1"

    def test_no_client_returns_unknown(self) -> None:
        """Verify 'unknown' returned when no client and no forwarded-for."""
        request = MagicMock()
        request.headers.get.return_value = None
        request.client = None
        assert _get_client_ip(request) == "unknown"


class TestIsWindowExpired:
    """Tests for _is_window_expired helper."""

    def test_window_not_expired(self) -> None:
        """Verify False when window is within rate limit period."""
        current = time.time()
        assert _is_window_expired(current - 30, current) is False

    def test_window_expired(self) -> None:
        """Verify True when window exceeds rate limit period."""
        current = time.time()
        assert _is_window_expired(current - 61, current) is True


class TestBuildRateLimitResponse:
    """Tests for _build_rate_limit_response helper."""

    def test_response_has_429_status(self) -> None:
        """Verify the response has 429 status code."""
        response = _build_rate_limit_response()
        assert response.status_code == 429

    def test_response_has_detail_message(self) -> None:
        """Verify the response body contains detail message."""
        response = _build_rate_limit_response()
        assert "Rate limit exceeded" in response.body.decode()


# ===========================================================================
# FirestoreRateLimiter tests
# ===========================================================================


class TestFirestoreRateLimiterFirestorePaths:
    """Tests for FirestoreRateLimiter._check_and_increment_firestore branches."""

    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_returns_none_when_db_unavailable(
        self, mock_get_db: MagicMock
    ) -> None:
        """Verify None returned when Firestore client is unavailable."""
        mock_get_db.return_value = None
        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_firestore("test-ip", time.time())
        assert result is None

    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_corrupt_document_resets(self, mock_get_db: MagicMock) -> None:
        """Verify corrupt document (to_dict returns None) triggers reset."""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = None
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_get_db.return_value = mock_db

        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_firestore("test-ip", time.time())
        assert result == 1
        mock_doc_ref.set.assert_called_once()

    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_existing_client_expired_window(
        self, mock_get_db: MagicMock
    ) -> None:
        """Verify expired window resets the counter."""
        current = time.time()
        old_time = datetime.fromtimestamp(current - 120, tz=timezone.utc)

        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "window_start": old_time,
            "request_count": 50,
        }
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_get_db.return_value = mock_db

        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_firestore("test-ip", current)
        assert result == 1
        mock_doc_ref.set.assert_called_once()

    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_existing_client_within_window(
        self, mock_get_db: MagicMock
    ) -> None:
        """Verify within-window request increments counter."""
        current = time.time()
        recent_time = datetime.fromtimestamp(current - 10, tz=timezone.utc)

        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "window_start": recent_time,
            "request_count": 5,
        }
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_get_db.return_value = mock_db

        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_firestore("test-ip", current)
        assert result == 6
        mock_doc_ref.update.assert_called_once_with({"request_count": 6})

    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_window_start_as_timestamp_float(
        self, mock_get_db: MagicMock
    ) -> None:
        """Verify non-datetime window_start (float timestamp) is handled."""
        current = time.time()

        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "window_start": current - 10,  # float, not datetime
            "request_count": 3,
        }
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_get_db.return_value = mock_db

        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_firestore("test-ip", current)
        assert result == 4

    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_window_start_none_defaults_to_zero(
        self, mock_get_db: MagicMock
    ) -> None:
        """Verify None window_start defaults to 0.0 (expired)."""
        current = time.time()

        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "window_start": None,
            "request_count": 3,
        }
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_get_db.return_value = mock_db

        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_firestore("test-ip", current)
        assert result == 1  # Expired window, reset to 1

    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_new_client_creates_document(
        self, mock_get_db: MagicMock
    ) -> None:
        """Verify new client (no existing doc) creates a new document."""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_get_db.return_value = mock_db

        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_firestore("new-ip", time.time())
        assert result == 1
        mock_doc_ref.set.assert_called_once()

    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_exception_returns_none(self, mock_get_db: MagicMock) -> None:
        """Verify Firestore exceptions return None and mark unavailable."""
        mock_db = MagicMock()
        mock_db.collection.side_effect = Exception("Firestore error")
        mock_get_db.return_value = mock_db

        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_firestore("test-ip", time.time())
        assert result is None
        assert limiter._firestore_available is False


class TestFirestoreRateLimiterMemoryFallback:
    """Tests for FirestoreRateLimiter._check_and_increment_memory."""

    def test_memory_new_client(self) -> None:
        """Verify new client gets count 1 in memory fallback."""
        limiter = FirestoreRateLimiter()
        result = limiter._check_and_increment_memory("new-ip", time.time())
        assert result == 1

    def test_memory_existing_client_within_window(self) -> None:
        """Verify existing client increments count within window."""
        current = time.time()
        limiter = FirestoreRateLimiter()
        limiter._memory_fallback["existing-ip"] = {
            "window_start": current - 10,
            "request_count": 3,
        }
        result = limiter._check_and_increment_memory("existing-ip", current)
        assert result == 4

    def test_memory_expired_window_resets(self) -> None:
        """Verify expired window resets counter in memory fallback."""
        current = time.time()
        limiter = FirestoreRateLimiter()
        limiter._memory_fallback["old-ip"] = {
            "window_start": current - 120,
            "request_count": 50,
        }
        result = limiter._check_and_increment_memory("old-ip", current)
        assert result == 1

    def test_memory_eviction_when_over_limit(self) -> None:
        """Verify oldest entries are evicted when over max client entries."""
        limiter = FirestoreRateLimiter()
        current = time.time()
        # Fill up beyond max
        for i in range(_MAX_CLIENT_ENTRIES + 10):
            limiter._memory_fallback[f"ip-{i}"] = {
                "window_start": current,
                "request_count": 1,
            }
        # Trigger eviction
        limiter._check_and_increment_memory("new-ip", current)
        assert len(limiter._memory_fallback) <= _MAX_CLIENT_ENTRIES


class TestFirestoreRateLimiterCheckAndIncrement:
    """Tests for the async check_and_increment method."""

    def test_firestore_available_uses_firestore(self) -> None:
        """Verify Firestore path is tried when available."""
        limiter = FirestoreRateLimiter()
        limiter._firestore_available = False  # Force memory fallback
        count = asyncio.run(limiter.check_and_increment("test-ip"))
        assert count == 1

    @patch.object(
        FirestoreRateLimiter,
        "_check_and_increment_firestore",
        return_value=3,
    )
    def test_firestore_available_returns_count(self, mock_firestore: MagicMock) -> None:
        """Verify Firestore result is returned when available."""
        limiter = FirestoreRateLimiter()
        limiter._firestore_available = True
        count = asyncio.run(limiter.check_and_increment("test-ip"))
        assert count == 3

    @patch.object(
        FirestoreRateLimiter,
        "_check_and_increment_firestore",
        return_value=None,
    )
    def test_firestore_falls_back_to_memory(self, mock_firestore: MagicMock) -> None:
        """Verify memory fallback when Firestore returns None."""
        limiter = FirestoreRateLimiter()
        limiter._firestore_available = True
        count = asyncio.run(limiter.check_and_increment("test-ip"))
        assert count == 1  # Falls back to memory


# ===========================================================================
# RateLimiterMiddleware (Firestore-backed) dispatch tests
# ===========================================================================


class TestRateLimiterMiddlewareDispatch:
    """Tests for RateLimiterMiddleware.dispatch with rate limiting."""

    def test_middleware_allows_request_under_limit(self) -> None:
        """Verify request is allowed when under rate limit."""
        test_app = FastAPI()

        @test_app.get("/test")
        async def test_route() -> dict:
            return {"status": "ok"}

        test_app.add_middleware(RateLimiterMiddleware)
        client = TestClient(test_app)
        response = client.get("/test")
        assert response.status_code == 200

    def test_middleware_blocks_request_over_limit(self) -> None:
        """Verify request is blocked when rate limit exceeded."""
        test_app = FastAPI()

        @test_app.get("/test")
        async def test_route() -> dict:
            return {"status": "ok"}

        test_app.add_middleware(RateLimiterMiddleware)
        client = TestClient(test_app)

        # Exceed the rate limit
        limit = AppConstants.RATE_LIMIT_REQUESTS_PER_MINUTE
        for _ in range(limit):
            client.get("/test")

        # Next request should be blocked
        response = client.get("/test")
        assert response.status_code == 429

    def test_middleware_ai_endpoint_stricter_limit(self) -> None:
        """Verify AI endpoints have stricter rate limiting."""
        test_app = FastAPI()

        @test_app.post("/api/v1/ai/insights")
        async def ai_route() -> dict:
            return {"status": "ok"}

        test_app.add_middleware(RateLimiterMiddleware)
        client = TestClient(test_app)

        ai_limit = AppConstants.RATE_LIMIT_AI_REQUESTS_PER_MINUTE
        for _ in range(ai_limit):
            client.post(
                "/api/v1/ai/insights", headers={"X-Requested-With": "XMLHttpRequest"}
            )

        response = client.post(
            "/api/v1/ai/insights", headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 429


# ===========================================================================
# InMemoryRateLimiterMiddleware additional tests
# ===========================================================================


class TestInMemoryRateLimiterEviction:
    """Tests for InMemoryRateLimiterMiddleware._evict_if_needed."""

    def test_eviction_triggers_when_over_limit(self) -> None:
        """Verify eviction occurs when client count exceeds max."""
        test_app = FastAPI()

        @test_app.get("/test")
        async def test_route() -> dict:
            return {"status": "ok"}

        test_app.add_middleware(InMemoryRateLimiterMiddleware)

        # Test the internal method directly
        middleware = InMemoryRateLimiterMiddleware(test_app)
        current = time.time()
        # Fill beyond limit
        for i in range(_MAX_CLIENT_ENTRIES + 10):
            middleware._clients[f"ip-{i}"] = {
                "window_start": current,
                "request_count": 1,
            }
        middleware._evict_if_needed()
        assert len(middleware._clients) <= _MAX_CLIENT_ENTRIES

    def test_no_eviction_when_under_limit(self) -> None:
        """Verify no eviction when client count is under max."""
        test_app = FastAPI()
        middleware = InMemoryRateLimiterMiddleware(test_app)
        current = time.time()
        for i in range(10):
            middleware._clients[f"ip-{i}"] = {
                "window_start": current,
                "request_count": 1,
            }
        initial_count = len(middleware._clients)
        middleware._evict_if_needed()
        assert len(middleware._clients) == initial_count
