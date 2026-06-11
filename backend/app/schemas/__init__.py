"""Pydantic validation schemas for the Carbon Footprint Awareness Platform.

Re-exports all schema models from sub-modules for clean imports:
    from app.schemas import CarbonCalculationRequest
"""

from app.schemas.ai_schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmissionSummaryEntry,
    InsightsRequest,
    InsightsResponse,
)

# ---------------------------------------------------------------------------
# Carbon footprint schemas (defined here for backward compatibility)
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TransportMode(str, Enum):
    """Allowed transportation modes for carbon footprint entries."""

    CAR = "car"
    BUS = "bus"
    TRAIN = "train"
    BICYCLE = "bicycle"
    WALKING = "walking"
    FLIGHT = "flight"


class EnergySource(str, Enum):
    """Allowed energy source types for carbon footprint entries."""

    ELECTRICITY = "electricity"
    NATURAL_GAS = "natural_gas"
    SOLAR = "solar"
    WIND = "wind"


class DietType(str, Enum):
    """Allowed dietary classification types for carbon footprint entries."""

    MEAT_HEAVY = "meat_heavy"
    AVERAGE = "average"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"


class ConsumptionItemType(str, Enum):
    """Allowed consumption item types for carbon footprint entries.

    Matches the frontend dropdown values exactly. Backend falls back to
    ``general`` emission factor for unknown values, maintaining forward
    compatibility if new types are added to the frontend first.
    """

    CLOTHING = "clothing"
    ELECTRONICS = "electronics"
    FURNITURE = "furniture"
    GENERAL = "general"


class ActivityCategory(str, Enum):
    """Top-level activity categories for a carbon footprint entry."""

    TRANSPORT = "transport"
    ENERGY = "energy"
    FOOD = "food"
    CONSUMPTION = "consumption"


class CarbonUnit(str, Enum):
    """Supported CO2 measurement units."""

    KG_CO2 = "kg_co2"
    G_CO2 = "g_co2"
    TONNES_CO2 = "tonnes_co2"


class TransportMetrics(BaseModel):
    """Transportation-specific measurement data."""

    mode: TransportMode
    distance_km: float = Field(
        ge=0.1, le=50000, description="Distance in km (minimum 0.1)"
    )


class EnergyMetrics(BaseModel):
    """Energy consumption-specific measurement data."""

    source: EnergySource
    consumption_kwh: float = Field(ge=0, le=1000000)


class DietMetrics(BaseModel):
    """Diet-specific measurement data."""

    diet_type: DietType
    days: int = Field(gt=0, le=365)


class ConsumptionMetrics(BaseModel):
    """Consumption-specific measurement data."""

    item_type: ConsumptionItemType = Field(
        description="Type of consumption item (clothing, electronics, furniture, general)"
    )
    quantity: int = Field(gt=0, le=1000)


class ActivityEntry(BaseModel):
    """A single carbon footprint activity entry with category-specific metrics."""

    category: ActivityCategory
    description: str = Field(min_length=1, max_length=500)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?")
    transport: TransportMetrics | None = None
    energy: EnergyMetrics | None = None
    diet: DietMetrics | None = None
    consumption: ConsumptionMetrics | None = None

    @field_validator("date")
    @classmethod
    def validate_date_not_future(cls, v: str) -> str:
        """Reject dates more than 1 day ahead of UTC to account for timezone offsets.

        Users submit local time via datetime-local inputs, which can be up to
        UTC+14 hours ahead of the server's UTC clock. Comparing only the date
        portion with a +1 day buffer ensures no legitimate 'today' entry is
        rejected regardless of the user's timezone.
        """
        try:
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Invalid date format") from None
        max_allowed = datetime.now(timezone.utc).date() + timedelta(days=1)
        if parsed.date() > max_allowed:
            raise ValueError("Date cannot be in the future")
        return v


class CarbonCalculationRequest(BaseModel):
    """Inbound payload for logging carbon footprint entries with category-specific metrics."""

    user_id: str = Field(min_length=1, max_length=128)
    entries: list[ActivityEntry] = Field(min_length=1, max_length=100)
    calculation_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?")

    @field_validator("calculation_date")
    @classmethod
    def validate_calculation_date_not_future(cls, v: str) -> str:
        """Reject calculation dates more than 1 day ahead of UTC.

        Uses the same timezone-aware logic as ActivityEntry.validate_date_not_future
        to avoid rejecting legitimate requests from users in UTC+ timezones.
        """
        try:
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Invalid date format") from None
        max_allowed = datetime.now(timezone.utc).date() + timedelta(days=1)
        if parsed.date() > max_allowed:
            raise ValueError("Calculation date cannot be in the future")
        return v


class EmissionResult(BaseModel):
    """Calculated emission output for a single activity entry."""

    category: str
    description: str
    co2e_kg: float
    date: str


class CarbonCalculationResponse(BaseModel):
    """Outbound response payload after processing a carbon calculation request."""

    user_id: str
    total_co2e_kg: float
    entry_count: int
    results: list[EmissionResult]
    document_id: str


__all__ = [
    "ActivityCategory",
    "ActivityEntry",
    "CarbonCalculationRequest",
    "CarbonCalculationResponse",
    "CarbonUnit",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ConsumptionItemType",
    "ConsumptionMetrics",
    "DietMetrics",
    "DietType",
    "EmissionResult",
    "EmissionSummaryEntry",
    "EnergyMetrics",
    "EnergySource",
    "InsightsRequest",
    "InsightsResponse",
    "TransportMetrics",
    "TransportMode",
]
