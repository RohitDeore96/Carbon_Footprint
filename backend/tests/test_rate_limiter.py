"""Tests for the RateLimiterMiddleware.

Tests cover:
- Requests under the rate limit are forwarded normally
- Requests exceeding the rate limit receive 429 responses
- AI endpoints receive stricter rate limiting (10 req/min)
- FirestoreRateLimiter falls back to in-memory when Firestore unavailable
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.constants import AppConstants
from app.middleware.rate_limiter import (
    InMemoryRateLimiterMiddleware,
    RateLimiterMiddleware,
)


@pytest.fixture(name="rate_limit_app")
def fixture_rate_limit_app() -> FastAPI:
    """Create a minimal FastAPI app with the RateLimiterMiddleware."""
    app = FastAPI()

    @app.get("/test-endpoint")
    async def test_route() -> dict:
        return {"status": "ok"}

    @app.post("/api/v1/ai/insights")
    async def ai_route() -> dict:
        return {"status": "ok"}

    app.add_middleware(InMemoryRateLimiterMiddleware)
    return app


@pytest.fixture(name="rate_limit_client")
def fixture_rate_limit_client(rate_limit_app: FastAPI) -> TestClient:
    """Provide a TestClient with the RateLimiterMiddleware applied."""
    return TestClient(rate_limit_app)


class TestRateLimiterAllows:
    """Tests for requests within the rate limit."""

    @pytest.mark.unit
    def test_first_request_is_allowed(self, rate_limit_client: TestClient) -> None:
        """Verify the first request is allowed through."""
        response = rate_limit_client.get("/test-endpoint")
        assert response.status_code == 200


class TestRateLimiterBlocks:
    """Tests for requests exceeding the rate limit."""

    @pytest.mark.unit
    def test_exceeding_rate_limit_returns_429(
        self, rate_limit_client: TestClient
    ) -> None:
        """Verify requests beyond the limit receive 429 Too Many Requests."""
        limit = AppConstants.RATE_LIMIT_REQUESTS_PER_MINUTE
        # Send limit + 1 requests
        for _ in range(limit):
            rate_limit_client.get("/test-endpoint")

        # The next request should be rate limited
        response = rate_limit_client.get("/test-endpoint")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]


class TestRateLimiterAIEndpoints:
    """Tests for stricter AI endpoint rate limiting."""

    @pytest.mark.unit
    def test_ai_endpoint_stricter_rate_limit(
        self, rate_limit_client: TestClient
    ) -> None:
        """Verify AI endpoints are rate limited at the stricter 10 req/min."""
        ai_limit = AppConstants.RATE_LIMIT_AI_REQUESTS_PER_MINUTE
        # Send limit requests
        for _ in range(ai_limit):
            rate_limit_client.post(
                "/api/v1/ai/insights", headers={"X-Requested-With": "XMLHttpRequest"}
            )

        # The next AI request should be rate limited
        response = rate_limit_client.post(
            "/api/v1/ai/insights", headers={"X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]


class TestFirestoreRateLimiterFallback:
    """Tests for FirestoreRateLimiter falling back to in-memory when Firestore unavailable."""

    @pytest.mark.unit
    def test_firestore_rate_limiter_falls_back_to_memory(self) -> None:
        """Verify FirestoreRateLimiter uses in-memory fallback when Firestore unavailable."""
        from app.middleware.rate_limiter import FirestoreRateLimiter

        limiter = FirestoreRateLimiter()
        limiter._firestore_available = False  # Skip real Firestore connection

        import asyncio

        count = asyncio.run(limiter.check_and_increment("test-ip-1"))
        assert count == 1

        count = asyncio.run(limiter.check_and_increment("test-ip-1"))
        assert count == 2

    @pytest.mark.unit
    def test_firestore_rate_limiter_different_ips_tracked_separately(self) -> None:
        """Verify different IPs are tracked independently in fallback mode."""
        from app.middleware.rate_limiter import FirestoreRateLimiter

        limiter = FirestoreRateLimiter()
        limiter._firestore_available = False  # Skip real Firestore connection

        import asyncio

        count1 = asyncio.run(limiter.check_and_increment("test-ip-a"))
        count2 = asyncio.run(limiter.check_and_increment("test-ip-b"))
        assert count1 == 1
        assert count2 == 1


class TestFirestoreRateLimiterMiddleware:
    """Tests for the new RateLimiterMiddleware that uses FirestoreRateLimiter."""

    @pytest.mark.unit
    @patch("app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client")
    def test_firestore_middleware_allows_first_request(
        self, mock_get_fs_client: MagicMock
    ) -> None:
        """Verify the Firestore-backed middleware allows the first request."""
        mock_get_fs_client.return_value = None  # Simulate Firestore unavailable

        test_app = FastAPI()

        @test_app.get("/test")
        async def test_route() -> dict:
            return {"status": "ok"}

        test_app.add_middleware(RateLimiterMiddleware)
        client = TestClient(test_app)
        response = client.get("/test")
        assert response.status_code == 200
