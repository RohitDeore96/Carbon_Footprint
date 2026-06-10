"""Tests for admin.py migration-status endpoint and other uncovered paths."""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class TestMigrationStatusEndpoint:
    """Tests for the /api/v1/admin/migration-status endpoint."""

    def test_migration_status_with_valid_key(self) -> None:
        """Verify migration-status endpoint returns schema info with valid admin key."""
        with patch.dict(os.environ, {"ADMIN_API_KEY": "test-key-123"}):
            client = TestClient(app)
            response = client.get(
                "/api/v1/admin/migration-status",
                headers={"X-Admin-Key": "test-key-123"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "current_schema_version" in data
            assert "registered_migrations" in data
            assert "migration_count" in data

    def test_migration_status_with_invalid_key(self) -> None:
        """Verify migration-status endpoint returns 401 with invalid admin key."""
        with patch.dict(os.environ, {"ADMIN_API_KEY": "test-key-123"}):
            client = TestClient(app)
            response = client.get(
                "/api/v1/admin/migration-status",
                headers={"X-Admin-Key": "wrong-key"},
            )
            assert response.status_code == 401

    def test_migration_status_without_key(self) -> None:
        """Verify migration-status endpoint returns 401 without admin key."""
        with patch.dict(os.environ, {"ADMIN_API_KEY": "test-key-123"}):
            client = TestClient(app)
            response = client.get("/api/v1/admin/migration-status")
            assert response.status_code == 401

    def test_migration_status_no_configured_key(self) -> None:
        """Verify migration-status endpoint returns 503 when ADMIN_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure ADMIN_API_KEY is not set
            os.environ.pop("ADMIN_API_KEY", None)
            client = TestClient(app)
            response = client.get(
                "/api/v1/admin/migration-status",
                headers={"X-Admin-Key": "any-key"},
            )
            assert response.status_code == 503
