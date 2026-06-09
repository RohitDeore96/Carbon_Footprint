"""Pure utility functions for computing CO2e emissions from activity entries.

All calculation functions are single-responsibility, branch-free, and use
emission factors from the centralized constants layer.
"""

from app.constants import AppConstants


def calculate_transport_emission(mode: str, distance_km: float) -> float:
    """Compute CO2e in kg for a given transport mode and distance.

    Args:
        mode: The transport mode key (must exist in emission factors).
        distance_km: Distance traveled in kilometers.

    Returns:
        CO2e emissions in kilograms.
    """
    factor: float = AppConstants.EMISSION_FACTORS_TRANSPORT_KG_PER_KM[mode]
    return round(factor * distance_km, 4)


def calculate_energy_emission(source: str, consumption_kwh: float) -> float:
    """Compute CO2e in kg for a given energy source and consumption.

    Args:
        source: The energy source key (must exist in emission factors).
        consumption_kwh: Energy consumed in kilowatt-hours.

    Returns:
        CO2e emissions in kilograms.
    """
    factor: float = AppConstants.EMISSION_FACTORS_ENERGY_KG_PER_KWH[source]
    return round(factor * consumption_kwh, 4)


def calculate_diet_emission(diet_type: str, days: int) -> float:
    """Compute CO2e in kg for a given diet type over a number of days.

    Args:
        diet_type: The dietary classification key (must exist in emission factors).
        days: Number of days for the dietary period.

    Returns:
        CO2e emissions in kilograms.
    """
    factor: float = AppConstants.EMISSION_FACTORS_DIET_KG_PER_DAY[diet_type]
    return round(factor * days, 4)


def calculate_consumption_emission(item_type: str, quantity: int) -> float:
    """Compute CO2e in kg for a consumption activity based on item type and quantity.

    Args:
        item_type: The type of consumed item (must exist in consumption emission factors).
        quantity: Number of items purchased or consumed.

    Returns:
        CO2e emissions in kilograms.
    """
    factor: float = AppConstants.EMISSION_FACTORS_CONSUMPTION_KG_PER_ITEM.get(
        item_type, AppConstants.EMISSION_FACTORS_CONSUMPTION_KG_PER_ITEM["general"]
    )
    return round(factor * quantity, 4)


def calculate_generic_emission(value: float, unit: str) -> float:
    """Convert a raw emission value to kilograms CO2e using unit conversion factors.

    Args:
        value: The raw emission value in its original unit.
        unit: The unit of measurement (must exist in unit conversion factors).

    Returns:
        CO2e emissions normalized to kilograms.
    """
    multiplier: float = AppConstants.UNIT_CONVERSION_TO_KG[unit]
    return round(value * multiplier, 4)
