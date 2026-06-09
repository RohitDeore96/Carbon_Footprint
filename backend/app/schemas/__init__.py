"""Pydantic validation schemas mirroring frontend Zod definitions for carbon footprint payloads."""

from enum import Enum

from pydantic import BaseModel, Field


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
    distance_km: float = Field(gt=0, le=50000)


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

    item_type: str = Field(min_length=1, max_length=100)
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


class CarbonCalculationRequest(BaseModel):
    """Inbound payload for logging carbon footprint entries with category-specific metrics."""

    user_id: str = Field(min_length=1, max_length=128)
    entries: list[ActivityEntry] = Field(min_length=1, max_length=100)
    calculation_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?")


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
