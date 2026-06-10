"""Pure utility functions for computing CO2e emissions from activity entries.

All calculation functions are single-responsibility, branch-free, and use
emission factors from the centralized constants layer.

Each function validates its numeric inputs and raises ValueError for
negative values, preventing nonsensical emission calculations.
"""

import logging

from app.constants import AppConstants

logger = logging.getLogger(__name__)


def calculate_transport_emission(mode: str, distance_km: float) -> float:
    """Compute CO2e in kg for a given transport mode and distance.

    Args:
        mode: The transport mode key (must exist in emission factors).
        distance_km: Distance traveled in kilometers (must be non-negative).

    Returns:
        CO2e emissions in kilograms.

    Raises:
        ValueError: If distance_km is negative.
        KeyError: If mode is not a recognized transport mode.
    """
    if distance_km < 0:
        raise ValueError(f"distance_km must be non-negative, got {distance_km}")
    factor: float = AppConstants.EMISSION_FACTORS_TRANSPORT_KG_PER_KM[mode]
    return round(factor * distance_km, 4)


def calculate_energy_emission(source: str, consumption_kwh: float) -> float:
    """Compute CO2e in kg for a given energy source and consumption.

    Args:
        source: The energy source key (must exist in emission factors).
        consumption_kwh: Energy consumed in kilowatt-hours (must be non-negative).

    Returns:
        CO2e emissions in kilograms.

    Raises:
        ValueError: If consumption_kwh is negative.
        KeyError: If source is not a recognized energy source.
    """
    if consumption_kwh < 0:
        raise ValueError(f"consumption_kwh must be non-negative, got {consumption_kwh}")
    factor: float = AppConstants.EMISSION_FACTORS_ENERGY_KG_PER_KWH[source]
    return round(factor * consumption_kwh, 4)


def calculate_diet_emission(diet_type: str, days: int) -> float:
    """Compute CO2e in kg for a given diet type over a number of days.

    Args:
        diet_type: The dietary classification key (must exist in emission factors).
        days: Number of days for the dietary period (must be non-negative).

    Returns:
        CO2e emissions in kilograms.

    Raises:
        ValueError: If days is negative.
        KeyError: If diet_type is not a recognized diet type.
    """
    if days < 0:
        raise ValueError(f"days must be non-negative, got {days}")
    factor: float = AppConstants.EMISSION_FACTORS_DIET_KG_PER_DAY[diet_type]
    return round(factor * days, 4)


def calculate_consumption_emission(item_type: str, quantity: int) -> float:
    """Compute CO2e in kg for a consumption activity based on item type and quantity.

    Args:
        item_type: The type of consumed item. If not recognized, falls back
            to the "general" emission factor with a warning.
        quantity: Number of items purchased or consumed (must be non-negative).

    Returns:
        CO2e emissions in kilograms.

    Raises:
        ValueError: If quantity is negative.
    """
    if quantity < 0:
        raise ValueError(f"quantity must be non-negative, got {quantity}")
    if item_type not in AppConstants.EMISSION_FACTORS_CONSUMPTION_KG_PER_ITEM:
        logger.warning(
            "Unknown consumption item_type '%s'; falling back to 'general' "
            "emission factor. Known types: %s",
            item_type,
            list(AppConstants.EMISSION_FACTORS_CONSUMPTION_KG_PER_ITEM.keys()),
        )
    factor: float = AppConstants.EMISSION_FACTORS_CONSUMPTION_KG_PER_ITEM.get(
        item_type, AppConstants.EMISSION_FACTORS_CONSUMPTION_KG_PER_ITEM["general"]
    )
    return round(factor * quantity, 4)


def calculate_generic_emission(value: float, unit: str) -> float:
    """Convert a raw emission value to kilograms CO2e using unit conversion factors.

    Args:
        value: The raw emission value in its original unit (must be non-negative).
        unit: The unit of measurement (must exist in unit conversion factors).

    Returns:
        CO2e emissions normalized to kilograms.

    Raises:
        ValueError: If value is negative.
        KeyError: If unit is not a recognized conversion unit.
    """
    if value < 0:
        raise ValueError(f"value must be non-negative, got {value}")
    multiplier: float = AppConstants.UNIT_CONVERSION_TO_KG[unit]
    return round(value * multiplier, 4)
