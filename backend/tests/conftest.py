"""Shared test fixtures and configuration."""

from unittest.mock import MagicMock, patch

import pytest
from app.main import app
from app.middleware.auth import get_current_user
from app.routes.footprint import get_firebase_service

# CSRF header that the frontend sends with every POST/PUT/DELETE request.
# Test requests must include this header to pass the CSRFMiddleware.
CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(name="csrf_headers")
def fixture_csrf_headers() -> dict[str, str]:
    """Provide the CSRF header required for state-changing requests in tests."""
    return CSRF_HEADERS.copy()


@pytest.fixture(autouse=True)
def _mock_firestore_rate_limiter():
    """Patch FirestoreRateLimiter._get_firestore_client for all tests.

    Without this, every request through RateLimiterMiddleware tries to
    connect to real Firebase/Firestore, causing multi-second connection
    timeouts that make the test suite extremely slow.
    """
    with patch(
        "app.middleware.rate_limiter.FirestoreRateLimiter._get_firestore_client",
        return_value=None,
    ):
        # Also pre-set the app's rate limiter to skip Firestore
        try:
            stack = getattr(app, "middleware_stack", None)
            if stack is not None:
                _disable_firestore_on_rate_limiter(stack)
        except Exception:
            pass
        yield


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


def _disable_firestore_on_rate_limiter(stack: object) -> None:
    """Pre-set _firestore_available=False on RateLimiterMiddleware instances."""
    from app.middleware.rate_limiter import RateLimiterMiddleware

    current = stack
    visited = set()
    while current is not None:
        if id(current) in visited:
            break
        visited.add(id(current))

        if isinstance(current, RateLimiterMiddleware):
            current._rate_limiter._firestore_available = False
            return

        inner = getattr(current, "app", None)
        if inner is None:
            break
        current = inner


def _clear_rate_limiter_from_stack(stack: object) -> None:
    """Recursively search the middleware stack for rate limiter middleware and reset it."""
    from app.middleware.rate_limiter import (
        InMemoryRateLimiterMiddleware,
        RateLimiterMiddleware,
    )

    current = stack
    visited = set()
    while current is not None:
        if id(current) in visited:
            break
        visited.add(id(current))

        if isinstance(current, InMemoryRateLimiterMiddleware):
            current._clients.clear()
            return

        if isinstance(current, RateLimiterMiddleware):
            current._rate_limiter._memory_fallback.clear()
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


@pytest.fixture(name="authenticated_user")
def fixture_authenticated_user():
    """Override get_current_user to return a fixed authenticated UID.

    By default, tests run as an authenticated user with UID
    ``test-authenticated-user``. This ensures strict ownership
    checks pass (the user can only access their own data).
    Individual tests can override this with a different UID
    by calling ``_override_auth(uid)`` directly.
    """
    uid = "test-authenticated-user"

    async def _mock_get_current_user():
        return uid

    app.dependency_overrides[get_current_user] = _mock_get_current_user
    yield uid
    app.dependency_overrides.pop(get_current_user, None)
