"""Tests for the admin routes.

Tests cover:
- Cache cleanup endpoint with valid admin key (200)
- Cache cleanup endpoint with missing admin key (401)
- Cache cleanup endpoint when ADMIN_API_KEY not configured (503)
- Cache cleanup endpoint with wrong admin key (401)
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(name="client")
def fixture_test_client() -> TestClient:
    """Provide a TestClient instance bound to the application."""
    return TestClient(app)


class TestAdminCleanupCache:
    """Tests for the /api/v1/admin/cleanup-cache endpoint."""

    @pytest.mark.integration
    @patch.dict(os.environ, {"ADMIN_API_KEY": "test-secret-key-123"})
    @patch("app.routes.admin.cleanup_expired_cache_entries", return_value=5)
    def test_cleanup_with_valid_key_returns_200(
        self, mock_cleanup: object, client: TestClient
    ) -> None:
        """Verify valid admin key returns 200 with deleted count."""
        response = client.post(
            "/api/v1/admin/cleanup-cache",
            headers={"X-Admin-Key": "test-secret-key-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 5

    @pytest.mark.integration
    @patch.dict(os.environ, {"ADMIN_API_KEY": "test-secret-key-123"})
    def test_cleanup_with_wrong_key_returns_401(self, client: TestClient) -> None:
        """Verify wrong admin key returns 401 Unauthorized."""
        response = client.post(
            "/api/v1/admin/cleanup-cache",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert response.status_code == 401

    @pytest.mark.integration
    @patch.dict(os.environ, {"ADMIN_API_KEY": "test-secret-key-123"})
    def test_cleanup_with_missing_key_returns_401(self, client: TestClient) -> None:
        """Verify missing admin key header returns 401 Unauthorized."""
        response = client.post("/api/v1/admin/cleanup-cache")
        assert response.status_code == 401

    @pytest.mark.integration
    @patch.dict(os.environ, {}, clear=True)
    def test_cleanup_without_configured_key_returns_503(
        self, client: TestClient
    ) -> None:
        """Verify 503 when ADMIN_API_KEY environment variable is not set."""
        # Ensure ADMIN_API_KEY is not set
        os.environ.pop("ADMIN_API_KEY", None)
        response = client.post(
            "/api/v1/admin/cleanup-cache",
            headers={"X-Admin-Key": "any-key"},
        )
        assert response.status_code == 503

    @pytest.mark.integration
    @patch.dict(os.environ, {"ADMIN_API_KEY": ""})
    def test_cleanup_with_empty_configured_key_returns_503(
        self, client: TestClient
    ) -> None:
        """Verify 503 when ADMIN_API_KEY is empty string."""
        response = client.post(
            "/api/v1/admin/cleanup-cache",
            headers={"X-Admin-Key": "any-key"},
        )
        assert response.status_code == 503
