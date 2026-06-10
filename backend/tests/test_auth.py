"""Tests for the Firebase Authentication middleware.

Tests cover:
- get_current_user with no credentials (anonymous access with unique ID)
- get_current_user with valid Firebase ID token
- get_current_user with invalid/expired Firebase ID token
- get_current_user with malformed Firebase ID token (ValueError)
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
    def test_no_auth_header_returns_unique_anonymous_id(
        self, auth_client: TestClient
    ) -> None:
        """Verify requests without Authorization header get a unique anonymous ID."""
        response = auth_client.get("/test-auth")
        assert response.status_code == 200
        user_id = response.json()["user_id"]
        assert user_id.startswith("anon-")
        assert len(user_id) > len("anon-")

    @pytest.mark.unit
    def test_each_anonymous_request_gets_unique_id(
        self, auth_client: TestClient
    ) -> None:
        """Verify each unauthenticated request receives a distinct anonymous ID."""
        response1 = auth_client.get("/test-auth")
        response2 = auth_client.get("/test-auth")
        id1 = response1.json()["user_id"]
        id2 = response2.json()["user_id"]
        # Each request should get a unique ID for data isolation
        assert id1 != id2
        assert id1.startswith("anon-")
        assert id2.startswith("anon-")


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
        from firebase_admin.exceptions import FirebaseError

        mock_firebase_auth.verify_id_token.side_effect = FirebaseError(
            code="INVALID_ID_TOKEN", message="Token expired"
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer expired-token"}
        )
        assert response.status_code == 401
        assert "Invalid or expired authentication token" in response.json()["detail"]

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_malformed_token_returns_401(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify malformed token (ValueError) returns 401 Unauthorized."""
        mock_firebase_auth.verify_id_token.side_effect = ValueError("Malformed JWT")
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer malformed-token"}
        )
        assert response.status_code == 401
        assert "Malformed authentication token" in response.json()["detail"]
