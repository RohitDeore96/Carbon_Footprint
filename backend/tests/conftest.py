"""Shared test fixtures and configuration."""

from unittest.mock import MagicMock

import pytest

from app.main import app
from app.routes.footprint import get_firebase_service


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the rate limiter middleware state before each test.

    The RateLimiterMiddleware holds per-IP request counts in memory.
    Without resetting, sequential tests accumulate counts and cause
    false 429 responses — especially for the stricter AI endpoint
    limit (10 req/min).
    """
    try:
        stack = getattr(app, "middleware_stack", None)
        if stack is not None:
            _clear_rate_limiter_from_stack(stack)
    except Exception:
        pass

    yield  # Run the test

    # Clean up dependency overrides after each test
    app.dependency_overrides.clear()


def _clear_rate_limiter_from_stack(stack: object) -> None:
    """Recursively search the middleware stack for RateLimiterMiddleware and reset it."""
    from app.middleware.rate_limiter import RateLimiterMiddleware

    current = stack
    visited = set()
    while current is not None:
        if id(current) in visited:
            break
        visited.add(id(current))

        if isinstance(current, RateLimiterMiddleware):
            current._clients.clear()
            return

        inner = getattr(current, "app", None)
        if inner is None:
            break
        current = inner


@pytest.fixture(name="mock_firebase_service", autouse=True)
def fixture_mock_firebase_service():
    """Override get_firebase_service with a mock for all tests.

    Prevents real Firebase initialization during tests. Individual tests
    can further customize the mock's return values as needed.
    """
    mock_service = MagicMock()
    mock_service.write_carbon_log.return_value = "mock-doc-id"
    mock_service.get_user_logs.return_value = []
    app.dependency_overrides[get_firebase_service] = lambda: mock_service
    yield mock_service
