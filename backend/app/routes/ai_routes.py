"""AI insights route for generating sustainability recommendations via Vertex AI."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth import get_current_user

from app.constants import AppConstants
from app.schemas.ai_schemas import (
    ChatRequest,
    ChatResponse,
    InsightsRequest,
    InsightsResponse,
)
from app.services.vertex_service import VertexAiService

router: APIRouter = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def _get_vertex_service() -> VertexAiService:
    """Obtain a VertexAiService instance for AI operations.

    Returns:
        A configured VertexAiService instance.
    """
    return VertexAiService()


def _build_user_data_payload(payload: InsightsRequest) -> dict[str, Any]:
    """Convert the validated request payload into a dictionary for prompt generation.

    Args:
        payload: The validated InsightsRequest Pydantic model.

    Returns:
        A plain dictionary containing the user's emission summary data.
    """
    return {
        "user_id": payload.user_id,
        "total_co2e_kg": payload.total_co2e_kg,
        "period_days": payload.period_days,
        "emission_breakdown": [
            entry.model_dump() for entry in payload.emission_breakdown
        ],
    }


def _build_insights_response(
    user_id: str,
    ai_result: dict[str, Any],
) -> InsightsResponse:
    """Assemble the API response model from the AI-generated insights.

    Args:
        user_id: The requesting user's identifier.
        ai_result: Parsed dictionary from the Gemini model response.

    Returns:
        A fully populated InsightsResponse model.
    """
    return InsightsResponse(
        user_id=user_id,
        insight=ai_result[AppConstants.VERTEX_AI_RESPONSE_KEY_INSIGHT],
        equivalent_impact=ai_result[AppConstants.VERTEX_AI_RESPONSE_KEY_EQUIVALENT],
        actionable_steps=ai_result[AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS],
        model_used=AppConstants.VERTEX_AI_MODEL_NAME,
    )


def _build_error_response(exc: Exception) -> HTTPException:
    """Map service-layer exceptions to a clean HTTP 500 error response.

    Args:
        exc: The exception raised during AI service execution.

    Returns:
        An HTTPException with status 500 and descriptive detail message.
    """
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"AI service error: {exc}",
    )


@router.post(
    "/insights",
    response_model=InsightsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_insights(
    payload: InsightsRequest,
    authenticated_uid: str = Depends(get_current_user),
) -> InsightsResponse:
    """Generate AI-powered sustainability insights from the user's carbon ledger.

    Uses the async Gemini wrapper to avoid blocking the event loop.
    If a valid Firebase ID token is provided, the authenticated UID is available.

    Args:
        payload: Validated insights request with accumulated emission data.
        authenticated_uid: UID from Firebase ID token, or "anonymous" if none provided.

    Returns:
        AI-generated insights with actionable sustainability recommendations.

    Raises:
        HTTPException: 500 if the Vertex AI service call fails.
    """
    user_data: dict[str, Any] = _build_user_data_payload(payload)
    try:
        service: VertexAiService = _get_vertex_service()
        ai_result: dict[str, Any] = await service.generate_insights_async(user_data)
    except Exception as exc:
        raise _build_error_response(exc) from exc
    return _build_insights_response(payload.user_id, ai_result)


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    payload: ChatRequest,
    authenticated_uid: str = Depends(get_current_user),
) -> ChatResponse:
    """Multi-turn conversational AI coaching endpoint.

    Enables follow-up questions about the user's carbon footprint data,
    allowing natural conversation with the Sustainability Coach.

    Args:
        payload: Validated chat request with message, user data, and conversation history.
        authenticated_uid: UID from Firebase ID token, or "anonymous" if none provided.

    Returns:
        AI-generated coaching response with suggested follow-up questions.

    Raises:
        HTTPException: 500 if the Vertex AI service call fails.
    """
    user_data: dict[str, Any] = {
        "user_id": payload.user_id,
        "total_co2e_kg": payload.total_co2e_kg,
        "period_days": payload.period_days,
        "emission_breakdown": [
            entry.model_dump() for entry in payload.emission_breakdown
        ],
    }
    conversation_history: list[dict[str, str]] = [
        msg.model_dump() for msg in payload.conversation_history
    ]
    try:
        service: VertexAiService = _get_vertex_service()
        chat_result: dict[str, Any] = await service.chat_async(
            user_data, conversation_history, payload.message
        )
    except Exception as exc:
        raise _build_error_response(exc) from exc

    return ChatResponse(
        user_id=payload.user_id,
        response=chat_result["response"],
        suggestions=chat_result.get("suggestions", []),
        model_used=chat_result["model_used"],
    )
