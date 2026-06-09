"""Entry processing pipeline that orchestrates calculation for a list of activity entries.

Dispatches each entry to the appropriate single-responsibility calculator based on
its category, producing a flat list of emission results.
"""

from app.schemas import ActivityEntry, EmissionResult
from app.utils.carbon_calculator import (
    calculate_consumption_emission,
    calculate_diet_emission,
    calculate_energy_emission,
    calculate_transport_emission,
)


def _process_transport_entry(entry: ActivityEntry) -> float:
    """Compute CO2e for a transport activity entry.

    Args:
        entry: An activity entry with transport metrics populated.

    Returns:
        CO2e emissions in kilograms, or 0.0 if transport metrics are absent.
    """
    metrics = entry.transport
    return (
        calculate_transport_emission(metrics.mode.value, metrics.distance_km)
        if metrics
        else 0.0
    )


def _process_energy_entry(entry: ActivityEntry) -> float:
    """Compute CO2e for an energy activity entry.

    Args:
        entry: An activity entry with energy metrics populated.

    Returns:
        CO2e emissions in kilograms, or 0.0 if energy metrics are absent.
    """
    metrics = entry.energy
    return (
        calculate_energy_emission(metrics.source.value, metrics.consumption_kwh)
        if metrics
        else 0.0
    )


def _process_food_entry(entry: ActivityEntry) -> float:
    """Compute CO2e for a food/diet activity entry.

    Args:
        entry: An activity entry with diet metrics populated.

    Returns:
        CO2e emissions in kilograms, or 0.0 if diet metrics are absent.
    """
    metrics = entry.diet
    return (
        calculate_diet_emission(metrics.diet_type.value, metrics.days)
        if metrics
        else 0.0
    )


def _process_consumption_entry(entry: ActivityEntry) -> float:
    """Compute CO2e for a consumption activity entry.

    Args:
        entry: An activity entry with consumption metrics populated.

    Returns:
        CO2e emissions in kilograms, or 0.0 if consumption metrics are absent.
    """
    metrics = entry.consumption
    return (
        calculate_consumption_emission(metrics.item_type, metrics.quantity)
        if metrics
        else 0.0
    )


_PROCESSOR_DISPATCH: dict[str, object] = {
    "transport": _process_transport_entry,
    "energy": _process_energy_entry,
    "food": _process_food_entry,
    "consumption": _process_consumption_entry,
}


def compute_entry_emission(entry: ActivityEntry) -> EmissionResult:
    """Compute the CO2e emission for a single activity entry via category dispatch.

    Args:
        entry: A validated activity entry with category-specific metrics.

    Returns:
        An EmissionResult containing the category, description, CO2e value, and date.
    """
    category_key: str = entry.category.value
    processor = _PROCESSOR_DISPATCH.get(category_key)
    co2e_kg: float = processor(entry) if callable(processor) else 0.0
    return _build_emission_result(entry, co2e_kg)


def _build_emission_result(entry: ActivityEntry, co2e_kg: float) -> EmissionResult:
    """Construct an EmissionResult from an entry and its calculated CO2e.

    Args:
        entry: The source activity entry.
        co2e_kg: Calculated CO2e in kilograms.

    Returns:
        A fully populated EmissionResult model.
    """
    return EmissionResult(
        category=entry.category.value,
        description=entry.description,
        co2e_kg=co2e_kg,
        date=entry.date,
    )


def process_all_entries(entries: list[ActivityEntry]) -> list[EmissionResult]:
    """Process a batch of activity entries and return their emission results.

    Args:
        entries: A list of validated activity entries.

    Returns:
        A list of EmissionResult objects, one per input entry.
    """
    return [compute_entry_emission(entry) for entry in entries]


def sum_total_emissions(results: list[EmissionResult]) -> float:
    """Sum the total CO2e across all emission results.

    Args:
        results: A list of computed emission results.

    Returns:
        The total CO2e emissions in kilograms, rounded to 4 decimal places.
    """
    return round(sum(result.co2e_kg for result in results), 4)
