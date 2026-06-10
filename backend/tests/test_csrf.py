"""Tests for CSRF middleware — covers all code paths in csrf.py.

Tests cover:
- Safe methods (GET, HEAD, OPTIONS) pass through
- Admin paths bypass CSRF check
- Bearer token requests bypass CSRF check
- X-Admin-Key requests bypass CSRF check
- X-Requested-With header validation
- Origin header matching allowed origins
- Referer header matching allowed origins
- Rejection when no valid CSRF indicator is present
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.constants import AppConstants
from app.middleware.csrf import CSRFMiddleware


def _create_csrf_test_app() -> FastAPI:
    """Create a minimal FastAPI app with CSRF middleware for testing."""
    application = FastAPI()

    @application.post("/api/v1/test")
    async def test_post() -> dict:
        return {"status": "ok"}

    @application.post("/api/v1/admin/cleanup-cache")
    async def admin_post() -> dict:
        return {"status": "admin_ok"}

    @application.get("/api/v1/test")
    async def test_get() -> dict:
        return {"status": "ok"}

    application.add_middleware(CSRFMiddleware)
    return application


class TestCSRFMiddlewareSafeMethods:
    """Test that safe HTTP methods always pass through."""

    @pytest.mark.unit
    def test_get_request_passes_through(self) -> None:
        """Verify GET requests pass through without CSRF checks."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.get("/api/v1/test")
        assert response.status_code == 200

    @pytest.mark.unit
    def test_head_request_passes_through(self) -> None:
        """Verify HEAD requests pass through without CSRF checks."""
        app = _create_csrf_test_app()

        @app.head("/api/v1/head-test")
        async def head_test() -> dict:
            return {}

        client = TestClient(app)
        response = client.head("/api/v1/head-test")
        assert response.status_code == 200

    @pytest.mark.unit
    def test_options_request_passes_through(self) -> None:
        """Verify OPTIONS requests pass through without CSRF checks."""
        app = _create_csrf_test_app()

        @app.options("/api/v1/opt-test")
        async def opt_test() -> dict:
            return {}

        client = TestClient(app)
        response = client.options("/api/v1/opt-test")
        assert response.status_code == 200


class TestCSRFMiddlewareAdminPaths:
    """Test that admin paths bypass CSRF checks."""

    @pytest.mark.unit
    def test_admin_post_without_csrf_headers_passes(self) -> None:
        """Verify POST to admin path passes without CSRF headers."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post("/api/v1/admin/cleanup-cache")
        # The endpoint itself may return 401 for missing admin key,
        # but it should NOT be blocked by CSRF (which returns 403)
        assert response.status_code != 403 or "CSRF" not in response.text


class TestCSRFMiddlewareBearerToken:
    """Test that Bearer token requests bypass CSRF checks."""

    @pytest.mark.unit
    def test_bearer_token_passes_csrf(self) -> None:
        """Verify POST with Bearer token passes without X-Requested-With."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/test",
            headers={"Authorization": "Bearer test-token-123"},
            json={},
        )
        assert response.status_code == 200


class TestCSRFMiddlewareAdminKeyHeader:
    """Test that X-Admin-Key requests bypass CSRF checks."""

    @pytest.mark.unit
    def test_admin_key_header_passes_csrf(self) -> None:
        """Verify POST with X-Admin-Key header passes without X-Requested-With."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/test",
            headers={"X-Admin-Key": "some-key"},
            json={},
        )
        assert response.status_code == 200


class TestCSRFMiddlewareXRequestedWith:
    """Test X-Requested-With header validation."""

    @pytest.mark.unit
    def test_xmlhttprequest_header_passes(self) -> None:
        """Verify POST with X-Requested-With: XMLHttpRequest passes."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/test",
            headers={"X-Requested-With": "XMLHttpRequest"},
            json={},
        )
        assert response.status_code == 200

    @pytest.mark.unit
    def test_lowercase_xmlhttprequest_header_passes(self) -> None:
        """Verify case-insensitive matching of XMLHttpRequest value."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/test",
            headers={"X-Requested-With": "xmlhttprequest"},
            json={},
        )
        assert response.status_code == 200


class TestCSRFMiddlewareOriginHeader:
    """Test Origin header matching against allowed origins."""

    @pytest.mark.unit
    def test_valid_origin_passes(self) -> None:
        """Verify POST with an allowed Origin header passes."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        # Use the first allowed origin from AppConstants
        allowed_origin = AppConstants.CORS_ALLOWED_ORIGINS[0]
        response = client.post(
            "/api/v1/test",
            headers={"Origin": allowed_origin},
            json={},
        )
        assert response.status_code == 200

    @pytest.mark.unit
    def test_invalid_origin_blocked(self) -> None:
        """Verify POST with a disallowed Origin is blocked (falls through to Referer check)."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/test",
            headers={"Origin": "https://evil.com"},
            json={},
        )
        # Should be 403 since Origin doesn't match and no Referer/X-Requested-With
        assert response.status_code == 403


class TestCSRFMiddlewareRefererHeader:
    """Test Referer header matching as a fallback."""

    @pytest.mark.unit
    def test_valid_referer_passes(self) -> None:
        """Verify POST with a Referer matching allowed origin passes."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        allowed_origin = AppConstants.CORS_ALLOWED_ORIGINS[0]
        response = client.post(
            "/api/v1/test",
            headers={"Referer": f"{allowed_origin}/some/page"},
            json={},
        )
        assert response.status_code == 200

    @pytest.mark.unit
    def test_invalid_referer_blocked(self) -> None:
        """Verify POST with a non-matching Referer is blocked."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/test",
            headers={"Referer": "https://evil.com/attack"},
            json={},
        )
        assert response.status_code == 403


class TestCSRFMiddlewareRejection:
    """Test CSRF rejection when no valid indicator is present."""

    @pytest.mark.unit
    def test_post_without_csrf_indicators_returns_403(self) -> None:
        """Verify POST without any CSRF indicator returns 403."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post("/api/v1/test", json={})
        assert response.status_code == 403
        assert "CSRF validation failed" in response.json()["detail"]

    @pytest.mark.unit
    def test_wrong_x_requested_with_value_blocked(self) -> None:
        """Verify POST with incorrect X-Requested-With value is blocked."""
        app = _create_csrf_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/test",
            headers={"X-Requested-With": "WrongValue"},
            json={},
        )
        assert response.status_code == 403
