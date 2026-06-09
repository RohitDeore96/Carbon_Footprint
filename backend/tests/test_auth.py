"""Tests for the Firebase Authentication middleware.

Tests cover:
- get_current_user with no credentials (anonymous access)
- get_current_user with valid Firebase ID token
- get_current_user with invalid/expired Firebase ID token
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.middleware.auth import get_current_user


@pytest.fixture(name="auth_app")
def fixture_auth_app() -> FastAPI:
    """Create a minimal FastAPI app for testing the auth dependency."""
    app = FastAPI()

    @app.get("/test-auth")
    async def test_route(user_id: str = Depends(get_current_user)) -> dict:
        return {"user_id": user_id}

    return app


@pytest.fixture(name="auth_client")
def fixture_auth_client(auth_app: FastAPI) -> TestClient:
    """Provide a TestClient for the auth test app."""
    return TestClient(auth_app)


class TestGetCurrentUserAnonymous:
    """Tests for anonymous (no Authorization header) access."""

    @pytest.mark.unit
    def test_no_auth_header_returns_anonymous(self, auth_client: TestClient) -> None:
        """Verify requests without Authorization header get 'anonymous' user."""
        response = auth_client.get("/test-auth")
        assert response.status_code == 200
        assert response.json()["user_id"] == "anonymous"


class TestGetCurrentUserValidToken:
    """Tests for valid Firebase ID token authentication."""

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_valid_token_returns_uid(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify valid Firebase ID token returns the decoded UID."""
        mock_firebase_auth.verify_id_token.return_value = {"uid": "user-abc-123"}
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer valid-firebase-token"}
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == "user-abc-123"


class TestGetCurrentUserInvalidToken:
    """Tests for invalid/expired Firebase ID token."""

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_invalid_token_returns_401(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify invalid Firebase ID token returns 401 Unauthorized."""
        mock_firebase_auth.verify_id_token.side_effect = Exception("Token expired")
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer expired-token"}
        )
        assert response.status_code == 401
        assert "Invalid or expired authentication token" in response.json()["detail"]
