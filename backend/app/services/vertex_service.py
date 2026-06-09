"""Vertex AI service for generating sustainability insights via the Gemini model.

Orchestrates calls to the Gemini 2.5 Flash model with structured JSON output
enforcement and a Sustainability Coach system instruction.
Supports both single-shot insights and multi-turn conversational coaching.
Includes caching, retry logic, and fallback model support.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any

from google import genai
from google.genai import types

from app.constants import AppConstants

logger = logging.getLogger(__name__)

FALLBACK_MODEL = "gemini-2.0-flash"
MAX_RETRIES = 2


def _build_response_schema() -> dict[str, Any]:
    """Build the JSON schema for structured Gemini output enforcement.

    Returns:
        A dictionary defining the expected JSON response structure with
        insight, equivalent_impact, and actionable_steps fields.
    """
    return {
        "type": "object",
        "properties": {
            AppConstants.VERTEX_AI_RESPONSE_KEY_INSIGHT: {"type": "string"},
            AppConstants.VERTEX_AI_RESPONSE_KEY_EQUIVALENT: {"type": "string"},
            AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS: {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            AppConstants.VERTEX_AI_RESPONSE_KEY_INSIGHT,
            AppConstants.VERTEX_AI_RESPONSE_KEY_EQUIVALENT,
            AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS,
        ],
    }


def _build_generation_config() -> types.GenerateContentConfig:
    """Build the Gemini generation configuration with structured output.

    Returns:
        A GenerateContentConfig with temperature, max tokens, JSON mime type,
        system instruction, and response schema enforcement.
    """
    return types.GenerateContentConfig(
        temperature=AppConstants.VERTEX_AI_TEMPERATURE,
        max_output_tokens=AppConstants.VERTEX_AI_MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
        response_schema=_build_response_schema(),
        system_instruction=AppConstants.VERTEX_AI_SYSTEM_INSTRUCTION,
    )


def _build_chat_generation_config() -> types.GenerateContentConfig:
    """Build the Gemini generation configuration for conversational chat.

    Unlike insights, chat uses freeform JSON output without a strict schema
    to allow flexible conversational responses.

    Returns:
        A GenerateContentConfig with temperature, max tokens, JSON mime type,
        and system instruction (no response_schema).
    """
    return types.GenerateContentConfig(
        temperature=AppConstants.VERTEX_AI_TEMPERATURE,
        max_output_tokens=AppConstants.VERTEX_AI_MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
        system_instruction=AppConstants.VERTEX_AI_SYSTEM_INSTRUCTION,
    )


def _format_prompt(user_data: dict[str, Any]) -> str:
    """Format the user's carbon ledger data into a structured prompt.

    Args:
        user_data: Dictionary containing the user's emission summary data.

    Returns:
        A formatted prompt string for the Gemini model.
    """
    return (
        f"Analyze this carbon footprint data and provide sustainability advice:\n\n"
        f"Total CO2e: {user_data['total_co2e_kg']} kg\n"
        f"Period: {user_data['period_days']} days\n"
        f"Breakdown: {json.dumps(user_data['emission_breakdown'], indent=2)}\n\n"
        f"Provide exactly {AppConstants.VERTEX_AI_ACTIONABLE_STEPS_COUNT} actionable steps."
    )


def _format_chat_prompt(
    user_data: dict[str, Any],
    conversation_history: list[dict[str, str]],
    user_message: str,
) -> str:
    """Format a conversational coaching prompt with history context.

    Args:
        user_data: The user's current emission summary data.
        conversation_history: Previous messages in the conversation.
        user_message: The latest user question or follow-up.

    Returns:
        A formatted prompt string for multi-turn Gemini interaction.
    """
    history_lines = "\n".join(
        f"  {msg['role'].capitalize()}: {msg['content']}"
        for msg in conversation_history[
            -10:
        ]  # Keep last 10 messages for context window
    )
    return (
        f"You are a Sustainability Coach. Continue this conversation naturally.\n\n"
        f"User's Carbon Data:\n"
        f"  Total CO2e: {user_data.get('total_co2e_kg', 0)} kg\n"
        f"  Period: {user_data.get('period_days', 1)} days\n"
        f"  Breakdown: {json.dumps(user_data.get('emission_breakdown', []), indent=2)}\n\n"
        f"Conversation so far:\n{history_lines}\n\n"
        f"User's latest message: {user_message}\n\n"
        f"Respond with a JSON object containing:\n"
        f'  "response": your detailed, encouraging coaching response (string),\n'
        f'  "suggestions": array of 1-3 follow-up questions the user might ask (strings).\n\n'
        f"Be specific, reference their actual data, and be encouraging."
    )


def _parse_model_response(response_text: str) -> dict[str, Any]:
    """Parse the raw model response text into a validated dictionary.

    Handles common Gemini response issues:
    - Truncated JSON (unterminated strings) from max_output_tokens limits
    - Markdown code fences wrapping JSON
    - Missing required keys in partial responses

    Args:
        response_text: The JSON string returned by the Gemini model.

    Returns:
        A parsed dictionary containing insight, equivalent_impact, and actionable_steps.

    Raises:
        ValueError: If the response text cannot be parsed as valid JSON.
    """
    cleaned = response_text.strip()

    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as original_err:
        # Attempt to repair truncated JSON by closing open structures
        repaired = _repair_truncated_json(cleaned)
        if repaired is not None:
            logger.warning(
                "Repaired truncated Gemini JSON response: %s -> success",
                str(original_err),
            )
            return repaired
        raise ValueError(
            f"Failed to parse Gemini response as JSON: {original_err}"
        ) from original_err


def _repair_truncated_json(text: str) -> dict[str, Any] | None:
    """Attempt to repair a truncated JSON string from Gemini.

    Common truncation patterns:
    - Unterminated string values (missing closing quote)
    - Unclosed arrays/objects (missing ] or })
    - Partial entries at the end of an array

    Args:
        text: The malformed JSON string.

    Returns:
        A repaired dictionary, or None if repair is not possible.
    """
    # Try progressively closing open structures
    for suffix in ["]}", "}]", '"}]}', '"}]}', '"\n}]}']:
        try:
            result = json.loads(text + suffix)
            if isinstance(result, dict):
                # Fill missing required keys with fallback values
                result.setdefault(
                    AppConstants.VERTEX_AI_RESPONSE_KEY_INSIGHT,
                    "Analysis complete. See actionable steps below.",
                )
                result.setdefault(
                    AppConstants.VERTEX_AI_RESPONSE_KEY_EQUIVALENT,
                    "Impact data is being processed.",
                )
                result.setdefault(
                    AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS,
                    ["Try logging more activities for detailed recommendations."],
                )
                # Filter out empty/partial strings from truncated steps
                if AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS in result:
                    steps = result[AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS]
                    result[AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS] = [
                        s for s in steps if isinstance(s, str) and len(s.strip()) > 5
                    ]
                    if not result[AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS]:
                        result[AppConstants.VERTEX_AI_RESPONSE_KEY_STEPS] = [
                            "Try logging more activities for detailed recommendations."
                        ]
                return result
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _extract_response_text(response: Any) -> str:
    """Extract the text content from a Gemini API response object.

    Args:
        response: The GenerateContentResponse from the Gemini API.

    Returns:
        The raw text string from the model's response.

    Raises:
        ValueError: If the response contains no text content.
    """
    text: str | None = response.text
    if text is None:
        raise ValueError("Gemini response contained no text content")
    return text


class VertexAiService:
    """Service class for orchestrating Vertex AI Gemini model interactions.

    Initializes the Gemini client and provides methods to generate
    sustainability insights from user carbon footprint data.

    Attributes:
        _client: The Google GenAI client instance.
        _model_name: The Gemini model identifier to use for generation.
        _config: The generation configuration with structured output enforcement.
    """

    def __init__(self, client: genai.Client | None = None) -> None:
        """Initialize the VertexAiService with an optional pre-configured client.

        Uses Vertex AI (GCP billing) instead of Google AI Studio.
        Falls back to Google AI if GOOGLE_API_KEY is set and no client is provided.

        Args:
            client: An optional pre-configured GenAI client.
                    If ``None``, a new client is created with Vertex AI credentials.
        """
        import os

        if client is not None:
            self._client: genai.Client = client
        elif os.environ.get("GOOGLE_API_KEY"):
            # Fallback: use Google AI SDK if API key is explicitly set
            self._client = genai.Client()
        else:
            # Use Vertex AI with GCP service account credentials
            self._client = genai.Client(
                vertexai=True,
                project=AppConstants.VERTEX_AI_PROJECT_ID,
                location=AppConstants.VERTEX_AI_LOCATION,
            )
        self._model_name: str = AppConstants.VERTEX_AI_MODEL_NAME
        self._config: types.GenerateContentConfig = _build_generation_config()

    def generate_insights(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """Generate sustainability insights from the user's carbon footprint data.

        Checks cache first, then retries with primary model, falls back to
        a secondary model if the primary is unavailable.

        Args:
            user_data: Dictionary containing aggregated emission data.

        Returns:
            A dictionary with insight, equivalent_impact, and actionable_steps.

        Raises:
            Exception: If all model calls fail.
        """
        from app.services.insights_cache import get_cached_insight, set_cached_insight

        # Check cache first
        cached = get_cached_insight(user_data)
        if cached is not None:
            return cached

        # Try primary model with retries
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                prompt: str = _format_prompt(user_data)
                response = self._call_model(prompt)
                response_text: str = _extract_response_text(response)
                result = _parse_model_response(response_text)
                # Cache successful result
                set_cached_insight(user_data, result)
                return result
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Model call attempt %d/%d failed: %s",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    exc,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(1 * (attempt + 1))  # Simple backoff

        # Fallback to secondary model
        try:
            logger.info("Trying fallback model: %s", FALLBACK_MODEL)
            prompt: str = _format_prompt(user_data)
            response = self._client.models.generate_content(
                model=FALLBACK_MODEL,
                contents=prompt,
                config=self._config,
            )
            response_text: str = _extract_response_text(response)
            result = _parse_model_response(response_text)
            set_cached_insight(user_data, result)
            return result
        except Exception as fallback_exc:
            logger.error("Fallback model also failed: %s", fallback_exc)
            raise last_exc or fallback_exc

    async def generate_insights_async(
        self, user_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Async variant of generate_insights that does not block the event loop.

        Delegates the synchronous Gemini call to a thread pool executor,
        allowing the asyncio event loop to serve other requests concurrently.

        Args:
            user_data: Dictionary containing aggregated emission data.

        Returns:
            A dictionary with keys ``insight``, ``equivalent_impact``,
            and ``actionable_steps``.
        """
        return await asyncio.to_thread(self.generate_insights, user_data)

    async def chat_async(
        self,
        user_data: dict[str, Any],
        conversation_history: list[dict[str, str]],
        user_message: str,
    ) -> dict[str, Any]:
        """Generate a conversational AI response for multi-turn coaching.

        Args:
            user_data: The user's current carbon footprint summary.
            conversation_history: Previous messages as list of
                ``{'role': 'user'|'model', 'content': str}`` dicts.
            user_message: The latest user question or follow-up.

        Returns:
            A dictionary with ``response``, ``suggestions``, and ``model_used``.
        """
        return await asyncio.to_thread(
            self._chat_sync, user_data, conversation_history, user_message
        )

    def _chat_sync(
        self,
        user_data: dict[str, Any],
        conversation_history: list[dict[str, str]],
        user_message: str,
    ) -> dict[str, Any]:
        """Synchronous implementation of the conversational chat."""
        chat_prompt = _format_chat_prompt(user_data, conversation_history, user_message)
        chat_config = _build_chat_generation_config()
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=chat_prompt,
            config=chat_config,
        )
        response_text = _extract_response_text(response)
        try:
            parsed = json.loads(response_text.strip())
            return {
                "response": parsed.get("response", response_text.strip()),
                "suggestions": parsed.get("suggestions", []),
                "model_used": self._model_name,
            }
        except json.JSONDecodeError:
            return {
                "response": response_text.strip(),
                "suggestions": [],
                "model_used": self._model_name,
            }

    def _call_model(self, prompt: str) -> Any:
        """Execute the Gemini model call with the configured generation settings.

        Args:
            prompt: The formatted user prompt to send to the model.

        Returns:
            The raw GenerateContentResponse from the Gemini API.

        Raises:
            google.api_core.exceptions.ResourceExhausted: If the API quota is exceeded.
            TimeoutError: If the request times out.
        """
        return self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=self._config,
        )
