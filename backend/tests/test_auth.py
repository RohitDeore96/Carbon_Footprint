"""Tests for the Firebase Authentication middleware.

Tests cover:
- get_current_user with no credentials (generates unique anonymous ID)
- get_current_user with valid Firebase ID token
- get_current_user with expired Firebase ID token (401)
- get_current_user with invalid Firebase ID token (401)
- get_current_user with revoked Firebase ID token (401)
- get_current_user with malformed token (ValueError, 401)
- get_current_user with uninitialized Firebase SDK (ValueError, 503)
- get_current_user with connection/timeout errors (503)
- get_current_user with unexpected auth error (503)
- Uniqueness of generated anonymous IDs across requests
- ensure_firebase_initialized idempotency
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.middleware.auth import get_current_user, ensure_firebase_initialized


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
    def test_no_auth_header_returns_anon_prefixed_id(
        self, auth_client: TestClient
    ) -> None:
        """Verify requests without Authorization header get an 'anon-' prefixed user ID."""
        response = auth_client.get("/test-auth")
        assert response.status_code == 200
        user_id: str = response.json()["user_id"]
        assert user_id.startswith("anon-")

    @pytest.mark.unit
    def test_each_anonymous_request_gets_unique_id(
        self, auth_client: TestClient
    ) -> None:
        """Verify each request without auth generates a unique anonymous ID."""
        response1 = auth_client.get("/test-auth")
        response2 = auth_client.get("/test-auth")
        user_id_1: str = response1.json()["user_id"]
        user_id_2: str = response2.json()["user_id"]
        assert user_id_1 != user_id_2


class TestGetCurrentUserValidToken:
    """Tests for valid Firebase ID token authentication."""

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_valid_token_returns_uid(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify valid Firebase ID token returns the decoded UID."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.return_value = {"uid": "user-abc-123"}
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer valid-firebase-token"}
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == "user-abc-123"


class TestGetCurrentUserExpiredToken:
    """Tests for expired Firebase ID token."""

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_expired_token_returns_401(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify expired Firebase ID token returns 401 with proper message."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.side_effect = (
            firebase_auth_exceptions.ExpiredIdTokenError("Token expired", None)
        )
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer expired-token"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


class TestGetCurrentUserInvalidToken:
    """Tests for invalid Firebase ID token."""

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_invalid_token_returns_401(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify invalid Firebase ID token returns 401 with proper message."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.side_effect = (
            firebase_auth_exceptions.InvalidIdTokenError("Invalid token")
        )
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_malformed_token_returns_401(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify malformed token (ValueError) returns 401 Unauthorized."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.side_effect = ValueError("Malformed JWT")
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer malformed-token"}
        )
        assert response.status_code == 401
        assert "Malformed authentication token" in response.json()["detail"]

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_uninitialized_sdk_valueerror_returns_503(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify ValueError from uninitialized Firebase SDK returns 503, not 401."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.side_effect = ValueError(
            "The default Firebase app does not exist. "
            "Make sure to initialize the SDK by calling initialize_app()."
        )
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer some-token"}
        )
        assert response.status_code == 503
        assert "not ready" in response.json()["detail"].lower()


class TestGetCurrentUserRevokedToken:
    """Tests for revoked Firebase ID token."""

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_revoked_token_returns_401(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify revoked Firebase ID token returns 401 with proper message."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.side_effect = (
            firebase_auth_exceptions.RevokedIdTokenError("Token revoked")
        )
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer revoked-token"}
        )
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()


class TestGetCurrentUserServerErrors:
    """Tests for server-side errors during token verification (503 responses)."""

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_connection_error_returns_503(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify network error during token verification returns 503."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.side_effect = ConnectionError(
            "Failed to reach Firebase Auth service"
        )
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer some-token"}
        )
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_timeout_error_returns_503(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify timeout during token verification returns 503."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.side_effect = TimeoutError(
            "Firebase Auth verification timed out"
        )
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer some-token"}
        )
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

    @pytest.mark.unit
    @patch("app.middleware.auth.firebase_auth")
    def test_unexpected_error_returns_503(
        self, mock_firebase_auth: MagicMock, auth_client: TestClient
    ) -> None:
        """Verify unexpected auth error returns 503 (server error, not auth)."""
        from firebase_admin import auth as firebase_auth_exceptions

        mock_firebase_auth.verify_id_token.side_effect = RuntimeError(
            "Unexpected error"
        )
        mock_firebase_auth.ExpiredIdTokenError = (
            firebase_auth_exceptions.ExpiredIdTokenError
        )
        mock_firebase_auth.InvalidIdTokenError = (
            firebase_auth_exceptions.InvalidIdTokenError
        )
        mock_firebase_auth.RevokedIdTokenError = (
            firebase_auth_exceptions.RevokedIdTokenError
        )
        response = auth_client.get(
            "/test-auth", headers={"Authorization": "Bearer some-token"}
        )
        assert response.status_code == 503
        assert "service error" in response.json()["detail"].lower()


class TestEnsureFirebaseInitialized:
    """Tests for the ensure_firebase_initialized helper."""

    @pytest.mark.unit
    @patch("app.middleware.auth.get_app")
    def test_skips_init_if_already_initialized(self, mock_get_app: MagicMock) -> None:
        """Verify no-op when Firebase Admin SDK is already initialized."""
        import app.middleware.auth as auth_module

        # Simulate already initialized
        auth_module._firebase_app_initialized = True
        ensure_firebase_initialized()
        mock_get_app.assert_not_called()
        # Reset for other tests
        auth_module._firebase_app_initialized = False

    @pytest.mark.unit
    @patch("app.middleware.auth.initialize_app")
    @patch("app.middleware.auth.get_app")
    def test_initializes_on_first_call(
        self, mock_get_app: MagicMock, mock_initialize_app: MagicMock
    ) -> None:
        """Verify SDK is initialized when get_app raises ValueError."""
        import app.middleware.auth as auth_module

        auth_module._firebase_app_initialized = False
        mock_get_app.side_effect = ValueError("App not found")
        ensure_firebase_initialized()
        mock_initialize_app.assert_called_once()
        # Should be set to True now
        assert auth_module._firebase_app_initialized is True
        # Reset for other tests
        auth_module._firebase_app_initialized = False
