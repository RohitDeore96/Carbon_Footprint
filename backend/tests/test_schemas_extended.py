"""Extended tests for schemas — covers future date validators in ActivityEntry and CarbonCalculationRequest."""

from datetime import datetime, timezone, timedelta

import pytest
from pydantic import ValidationError

from app.schemas import ActivityEntry, CarbonCalculationRequest


class TestActivityEntryFutureDateValidation:
    """Tests for ActivityEntry._validate_not_future_date."""

    def test_future_date_raises_validation_error(self) -> None:
        """Verify a future date raises a ValidationError."""
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        with pytest.raises(ValidationError, match="future"):
            ActivityEntry(
                category="transport",
                description="test",
                date=future_date,
                transport={"mode": "car", "distance_km": 10},
            )

    def test_past_date_passes_validation(self) -> None:
        """Verify a past date passes validation."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        entry = ActivityEntry(
            category="transport",
            description="test past",
            date=past_date,
            transport={"mode": "car", "distance_km": 10},
        )
        assert entry.date == past_date

    def test_current_date_passes_validation(self) -> None:
        """Verify the current date/time passes validation."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        entry = ActivityEntry(
            category="energy",
            description="test now",
            date=now,
            energy={"source": "electricity", "consumption_kwh": 100},
        )
        assert entry.date == now


class TestCarbonCalculationRequestFutureDateValidation:
    """Tests for CarbonCalculationRequest._validate_calc_date_not_future."""

    def test_future_calculation_date_raises_validation_error(self) -> None:
        """Verify a future calculation_date raises a ValidationError."""
        future_date = (datetime.now(timezone.utc) + timedelta(days=10)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        with pytest.raises(ValidationError, match="future"):
            CarbonCalculationRequest(
                user_id="user1",
                entries=[
                    {
                        "category": "transport",
                        "description": "test",
                        "date": "2024-01-01T10:00",
                        "transport": {"mode": "car", "distance_km": 10},
                    }
                ],
                calculation_date=future_date,
            )

    def test_past_calculation_date_passes(self) -> None:
        """Verify a past calculation_date passes validation."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        req = CarbonCalculationRequest(
            user_id="user1",
            entries=[
                {
                    "category": "food",
                    "description": "test food",
                    "date": "2024-01-01T10:00",
                    "diet": {"diet_type": "vegan", "days": 5},
                }
            ],
            calculation_date=past_date,
        )
        assert req.calculation_date == past_date
