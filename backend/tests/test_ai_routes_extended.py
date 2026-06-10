"""Extended tests for ai_routes.py — covers _get_vertex_service reset path."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.ai_routes import _get_vertex_service


class TestGetVertexServiceReset:
    """Tests for _get_vertex_service client reset path."""

    def setup_method(self) -> None:
        """Reset the module-level singleton before each test."""
        import app.routes.ai_routes as ai_module
        ai_module._vertex_service_instance = None

    def teardown_method(self) -> None:
        """Clean up the module-level singleton after each test."""
        import app.routes.ai_routes as ai_module
        ai_module._vertex_service_instance = None

    @patch("app.routes.ai_routes.VertexAiService")
    def test_creates_new_instance_when_none(self, mock_service_cls: MagicMock) -> None:
        """Verify _get_vertex_service creates a new instance when none exists."""
        mock_instance = MagicMock()
        mock_service_cls.return_value = mock_instance

        result = _get_vertex_service()
        assert result is mock_instance
        mock_service_cls.assert_called_once()

    @patch("app.routes.ai_routes.VertexAiService")
    def test_returns_existing_healthy_instance(self, mock_service_cls: MagicMock) -> None:
        """Verify _get_vertex_service returns existing healthy instance."""
        mock_instance = MagicMock()
        mock_instance.is_healthy.return_value = True

        import app.routes.ai_routes as ai_module
        ai_module._vertex_service_instance = mock_instance

        result = _get_vertex_service()
        assert result is mock_instance
        mock_service_cls.assert_not_called()

    @patch("app.routes.ai_routes.VertexAiService")
    def test_resets_unhealthy_instance(self, mock_service_cls: MagicMock) -> None:
        """Verify _get_vertex_service resets an unhealthy instance."""
        mock_instance = MagicMock()
        mock_instance.is_healthy.return_value = False
        mock_instance.reset_client.return_value = None

        import app.routes.ai_routes as ai_module
        ai_module._vertex_service_instance = mock_instance

        result = _get_vertex_service()
        assert result is mock_instance
        mock_instance.reset_client.assert_called_once()
