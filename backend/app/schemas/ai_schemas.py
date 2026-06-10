"""Pydantic schemas for Vertex AI sustainability insights request and response payloads."""

from pydantic import BaseModel, Field


class EmissionSummaryEntry(BaseModel):
    """A single emission summary entry from the user's carbon ledger."""

    category: str = Field(min_length=1, max_length=100)
    total_co2e_kg: float = Field(ge=0)
    entry_count: int = Field(ge=1)
    description: str = Field(min_length=1, max_length=500)


class InsightsRequest(BaseModel):
    """Inbound payload for requesting AI-powered sustainability insights.

    Contains the user's accumulated carbon ledger data aggregated by category.
    """

    user_id: str = Field(min_length=1, max_length=128)
    total_co2e_kg: float = Field(ge=0)
    period_days: int = Field(ge=1, le=365)
    emission_breakdown: list[EmissionSummaryEntry] = Field(min_length=1, max_length=50)


class InsightsResponse(BaseModel):
    """Outbound payload containing AI-generated sustainability insights."""

    user_id: str
    insight: str
    equivalent_impact: str
    actionable_steps: list[str]
    model_used: str


class ChatMessage(BaseModel):
    """A single message in a conversation thread."""

    role: str = Field(pattern=r"^(user|model)$")
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    """Inbound payload for multi-turn conversational AI coaching."""

    user_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=2000)
    total_co2e_kg: float = Field(ge=0)
    period_days: int = Field(ge=1, le=365)
    emission_breakdown: list[EmissionSummaryEntry] = Field(min_length=1, max_length=50)
    conversation_history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    """Outbound payload for a conversational AI coaching response."""

    user_id: str
    response: str
    suggestions: list[str]
    model_used: str
