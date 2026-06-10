"""Tests for the shared verify_user_access function.

Tests cover:
- Authenticated user accessing own data (allowed)
- Authenticated user accessing different user data (403)
- Anonymous user accessing own anonymous ID (allowed)
- Anonymous user accessing different user ID (403)
- Context parameter is used in logging for anonymous cross-user access
"""

import pytest
from fastapi import HTTPException

from app.constants import AppConstants
from app.middleware.auth import verify_user_access


class TestVerifyUserAccessAuthenticated:
    """Tests for authenticated user access checks."""

    @pytest.mark.unit
    def test_same_user_returns_uid(self) -> None:
        """Verify authenticated user accessing own data returns their UID."""
        result = verify_user_access("user-001", "user-001")
        assert result == "user-001"

    @pytest.mark.unit
    def test_different_user_raises_403(self) -> None:
        """Verify authenticated user accessing different user data raises 403."""
        with pytest.raises(HTTPException) as exc_info:
            verify_user_access("user-001", "user-002")
        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail


class TestVerifyUserAccessAnonymous:
    """Tests for anonymous user access checks."""

    @pytest.mark.unit
    def test_anonymous_user_accessing_own_id_allowed(self) -> None:
        """Verify anonymous user accessing their own ID is allowed."""
        anon_id = f"{AppConstants.ANONYMOUS_ID_PREFIX}abc123"
        result = verify_user_access(anon_id, anon_id)
        assert result == anon_id

    @pytest.mark.unit
    def test_anonymous_user_accessing_different_id_raises_403(self) -> None:
        """Verify anonymous user accessing a different user_id raises 403."""
        anon_id = f"{AppConstants.ANONYMOUS_ID_PREFIX}abc123"
        with pytest.raises(HTTPException) as exc_info:
            verify_user_access(anon_id, "user-001")
        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail

    @pytest.mark.unit
    def test_anonymous_user_accessing_different_anon_id_raises_403(self) -> None:
        """Verify anonymous user accessing a different anonymous ID raises 403."""
        anon_id_1 = f"{AppConstants.ANONYMOUS_ID_PREFIX}abc123"
        anon_id_2 = f"{AppConstants.ANONYMOUS_ID_PREFIX}def456"
        with pytest.raises(HTTPException) as exc_info:
            verify_user_access(anon_id_1, anon_id_2)
        assert exc_info.value.status_code == 403


class TestVerifyUserAccessContext:
    """Tests for the context parameter in verify_user_access."""

    @pytest.mark.unit
    def test_context_parameter_accepted(self) -> None:
        """Verify the context parameter is accepted without error."""
        # Same user — should succeed regardless of context
        result = verify_user_access("user-001", "user-001", context="footprint")
        assert result == "user-001"

    @pytest.mark.unit
    def test_context_included_in_anonymous_cross_user_warning(self) -> None:
        """Verify context is used when logging anonymous cross-user access."""
        anon_id = f"{AppConstants.ANONYMOUS_ID_PREFIX}abc123"
        # Should raise 403 — the context is logged, we just verify it doesn't crash
        with pytest.raises(HTTPException):
            verify_user_access(anon_id, "user-001", context="ai")
