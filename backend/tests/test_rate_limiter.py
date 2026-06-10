"""Tests for the RateLimiterMiddleware.

Tests cover:
- Requests under the rate limit are forwarded normally
- Requests exceeding the rate limit receive 429 responses
- AI endpoints receive stricter rate limiting (10 req/min)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.constants import AppConstants
from app.middleware.rate_limiter import RateLimiterMiddleware


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

    app.add_middleware(RateLimiterMiddleware)
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
            rate_limit_client.post("/api/v1/ai/insights")

        # The next AI request should be rate limited
        response = rate_limit_client.post("/api/v1/ai/insights")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
