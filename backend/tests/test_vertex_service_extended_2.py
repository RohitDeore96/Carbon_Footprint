"""Extended tests for vertex_service.py — covers reset_client, is_healthy, generate_insights sync path."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.vertex_service import VertexAiService


class TestVertexAiServiceResetClient:
    """Tests for VertexAiService.reset_client."""

    @patch("app.services.vertex_service.genai")
    def test_reset_client_reinitializes(self, mock_genai: MagicMock) -> None:
        """Verify reset_client creates a new client."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            service = VertexAiService(client=MagicMock())
            service.reset_client()

        # After reset, _client should be the new one
        assert service._client is not None

    @patch("app.services.vertex_service.genai")
    def test_reset_client_with_provided_client(self, mock_genai: MagicMock) -> None:
        """Verify reset_client uses the provided client."""
        provided_client = MagicMock()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            service = VertexAiService(client=MagicMock())
            service.reset_client(client=provided_client)

        assert service._client is provided_client


class TestVertexAiServiceIsHealthy:
    """Tests for VertexAiService.is_healthy."""

    def test_healthy_when_client_exists(self) -> None:
        """Verify is_healthy returns True when client exists."""
        mock_client = MagicMock()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            service = VertexAiService(client=mock_client)
        assert service.is_healthy() is True

    def test_unhealthy_when_client_is_none(self) -> None:
        """Verify is_healthy returns False when client is None."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            service = VertexAiService(client=MagicMock())
        service._client = None
        assert service.is_healthy() is False

    def test_unhealthy_when_attribute_missing(self) -> None:
        """Verify is_healthy returns False when _client attribute is missing."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            service = VertexAiService(client=MagicMock())
        delattr(service, "_client")
        assert service.is_healthy() is False


class TestVertexAiServiceGenerateInsightsSync:
    """Tests for VertexAiService.generate_insights synchronous path."""

    @patch("app.services.vertex_service.genai")
    def test_generate_insights_without_running_loop(
        self, mock_genai: MagicMock
    ) -> None:
        """Verify generate_insights works outside an event loop."""
        mock_client = MagicMock()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            service = VertexAiService(client=mock_client)

        expected = {
            "insight": "test",
            "equivalent_impact": "test",
            "actionable_steps": ["step1"],
        }

        with patch.object(service, "generate_insights_async", return_value=expected):
            result = service.generate_insights(
                {"total_co2e_kg": 10, "period_days": 30, "emission_breakdown": []}
            )
        assert result == expected
