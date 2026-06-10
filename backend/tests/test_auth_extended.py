"""Extended tests for auth.py — covers ensure_firebase_initialized already-initialized path."""

from unittest.mock import MagicMock, patch

from app.middleware.auth import ensure_firebase_initialized


class TestEnsureFirebaseInitializedAlreadyInitialized:
    """Tests for ensure_firebase_initialized when already initialized."""

    @patch("app.middleware.auth._firebase_app_initialized", True)
    def test_returns_immediately_when_already_initialized(self) -> None:
        """Verify ensure_firebase_initialized returns immediately when flag is True."""
        import app.middleware.auth as auth_module

        auth_module._firebase_app_initialized = True

        with patch("app.middleware.auth.get_app") as mock_get_app:
            ensure_firebase_initialized()
            # get_app should NOT be called when flag is True
            mock_get_app.assert_not_called()

        auth_module._firebase_app_initialized = True

    @patch("app.middleware.auth._firebase_app_initialized", False)
    def test_calls_get_app_when_flag_is_false(self) -> None:
        """Verify ensure_firebase_initialized checks get_app when flag is False."""
        import app.middleware.auth as auth_module

        auth_module._firebase_app_initialized = False

        with patch("app.middleware.auth.get_app") as mock_get_app:
            mock_get_app.return_value = MagicMock()
            ensure_firebase_initialized()
            mock_get_app.assert_called_once()
            assert auth_module._firebase_app_initialized is True

        auth_module._firebase_app_initialized = True
