"""AI insights route for generating sustainability recommendations via Vertex AI."""

import logging
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

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/v1/ai", tags=["ai"])

# Rate limiting: The RateLimiterMiddleware (app/main.py) enforces a global
# per-IP limit of 60 requests/minute with a stricter 10 req/min for AI
# endpoints. This protects all AI endpoints from abuse and cost amplification.

# Module-level singleton — created once per process, not per request
_vertex_service_instance: VertexAiService | None = None


def _get_vertex_service() -> VertexAiService:
    """Return a cached VertexAiService singleton for AI operations.

    Uses module-level caching to avoid creating a new GenAI client
    on every request.

    Returns:
        A configured VertexAiService instance.
    """
    global _vertex_service_instance
    if _vertex_service_instance is None:
        _vertex_service_instance = VertexAiService()
    return _vertex_service_instance


def _verify_ai_user_access(authenticated_uid: str, requested_user_id: str) -> str:
    """Verify the authenticated user has access to the requested user's AI data.

    Users can only request AI insights for their own data. Anonymous IDs
    (anon-*) are treated as unauthenticated — they can access the requested
    user_id since they have no verified identity to compare against.

    Args:
        authenticated_uid: UID from Firebase ID token, or generated anonymous ID.
        requested_user_id: The user_id from the request payload.

    Returns:
        The effective user_id to use for the AI operation.

    Raises:
        HTTPException: 403 if the user tries to request AI insights for
            another user's data.
    """
    if authenticated_uid.startswith("anon-"):
        return requested_user_id
    if authenticated_uid != requested_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: users can only request AI insights for their own data",
        )
    return authenticated_uid


def _build_user_data_payload(
    payload: InsightsRequest | ChatRequest,
) -> dict[str, Any]:
    """Convert the validated request payload into a dictionary for prompt generation.

    Args:
        payload: The validated InsightsRequest or ChatRequest Pydantic model.

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

    Logs the full exception server-side but returns a generic message
    to the client to avoid leaking internal details.

    Args:
        exc: The exception raised during AI service execution.

    Returns:
        An HTTPException with status 500 and a generic detail message.
    """
    logger.error("AI service call failed: %s", exc)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="AI service temporarily unavailable. Please try again later.",
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
        authenticated_uid: UID from Firebase ID token, or generated anonymous ID if none provided.

    Returns:
        AI-generated insights with actionable sustainability recommendations.

    Raises:
        HTTPException: 500 if the Vertex AI service call fails.
    """
    _verify_ai_user_access(authenticated_uid, payload.user_id)
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
        authenticated_uid: UID from Firebase ID token, or generated anonymous ID if none provided.

    Returns:
        AI-generated coaching response with suggested follow-up questions.

    Raises:
        HTTPException: 500 if the Vertex AI service call fails.
    """
    _verify_ai_user_access(authenticated_uid, payload.user_id)
    user_data: dict[str, Any] = _build_user_data_payload(payload)
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
