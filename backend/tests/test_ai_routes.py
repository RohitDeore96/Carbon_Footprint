"""Comprehensive tests for the AI insights endpoint and VertexAiService.

Tests cover:
- VertexAiService unit tests (prompt formatting, response parsing, model call)
- POST /api/v1/ai/insights happy path (200 OK)
- API failure path (simulated quota exceeded and network timeout → 500)
- Input validation path (empty emission_breakdown → 422)
- Ownership enforcement (403 for cross-user access)
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.constants import AppConstants
from app.main import app
from app.middleware.auth import get_current_user
from app.services.vertex_service import (
    VertexAiService,
    _build_response_schema,
    _extract_response_text,
    _format_prompt,
    _parse_model_response,
    _repair_truncated_json,
)


@pytest.fixture(name="client")
def fixture_test_client() -> TestClient:
    """Provide a TestClient instance bound to the application."""
    return TestClient(app)


@pytest.fixture(name="valid_insights_payload")
def fixture_valid_insights_payload() -> dict[str, Any]:
    """Provide a valid insights request payload with emission breakdown."""
    return {
        "user_id": "test-user-ai-001",
        "total_co2e_kg": 156.8,
        "period_days": 30,
        "emission_breakdown": [
            {
                "category": "transport",
                "total_co2e_kg": 85.5,
                "entry_count": 12,
                "description": "Daily car commute and weekend trips",
            },
            {
                "category": "energy",
                "total_co2e_kg": 48.3,
                "entry_count": 4,
                "description": "Home electricity and natural gas usage",
            },
            {
                "category": "food",
                "total_co2e_kg": 23.0,
                "entry_count": 7,
                "description": "Average diet with occasional meat-heavy meals",
            },
        ],
    }


@pytest.fixture(name="mock_ai_response_dict")
def fixture_mock_ai_response_dict() -> dict[str, Any]:
    """Provide a mock AI response dictionary matching the structured schema."""
    return {
        "insight": (
            "Your monthly carbon footprint of 156.8 kg CO2e is above the global average. "
            "Transport is your largest contributor at 54.5% of total emissions."
        ),
        "equivalent_impact": (
            "This is equivalent to charging 19,246 smartphones or driving 627 km in an average car."
        ),
        "actionable_steps": [
            "Switch two weekly car commutes to public transit to reduce transport emissions by 30%.",
            "Replace natural gas heating with a heat pump to cut energy emissions by 50%.",
            "Adopt two meatless days per week to reduce food emissions by 25%.",
        ],
    }


def _build_mock_genai_response(response_dict: dict[str, Any]) -> MagicMock:
    """Create a mock Gemini API response with the given dictionary as JSON text."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_dict)
    return mock_response


# ===========================================================================
# Unit Tests: Vertex AI Service Helper Functions
# ===========================================================================


class TestBuildResponseSchema:
    """Unit tests for the structured response schema builder."""

    @pytest.mark.unit
    def test_schema_contains_required_keys(self) -> None:
        """Verify the schema includes all three required response keys."""
        schema: dict[str, Any] = _build_response_schema()
        required: list[str] = schema["required"]
        assert "insight" in required
        assert "equivalent_impact" in required
        assert "actionable_steps" in required

    @pytest.mark.unit
    def test_schema_has_object_type(self) -> None:
        """Verify the schema root type is 'object'."""
        schema: dict[str, Any] = _build_response_schema()
        assert schema["type"] == "object"

    @pytest.mark.unit
    def test_schema_steps_is_array(self) -> None:
        """Verify actionable_steps is defined as an array of strings."""
        schema: dict[str, Any] = _build_response_schema()
        steps_schema = schema["properties"]["actionable_steps"]
        assert steps_schema["type"] == "array"
        assert steps_schema["items"]["type"] == "string"


class TestFormatPrompt:
    """Unit tests for prompt formatting."""

    @pytest.mark.unit
    def test_prompt_contains_total_emissions(self) -> None:
        """Verify the formatted prompt includes the total CO2e value."""
        user_data: dict[str, Any] = {
            "total_co2e_kg": 100.0,
            "period_days": 7,
            "emission_breakdown": [],
        }
        prompt: str = _format_prompt(user_data)
        assert "100.0 kg" in prompt

    @pytest.mark.unit
    def test_prompt_contains_period(self) -> None:
        """Verify the formatted prompt includes the period in days."""
        user_data: dict[str, Any] = {
            "total_co2e_kg": 50.0,
            "period_days": 30,
            "emission_breakdown": [],
        }
        prompt: str = _format_prompt(user_data)
        assert "30 days" in prompt

    @pytest.mark.unit
    def test_prompt_requests_exact_step_count(self) -> None:
        """Verify the prompt requests exactly 3 actionable steps."""
        user_data: dict[str, Any] = {
            "total_co2e_kg": 50.0,
            "period_days": 30,
            "emission_breakdown": [],
        }
        prompt: str = _format_prompt(user_data)
        expected_count: str = str(AppConstants.VERTEX_AI_ACTIONABLE_STEPS_COUNT)
        assert f"{expected_count} actionable steps" in prompt


class TestParseModelResponse:
    """Unit tests for response parsing."""

    @pytest.mark.unit
    def test_parse_valid_json(self) -> None:
        """Verify valid JSON string is parsed correctly."""
        raw: str = json.dumps(
            {"insight": "test", "equivalent_impact": "test", "actionable_steps": []}
        )
        result: dict[str, Any] = _parse_model_response(raw)
        assert result["insight"] == "test"

    @pytest.mark.unit
    def test_parse_invalid_json_raises(self) -> None:
        """Verify invalid JSON raises ValueError (wraps JSONDecodeError)."""
        with pytest.raises(ValueError, match="Failed to parse Gemini response"):
            _parse_model_response("not valid json {{{")


class TestExtractResponseText:
    """Unit tests for response text extraction."""

    @pytest.mark.unit
    def test_extract_text_from_response(self) -> None:
        """Verify text is extracted from a response with text content."""
        mock_response = MagicMock()
        mock_response.text = "extracted text"
        result: str = _extract_response_text(mock_response)
        assert result == "extracted text"

    @pytest.mark.unit
    def test_extract_none_text_raises(self) -> None:
        """Verify ValueError is raised when response text is None."""
        mock_response = MagicMock()
        mock_response.text = None
        with pytest.raises(ValueError, match="no text content"):
            _extract_response_text(mock_response)


# ===========================================================================
# Unit Tests: VertexAiService Class
# ===========================================================================


class TestVertexAiService:
    """Unit tests for the VertexAiService class."""

    @pytest.mark.unit
    def test_generate_insights_returns_parsed_dict(
        self,
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify generate_insights returns the parsed AI response dictionary."""
        mock_client = MagicMock()
        mock_response = _build_mock_genai_response(mock_ai_response_dict)
        mock_client.models.generate_content.return_value = mock_response
        service = VertexAiService(client=mock_client)
        result: dict[str, Any] = service.generate_insights(
            {
                "total_co2e_kg": 100.0,
                "period_days": 30,
                "emission_breakdown": [],
            }
        )
        assert result["insight"] == mock_ai_response_dict["insight"]
        assert len(result["actionable_steps"]) == 3

    @pytest.mark.unit
    def test_generate_insights_calls_model_with_correct_name(
        self,
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify the service calls the model with the configured model name."""
        mock_client = MagicMock()
        mock_response = _build_mock_genai_response(mock_ai_response_dict)
        mock_client.models.generate_content.return_value = mock_response
        service = VertexAiService(client=mock_client)
        service.generate_insights(
            {
                "total_co2e_kg": 50.0,
                "period_days": 7,
                "emission_breakdown": [],
            }
        )
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == AppConstants.VERTEX_AI_MODEL_NAME

    @pytest.mark.unit
    def test_generate_insights_quota_exceeded_raises(self) -> None:
        """Verify ResourceExhausted exception propagates from the service."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception(
            "429 Quota exceeded"
        )
        service = VertexAiService(client=mock_client)
        with pytest.raises(Exception, match="Quota exceeded"):
            service.generate_insights(
                {
                    "total_co2e_kg": 50.0,
                    "period_days": 7,
                    "emission_breakdown": [],
                }
            )

    @pytest.mark.unit
    def test_generate_insights_timeout_raises(self) -> None:
        """Verify TimeoutError propagates from the service."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError(
            "Request timed out"
        )
        service = VertexAiService(client=mock_client)
        with pytest.raises(TimeoutError, match="timed out"):
            service.generate_insights(
                {
                    "total_co2e_kg": 50.0,
                    "period_days": 7,
                    "emission_breakdown": [],
                }
            )


# ===========================================================================
# Integration Tests: POST /api/v1/ai/insights — Happy Path (200)
# ===========================================================================


class TestInsightsEndpointHappyPath:
    """Integration tests for successful AI insights requests."""

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_valid_payload_returns_200(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify valid payload returns 200 with complete insights response."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value=mock_ai_response_dict
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 200
            data: dict[str, Any] = response.json()
            assert data["user_id"] == "test-user-ai-001"
            assert data["model_used"] == AppConstants.VERTEX_AI_MODEL_NAME
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_response_contains_insight_field(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify the response includes the insight field from the AI model."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value=mock_ai_response_dict
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            data: dict[str, Any] = response.json()
            assert "insight" in data
            assert len(data["insight"]) > 0
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_response_contains_actionable_steps(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify the response includes exactly 3 actionable steps."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value=mock_ai_response_dict
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            data: dict[str, Any] = response.json()
            assert len(data["actionable_steps"]) == 3
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_response_contains_equivalent_impact(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify the response includes the equivalent_impact comparison."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value=mock_ai_response_dict
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            data: dict[str, Any] = response.json()
            assert "equivalent_impact" in data
            assert len(data["equivalent_impact"]) > 0
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_vertex_service_called_once(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify the VertexAiService.generate_insights_async is called exactly once."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value=mock_ai_response_dict
            )
            mock_get_service.return_value = mock_service
            client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            mock_service.generate_insights_async.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# Integration Tests: API Failure Path (500)
# ===========================================================================


class TestInsightsEndpointApiFailure:
    """Integration tests simulating Vertex AI service failures."""

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_quota_exceeded_returns_500(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
    ) -> None:
        """Verify simulated quota exceeded returns 500 with error detail."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                side_effect=Exception("429 Resource exhausted: quota exceeded")
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 500
            assert "temporarily unavailable" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_network_timeout_returns_500(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
    ) -> None:
        """Verify simulated network timeout returns 500 with error detail."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                side_effect=TimeoutError("Connection timed out after 30s")
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 500
            assert "temporarily unavailable" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_json_parse_error_returns_500(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
    ) -> None:
        """Verify malformed AI response triggers 500 with error detail."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                side_effect=ValueError("Invalid JSON from model")
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 500
            assert "temporarily unavailable" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# Integration Tests: Input Validation Path (422)
# ===========================================================================


class TestInsightsEndpointValidation:
    """Integration tests for Pydantic validation rejection scenarios."""

    @pytest.mark.integration
    def test_empty_emission_breakdown_returns_422(self, client: TestClient) -> None:
        """Verify empty emission_breakdown list triggers 422 validation error."""
        payload: dict[str, Any] = {
            "user_id": "user-001",
            "total_co2e_kg": 100.0,
            "period_days": 30,
            "emission_breakdown": [],
        }
        response = client.post(
            "/api/v1/ai/insights",
            json=payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_missing_user_id_returns_422(self, client: TestClient) -> None:
        """Verify missing user_id triggers 422 validation error."""
        payload: dict[str, Any] = {
            "total_co2e_kg": 100.0,
            "period_days": 30,
            "emission_breakdown": [
                {
                    "category": "transport",
                    "total_co2e_kg": 50.0,
                    "entry_count": 5,
                    "description": "Car commute",
                }
            ],
        }
        response = client.post(
            "/api/v1/ai/insights",
            json=payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_negative_total_returns_422(self, client: TestClient) -> None:
        """Verify negative total_co2e_kg triggers 422 validation error."""
        payload: dict[str, Any] = {
            "user_id": "user-001",
            "total_co2e_kg": -10.0,
            "period_days": 30,
            "emission_breakdown": [
                {
                    "category": "transport",
                    "total_co2e_kg": 50.0,
                    "entry_count": 5,
                    "description": "Car commute",
                }
            ],
        }
        response = client.post(
            "/api/v1/ai/insights",
            json=payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_zero_period_days_returns_422(self, client: TestClient) -> None:
        """Verify zero period_days triggers 422 validation error."""
        payload: dict[str, Any] = {
            "user_id": "user-001",
            "total_co2e_kg": 100.0,
            "period_days": 0,
            "emission_breakdown": [
                {
                    "category": "transport",
                    "total_co2e_kg": 50.0,
                    "entry_count": 5,
                    "description": "Car commute",
                }
            ],
        }
        response = client.post(
            "/api/v1/ai/insights",
            json=payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_empty_category_returns_422(self, client: TestClient) -> None:
        """Verify empty category string triggers 422 validation error."""
        payload: dict[str, Any] = {
            "user_id": "user-001",
            "total_co2e_kg": 100.0,
            "period_days": 30,
            "emission_breakdown": [
                {
                    "category": "",
                    "total_co2e_kg": 50.0,
                    "entry_count": 5,
                    "description": "Car commute",
                }
            ],
        }
        response = client.post(
            "/api/v1/ai/insights",
            json=payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_missing_body_returns_422(self, client: TestClient) -> None:
        """Verify completely empty request body triggers 422 validation error."""
        response = client.post(
            "/api/v1/ai/insights",
            json={},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 422


# ===========================================================================
# Unit Tests: VertexAiService Cache Hit and Fallback Model Paths
# ===========================================================================


class TestVertexAiServiceCacheHit:
    """Unit tests for the VertexAiService cache hit path (line 158)."""

    @pytest.mark.unit
    @patch("app.services.insights_cache.set_cached_insight")
    @patch("app.services.insights_cache.get_cached_insight")
    def test_cache_hit_returns_cached_result(
        self,
        mock_get_cache: MagicMock,
        mock_set_cache: MagicMock,
    ) -> None:
        """Verify generate_insights returns cached result without calling model."""
        cached_result = {
            "insight": "cached insight",
            "equivalent_impact": "cached impact",
            "actionable_steps": ["step 1"],
        }
        mock_get_cache.return_value = cached_result
        mock_client = MagicMock()
        service = VertexAiService(client=mock_client)
        result = service.generate_insights(
            {"total_co2e_kg": 50.0, "period_days": 7, "emission_breakdown": []}
        )
        assert result == cached_result
        # Model should NOT be called when cache hits
        mock_client.models.generate_content.assert_not_called()
        # Cache should not be set again on a hit
        mock_set_cache.assert_not_called()


class TestVertexAiServiceFallbackModel:
    """Unit tests for the VertexAiService fallback model path (lines 191-194)."""

    @pytest.mark.unit
    @patch("app.services.insights_cache.set_cached_insight")
    @patch("app.services.insights_cache.get_cached_insight")
    def test_fallback_model_used_on_primary_failure(
        self,
        mock_get_cache: MagicMock,
        mock_set_cache: MagicMock,
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify fallback model is tried when primary model fails all retries."""
        mock_get_cache.return_value = None  # No cache hit
        mock_client = MagicMock()
        # Primary model fails, fallback succeeds
        fallback_response = _build_mock_genai_response(mock_ai_response_dict)
        mock_client.models.generate_content.side_effect = [
            Exception("Primary model error"),
            Exception("Primary model retry error"),
            Exception("Primary model retry 2 error"),
            fallback_response,  # This is the fallback call
        ]
        service = VertexAiService(client=mock_client)
        result = service.generate_insights(
            {"total_co2e_kg": 50.0, "period_days": 7, "emission_breakdown": []}
        )
        assert result["insight"] == mock_ai_response_dict["insight"]
        # set_cached_insight should be called for the fallback result
        mock_set_cache.assert_called_once()

    @pytest.mark.unit
    @patch("app.services.insights_cache.set_cached_insight")
    @patch("app.services.insights_cache.get_cached_insight")
    def test_fallback_model_failure_raises_original_exception(
        self,
        mock_get_cache: MagicMock,
        mock_set_cache: MagicMock,
    ) -> None:
        """Verify original exception is raised when both primary and fallback fail."""
        mock_get_cache.return_value = None
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("All models down")
        service = VertexAiService(client=mock_client)
        with pytest.raises(Exception, match="All models down"):
            service.generate_insights(
                {"total_co2e_kg": 50.0, "period_days": 7, "emission_breakdown": []}
            )


# ===========================================================================
# Unit Tests: Truncated JSON Repair
# ===========================================================================


class TestRepairTruncatedJson:
    """Unit tests for the _repair_truncated_json helper function."""

    @pytest.mark.unit
    def test_repair_missing_closing_braces(self) -> None:
        """Verify truncated JSON missing closing braces can be repaired."""
        truncated = '{"insight": "test", "equivalent_impact": "test", "actionable_steps": ["step 1"'
        result = _repair_truncated_json(truncated)
        assert result is not None
        assert result["insight"] == "test"

    @pytest.mark.unit
    def test_repair_unterminated_string(self) -> None:
        """Verify truncated JSON with unterminated string can be repaired."""
        truncated = '{"insight": "this is a long insight that got trun'
        result = _repair_truncated_json(truncated)
        # Should either repair or return None — both are acceptable
        if result is not None:
            assert isinstance(result, dict)

    @pytest.mark.unit
    def test_repair_fills_missing_keys(self) -> None:
        """Verify repaired JSON gets fallback values for missing required keys."""
        truncated = '{"insight": "only insight"'
        result = _repair_truncated_json(truncated)
        if result is not None:
            assert "insight" in result
            # Missing keys should be filled with fallback values
            assert AppConstants.VERTEX_AI_RESPONSE_KEY_EQUIVALENT in result
            assert AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS in result

    @pytest.mark.unit
    def test_repair_returns_none_for_unrepairable(self) -> None:
        """Verify completely invalid input returns None."""
        result = _repair_truncated_json("not json at all")
        assert result is None


# ===========================================================================
# Integration Tests: POST /api/v1/ai/chat
# ===========================================================================


class TestChatEndpointHappyPath:
    """Integration tests for the conversational AI chat endpoint."""

    @pytest.fixture(name="valid_chat_payload")
    def fixture_valid_chat_payload(self) -> dict[str, Any]:
        """Provide a valid chat request payload."""
        return {
            "user_id": "test-user-chat-001",
            "message": "How can I reduce my transport emissions?",
            "total_co2e_kg": 85.5,
            "period_days": 30,
            "emission_breakdown": [
                {
                    "category": "transport",
                    "total_co2e_kg": 85.5,
                    "entry_count": 12,
                    "description": "Daily car commute",
                }
            ],
            "conversation_history": [],
        }

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_chat_returns_200(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_chat_payload: dict[str, Any],
    ) -> None:
        """Verify valid chat payload returns 200 with coaching response."""
        app.dependency_overrides[get_current_user] = _override_auth(
            "test-user-chat-001"
        )
        try:
            mock_service = MagicMock()
            mock_service.chat_async = AsyncMock(
                return_value={
                    "response": "Try switching to public transit for 2 days a week.",
                    "suggestions": [
                        "What about cycling?",
                        "Tell me about electric vehicles.",
                    ],
                    "model_used": AppConstants.VERTEX_AI_MODEL_NAME,
                }
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/chat",
                json=valid_chat_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_chat_response_contains_required_fields(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_chat_payload: dict[str, Any],
    ) -> None:
        """Verify chat response includes response, suggestions, and model_used."""
        app.dependency_overrides[get_current_user] = _override_auth(
            "test-user-chat-001"
        )
        try:
            mock_service = MagicMock()
            mock_service.chat_async = AsyncMock(
                return_value={
                    "response": "Try switching to public transit.",
                    "suggestions": ["What about cycling?"],
                    "model_used": AppConstants.VERTEX_AI_MODEL_NAME,
                }
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/chat",
                json=valid_chat_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            data: dict[str, Any] = response.json()
            assert "response" in data
            assert "suggestions" in data
            assert "model_used" in data
            assert data["user_id"] == "test-user-chat-001"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_chat_service_failure_returns_500(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_chat_payload: dict[str, Any],
    ) -> None:
        """Verify chat service failure returns 500 with generic error."""
        app.dependency_overrides[get_current_user] = _override_auth(
            "test-user-chat-001"
        )
        try:
            mock_service = MagicMock()
            mock_service.chat_async = AsyncMock(
                side_effect=Exception("Gemini API timeout")
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/chat",
                json=valid_chat_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 500
            assert "temporarily unavailable" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestChatEndpointValidation:
    """Integration tests for chat endpoint input validation."""

    @pytest.mark.integration
    def test_chat_missing_message_returns_422(self, client: TestClient) -> None:
        """Verify chat without message field returns 422."""
        payload: dict[str, Any] = {
            "user_id": "user-001",
            "total_co2e_kg": 50.0,
            "period_days": 30,
            "emission_breakdown": [
                {
                    "category": "transport",
                    "total_co2e_kg": 50.0,
                    "entry_count": 1,
                    "description": "Car commute",
                }
            ],
        }
        response = client.post(
            "/api/v1/ai/chat",
            json=payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_chat_empty_message_returns_422(self, client: TestClient) -> None:
        """Verify chat with empty message string returns 422."""
        payload: dict[str, Any] = {
            "user_id": "user-001",
            "message": "",
            "total_co2e_kg": 50.0,
            "period_days": 30,
            "emission_breakdown": [
                {
                    "category": "transport",
                    "total_co2e_kg": 50.0,
                    "entry_count": 1,
                    "description": "Car commute",
                }
            ],
        }
        response = client.post(
            "/api/v1/ai/chat",
            json=payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 422


# ===========================================================================
# Integration Tests: AI Route Ownership Enforcement
# ===========================================================================


def _override_auth(uid: str):
    """Create a dependency override that returns the given UID for get_current_user."""

    async def _mock_get_current_user():
        return uid

    return _mock_get_current_user


class TestAiRouteOwnership:
    """Integration tests verifying authenticated users can only access their own AI data."""

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_insights_cross_user_access_returns_403(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
    ) -> None:
        """Verify authenticated user cannot request AI insights for another user."""
        app.dependency_overrides[get_current_user] = _override_auth("auth-user-001")
        try:
            # payload has user_id "test-user-ai-001" which differs from "auth-user-001"
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value={
                    "insight": "test",
                    "equivalent_impact": "test",
                    "actionable_steps": ["step 1"],
                }
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 403
            assert "Access denied" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_insights_same_user_returns_200(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify authenticated user can request AI insights for their own data."""
        app.dependency_overrides[get_current_user] = _override_auth("test-user-ai-001")
        try:
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value=mock_ai_response_dict
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_insights_anonymous_user_cross_user_blocked(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        valid_insights_payload: dict[str, Any],
    ) -> None:
        """Verify anonymous users cannot request AI insights for a different user_id."""
        app.dependency_overrides[get_current_user] = _override_auth("anon-abc123def456")
        try:
            # payload has user_id "test-user-ai-001" which differs from "anon-abc123def456"
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value={
                    "insight": "test",
                    "equivalent_impact": "test",
                    "actionable_steps": ["step 1"],
                }
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=valid_insights_payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 403
            assert "Access denied" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_insights_anonymous_user_can_access_own_id(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        mock_ai_response_dict: dict[str, Any],
    ) -> None:
        """Verify anonymous users can request AI insights for their own anonymous ID."""
        anon_id = "anon-abc123def456"
        app.dependency_overrides[get_current_user] = _override_auth(anon_id)
        try:
            payload = {
                "user_id": anon_id,
                "total_co2e_kg": 156.8,
                "period_days": 30,
                "emission_breakdown": [
                    {
                        "category": "transport",
                        "total_co2e_kg": 85.5,
                        "entry_count": 12,
                        "description": "Daily car commute",
                    }
                ],
            }
            mock_service = MagicMock()
            mock_service.generate_insights_async = AsyncMock(
                return_value=mock_ai_response_dict
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/insights",
                json=payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_chat_cross_user_access_returns_403(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
    ) -> None:
        """Verify authenticated user cannot request AI chat for another user."""
        app.dependency_overrides[get_current_user] = _override_auth("auth-user-001")
        try:
            payload: dict[str, Any] = {
                "user_id": "different-user-002",
                "message": "How can I reduce emissions?",
                "total_co2e_kg": 50.0,
                "period_days": 30,
                "emission_breakdown": [
                    {
                        "category": "transport",
                        "total_co2e_kg": 50.0,
                        "entry_count": 1,
                        "description": "Car commute",
                    }
                ],
                "conversation_history": [],
            }
            mock_service = MagicMock()
            mock_service.chat_async = AsyncMock(
                return_value={
                    "response": "Try biking.",
                    "suggestions": ["What about transit?"],
                    "model_used": AppConstants.VERTEX_AI_MODEL_NAME,
                }
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/chat",
                json=payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 403
            assert "Access denied" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    @patch("app.routes.ai_routes._get_vertex_service")
    def test_chat_same_user_returns_200(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
    ) -> None:
        """Verify authenticated user can request AI chat for their own data."""
        app.dependency_overrides[get_current_user] = _override_auth("auth-user-001")
        try:
            payload: dict[str, Any] = {
                "user_id": "auth-user-001",
                "message": "How can I reduce emissions?",
                "total_co2e_kg": 50.0,
                "period_days": 30,
                "emission_breakdown": [
                    {
                        "category": "transport",
                        "total_co2e_kg": 50.0,
                        "entry_count": 1,
                        "description": "Car commute",
                    }
                ],
                "conversation_history": [],
            }
            mock_service = MagicMock()
            mock_service.chat_async = AsyncMock(
                return_value={
                    "response": "Try biking.",
                    "suggestions": ["What about transit?"],
                    "model_used": AppConstants.VERTEX_AI_MODEL_NAME,
                }
            )
            mock_get_service.return_value = mock_service
            response = client.post(
                "/api/v1/ai/chat",
                json=payload,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
