"""Comprehensive tests for the carbon calculation engine and footprint logging endpoint.

Tests cover:
- Pure calculation utility functions (unit tests)
- Entry processor pipeline (unit tests)
- POST /api/v1/footprint/log happy path (201 Created, integration)
- GET /api/v1/footprint/history/{user_id} (200 OK, integration)
- GET /api/v1/footprint/summary/{user_id} (200 OK, integration)
- Pydantic validation failures (422 Unprocessable Entity, integration)
- Simulated database timeout errors (500 Internal Server Error, integration)
- Auth-enforced access control (403 Forbidden for cross-user access)

All Firestore interactions are fully mocked via unittest.mock.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_current_user
from app.routes.footprint import get_firebase_service
from app.schemas import (
    ActivityEntry,
    ConsumptionMetrics,
    DietMetrics,
    EnergyMetrics,
    TransportMetrics,
)
from app.utils.carbon_calculator import (
    calculate_consumption_emission,
    calculate_diet_emission,
    calculate_energy_emission,
    calculate_generic_emission,
    calculate_transport_emission,
)
from app.utils.entry_processor import (
    compute_entry_emission,
    process_all_entries,
    sum_total_emissions,
)


@pytest.fixture(name="client")
def fixture_test_client() -> TestClient:
    """Provide a TestClient instance bound to the application."""
    return TestClient(app)


@pytest.fixture(name="valid_transport_payload")
def fixture_valid_transport_payload() -> dict:
    """Provide a valid transport-category carbon calculation request payload."""
    return {
        "user_id": "test-user-001",
        "calculation_date": "2026-06-08T12:00:00",
        "entries": [
            {
                "category": "transport",
                "description": "Daily commute by car",
                "date": "2026-06-08T08:00:00",
                "transport": {"mode": "car", "distance_km": 25.0},
            }
        ],
    }


@pytest.fixture(name="valid_energy_payload")
def fixture_valid_energy_payload() -> dict:
    """Provide a valid energy-category carbon calculation request payload."""
    return {
        "user_id": "test-user-002",
        "calculation_date": "2026-06-08T12:00:00",
        "entries": [
            {
                "category": "energy",
                "description": "Monthly electricity usage",
                "date": "2026-06-08T08:00:00",
                "energy": {"source": "electricity", "consumption_kwh": 350.0},
            }
        ],
    }


@pytest.fixture(name="valid_diet_payload")
def fixture_valid_diet_payload() -> dict:
    """Provide a valid food-category carbon calculation request payload."""
    return {
        "user_id": "test-user-003",
        "calculation_date": "2026-06-08T12:00:00",
        "entries": [
            {
                "category": "food",
                "description": "Weekly vegan diet",
                "date": "2026-06-08T08:00:00",
                "diet": {"diet_type": "vegan", "days": 7},
            }
        ],
    }


@pytest.fixture(name="multi_entry_payload")
def fixture_multi_entry_payload() -> dict:
    """Provide a payload with multiple entry categories."""
    return {
        "user_id": "test-user-004",
        "calculation_date": "2026-06-08T12:00:00",
        "entries": [
            {
                "category": "transport",
                "description": "Flight to conference",
                "date": "2026-06-08T08:00:00",
                "transport": {"mode": "flight", "distance_km": 1500.0},
            },
            {
                "category": "energy",
                "description": "Home gas heating",
                "date": "2026-06-08T08:00:00",
                "energy": {"source": "natural_gas", "consumption_kwh": 200.0},
            },
            {
                "category": "food",
                "description": "Vegetarian week",
                "date": "2026-06-08T08:00:00",
                "diet": {"diet_type": "vegetarian", "days": 7},
            },
        ],
    }


def _override_auth(uid: str):
    """Create a dependency override that returns the given UID for get_current_user."""

    async def _mock_get_current_user():
        return uid

    return _mock_get_current_user


def _mock_firestore_write() -> MagicMock:
    """Create a mock that simulates a successful Firestore document write."""
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "mock-document-id-12345"
    mock_collection = MagicMock()
    mock_collection.add.return_value = (None, mock_doc_ref)
    mock_client = MagicMock()
    mock_client.collection.return_value = mock_collection
    return mock_client


def _override_firebase_service(mock_service: MagicMock):
    """Create a dependency override for get_firebase_service that returns mock_service."""

    def _mock_get_firebase_service():
        return mock_service

    return _mock_get_firebase_service


# ===========================================================================
# Unit Tests: Pure Calculation Functions
# ===========================================================================


class TestTransportCalculation:
    """Unit tests for transport emission calculations."""

    @pytest.mark.unit
    def test_car_emission_calculation(self) -> None:
        """Verify car emission uses correct factor (0.21 kg/km)."""
        result: float = calculate_transport_emission("car", 100.0)
        assert result == 21.0

    @pytest.mark.unit
    def test_bus_emission_calculation(self) -> None:
        """Verify bus emission uses correct factor (0.089 kg/km)."""
        result: float = calculate_transport_emission("bus", 50.0)
        assert result == 4.45

    @pytest.mark.unit
    def test_train_emission_calculation(self) -> None:
        """Verify train emission uses correct factor (0.041 kg/km)."""
        result: float = calculate_transport_emission("train", 200.0)
        assert result == 8.2

    @pytest.mark.unit
    def test_bicycle_zero_emission(self) -> None:
        """Verify bicycle produces zero emissions."""
        result: float = calculate_transport_emission("bicycle", 100.0)
        assert result == 0.0

    @pytest.mark.unit
    def test_walking_zero_emission(self) -> None:
        """Verify walking produces zero emissions."""
        result: float = calculate_transport_emission("walking", 5.0)
        assert result == 0.0

    @pytest.mark.unit
    def test_flight_emission_calculation(self) -> None:
        """Verify flight emission uses correct factor (0.255 kg/km)."""
        result: float = calculate_transport_emission("flight", 1000.0)
        assert result == 255.0

    @pytest.mark.unit
    def test_negative_distance_raises_value_error(self) -> None:
        """Verify negative distance_km raises ValueError."""
        with pytest.raises(ValueError, match="distance_km must be non-negative"):
            calculate_transport_emission("car", -10.0)


class TestEnergyCalculation:
    """Unit tests for energy emission calculations."""

    @pytest.mark.unit
    def test_electricity_emission(self) -> None:
        """Verify electricity emission uses correct factor (0.233 kg/kWh)."""
        result: float = calculate_energy_emission("electricity", 100.0)
        assert result == 23.3

    @pytest.mark.unit
    def test_natural_gas_emission(self) -> None:
        """Verify natural gas emission uses correct factor (0.184 kg/kWh)."""
        result: float = calculate_energy_emission("natural_gas", 500.0)
        assert result == 92.0

    @pytest.mark.unit
    def test_solar_zero_emission(self) -> None:
        """Verify solar energy produces zero emissions."""
        result: float = calculate_energy_emission("solar", 1000.0)
        assert result == 0.0

    @pytest.mark.unit
    def test_wind_zero_emission(self) -> None:
        """Verify wind energy produces zero emissions."""
        result: float = calculate_energy_emission("wind", 500.0)
        assert result == 0.0

    @pytest.mark.unit
    def test_negative_consumption_raises_value_error(self) -> None:
        """Verify negative consumption_kwh raises ValueError."""
        with pytest.raises(ValueError, match="consumption_kwh must be non-negative"):
            calculate_energy_emission("electricity", -5.0)


class TestDietCalculation:
    """Unit tests for diet emission calculations."""

    @pytest.mark.unit
    def test_meat_heavy_emission(self) -> None:
        """Verify meat-heavy diet uses correct factor (7.19 kg/day)."""
        result: float = calculate_diet_emission("meat_heavy", 7)
        assert result == 50.33

    @pytest.mark.unit
    def test_vegan_emission(self) -> None:
        """Verify vegan diet uses correct factor (2.89 kg/day)."""
        result: float = calculate_diet_emission("vegan", 30)
        assert result == 86.7

    @pytest.mark.unit
    def test_vegetarian_emission(self) -> None:
        """Verify vegetarian diet uses correct factor (3.81 kg/day)."""
        result: float = calculate_diet_emission("vegetarian", 7)
        assert result == 26.67

    @pytest.mark.unit
    def test_average_emission(self) -> None:
        """Verify average diet uses correct factor (5.63 kg/day)."""
        result: float = calculate_diet_emission("average", 1)
        assert result == 5.63

    @pytest.mark.unit
    def test_negative_days_raises_value_error(self) -> None:
        """Verify negative days raises ValueError."""
        with pytest.raises(ValueError, match="days must be non-negative"):
            calculate_diet_emission("vegan", -1)


class TestGenericEmission:
    """Unit tests for unit conversion calculations."""

    @pytest.mark.unit
    def test_kg_passthrough(self) -> None:
        """Verify kg_co2 unit has 1:1 conversion."""
        result: float = calculate_generic_emission(10.0, "kg_co2")
        assert result == 10.0

    @pytest.mark.unit
    def test_grams_to_kg(self) -> None:
        """Verify g_co2 converts to kg correctly (factor 0.001)."""
        result: float = calculate_generic_emission(5000.0, "g_co2")
        assert result == 5.0

    @pytest.mark.unit
    def test_tonnes_to_kg(self) -> None:
        """Verify tonnes_co2 converts to kg correctly (factor 1000)."""
        result: float = calculate_generic_emission(2.5, "tonnes_co2")
        assert result == 2500.0

    @pytest.mark.unit
    def test_negative_value_raises_value_error(self) -> None:
        """Verify negative value raises ValueError."""
        with pytest.raises(ValueError, match="value must be non-negative"):
            calculate_generic_emission(-10.0, "kg_co2")


# ===========================================================================
# Unit Tests: Entry Processor
# ===========================================================================


class TestEntryProcessor:
    """Unit tests for the entry processing pipeline."""

    @pytest.mark.unit
    def test_compute_transport_entry(self) -> None:
        """Verify transport entry produces correct EmissionResult."""
        entry = ActivityEntry(
            category="transport",
            description="Car trip",
            date="2026-06-08T08:00:00",
            transport=TransportMetrics(mode="car", distance_km=10.0),
        )
        result = compute_entry_emission(entry)
        assert result.co2e_kg == 2.1
        assert result.category == "transport"

    @pytest.mark.unit
    def test_compute_energy_entry(self) -> None:
        """Verify energy entry produces correct EmissionResult."""
        entry = ActivityEntry(
            category="energy",
            description="Electricity",
            date="2026-06-08T08:00:00",
            energy=EnergyMetrics(source="electricity", consumption_kwh=100.0),
        )
        result = compute_entry_emission(entry)
        assert result.co2e_kg == 23.3
        assert result.category == "energy"

    @pytest.mark.unit
    def test_compute_food_entry(self) -> None:
        """Verify food entry produces correct EmissionResult."""
        entry = ActivityEntry(
            category="food",
            description="Vegan day",
            date="2026-06-08T08:00:00",
            diet=DietMetrics(diet_type="vegan", days=1),
        )
        result = compute_entry_emission(entry)
        assert result.co2e_kg == 2.89
        assert result.category == "food"

    @pytest.mark.unit
    def test_process_all_entries_count(self) -> None:
        """Verify process_all_entries returns one result per input entry."""
        entries = [
            ActivityEntry(
                category="transport",
                description="Bus ride",
                date="2026-06-08T08:00:00",
                transport=TransportMetrics(mode="bus", distance_km=20.0),
            ),
            ActivityEntry(
                category="energy",
                description="Solar",
                date="2026-06-08T08:00:00",
                energy=EnergyMetrics(source="solar", consumption_kwh=500.0),
            ),
        ]
        results = process_all_entries(entries)
        assert len(results) == 2

    @pytest.mark.unit
    def test_sum_total_emissions(self) -> None:
        """Verify sum_total_emissions aggregates correctly."""
        entries = [
            ActivityEntry(
                category="transport",
                description="Car",
                date="2026-06-08T08:00:00",
                transport=TransportMetrics(mode="car", distance_km=100.0),
            ),
            ActivityEntry(
                category="food",
                description="Average diet",
                date="2026-06-08T08:00:00",
                diet=DietMetrics(diet_type="average", days=1),
            ),
        ]
        results = process_all_entries(entries)
        total: float = sum_total_emissions(results)
        assert total == 26.63

    @pytest.mark.unit
    def test_consumption_category_returns_correct_emission(self) -> None:
        """Verify consumption category with metrics returns correct CO2e."""
        entry = ActivityEntry(
            category="consumption",
            description="Bought a laptop",
            date="2026-06-08T08:00:00",
            consumption=ConsumptionMetrics(item_type="electronics", quantity=1),
        )
        result = compute_entry_emission(entry)
        assert result.co2e_kg == 100.0
        assert result.category == "consumption"

    @pytest.mark.unit
    def test_consumption_category_without_metrics_returns_zero(self) -> None:
        """Verify consumption category with no metrics returns 0.0."""
        entry = ActivityEntry(
            category="consumption",
            description="Bought something",
            date="2026-06-08T08:00:00",
        )
        result = compute_entry_emission(entry)
        assert result.co2e_kg == 0.0


# ===========================================================================
# Integration Tests: POST /api/v1/footprint/log
# ===========================================================================


class TestFootprintEndpointHappyPath:
    """Integration tests for successful footprint logging requests."""

    @pytest.mark.integration
    def test_transport_entry_returns_201(
        self,
        client: TestClient,
        valid_transport_payload: dict,
    ) -> None:
        """Verify transport entry returns 201 with correct response structure."""
        mock_service = MagicMock()
        mock_service.write_carbon_log.return_value = "mock-doc-id"
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.post(
                "/api/v1/footprint/log", json=valid_transport_payload
            )
            assert response.status_code == 201
            data: dict = response.json()
            # user_id in response is now the authenticated UID (anon-...) not payload.user_id
            assert data["entry_count"] == 1
            assert data["total_co2e_kg"] == 5.25
            assert data["document_id"] == "mock-doc-id"
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_energy_entry_returns_201(
        self,
        client: TestClient,
        valid_energy_payload: dict,
    ) -> None:
        """Verify energy entry returns 201 with correct emission calculation."""
        mock_service = MagicMock()
        mock_service.write_carbon_log.return_value = "mock-doc-energy"
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.post("/api/v1/footprint/log", json=valid_energy_payload)
            assert response.status_code == 201
            data: dict = response.json()
            assert data["total_co2e_kg"] == 81.55
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_diet_entry_returns_201(
        self,
        client: TestClient,
        valid_diet_payload: dict,
    ) -> None:
        """Verify diet entry returns 201 with correct emission calculation."""
        mock_service = MagicMock()
        mock_service.write_carbon_log.return_value = "mock-doc-diet"
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.post("/api/v1/footprint/log", json=valid_diet_payload)
            assert response.status_code == 201
            data: dict = response.json()
            assert data["total_co2e_kg"] == 20.23
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_multi_entry_returns_201(
        self,
        client: TestClient,
        multi_entry_payload: dict,
    ) -> None:
        """Verify multi-category payload returns 201 with aggregated total."""
        mock_service = MagicMock()
        mock_service.write_carbon_log.return_value = "mock-doc-multi"
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.post("/api/v1/footprint/log", json=multi_entry_payload)
            assert response.status_code == 201
            data: dict = response.json()
            assert data["entry_count"] == 3
            assert len(data["results"]) == 3
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_authenticated_uid_overrides_payload_user_id(
        self,
        client: TestClient,
        valid_transport_payload: dict,
    ) -> None:
        """Verify authenticated UID always overrides the payload user_id for security."""
        app.dependency_overrides[get_current_user] = _override_auth("auth-user-999")
        mock_service = MagicMock()
        mock_service.write_carbon_log.return_value = "mock-doc-verify"
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.post(
                "/api/v1/footprint/log", json=valid_transport_payload
            )
            assert response.status_code == 201
            data: dict = response.json()
            # The response user_id must be the authenticated UID, not the payload user_id
            assert data["user_id"] == "auth-user-999"
            mock_service.write_carbon_log.assert_called_once()
            call_args = mock_service.write_carbon_log.call_args
            assert call_args[0][0] == "auth-user-999"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_firebase_service, None)


# ===========================================================================
# Integration Tests: Validation Failures (422)
# ===========================================================================


class TestFootprintEndpointValidation:
    """Integration tests for Pydantic validation rejection scenarios."""

    @pytest.mark.integration
    def test_empty_entries_returns_422(self, client: TestClient) -> None:
        """Verify empty entries list triggers 422 validation error."""
        payload: dict = {
            "user_id": "user-001",
            "calculation_date": "2026-06-08T12:00:00",
            "entries": [],
        }
        response = client.post("/api/v1/footprint/log", json=payload)
        assert response.status_code == 422

    @pytest.mark.integration
    def test_missing_user_id_returns_422(self, client: TestClient) -> None:
        """Verify missing user_id triggers 422 validation error."""
        payload: dict = {
            "calculation_date": "2026-06-08T12:00:00",
            "entries": [
                {
                    "category": "transport",
                    "description": "Car ride",
                    "date": "2026-06-08T08:00:00",
                    "transport": {"mode": "car", "distance_km": 10.0},
                }
            ],
        }
        response = client.post("/api/v1/footprint/log", json=payload)
        assert response.status_code == 422

    @pytest.mark.integration
    def test_invalid_category_returns_422(self, client: TestClient) -> None:
        """Verify invalid category value triggers 422 validation error."""
        payload: dict = {
            "user_id": "user-001",
            "calculation_date": "2026-06-08T12:00:00",
            "entries": [
                {
                    "category": "invalid_category",
                    "description": "Test",
                    "date": "2026-06-08T08:00:00",
                }
            ],
        }
        response = client.post("/api/v1/footprint/log", json=payload)
        assert response.status_code == 422

    @pytest.mark.integration
    def test_negative_distance_returns_422(self, client: TestClient) -> None:
        """Verify negative distance_km triggers 422 validation error."""
        payload: dict = {
            "user_id": "user-001",
            "calculation_date": "2026-06-08T12:00:00",
            "entries": [
                {
                    "category": "transport",
                    "description": "Invalid distance",
                    "date": "2026-06-08T08:00:00",
                    "transport": {"mode": "car", "distance_km": -10.0},
                }
            ],
        }
        response = client.post("/api/v1/footprint/log", json=payload)
        assert response.status_code == 422

    @pytest.mark.integration
    def test_empty_description_returns_422(self, client: TestClient) -> None:
        """Verify empty description string triggers 422 validation error."""
        payload: dict = {
            "user_id": "user-001",
            "calculation_date": "2026-06-08T12:00:00",
            "entries": [
                {
                    "category": "transport",
                    "description": "",
                    "date": "2026-06-08T08:00:00",
                    "transport": {"mode": "car", "distance_km": 10.0},
                }
            ],
        }
        response = client.post("/api/v1/footprint/log", json=payload)
        assert response.status_code == 422

    @pytest.mark.integration
    def test_exceeds_max_entries_returns_422(self, client: TestClient) -> None:
        """Verify more than 100 entries triggers 422 validation error."""
        entries = [
            {
                "category": "transport",
                "description": f"Entry {i}",
                "date": "2026-06-08T08:00:00",
                "transport": {"mode": "car", "distance_km": 1.0},
            }
            for i in range(101)
        ]
        payload: dict = {
            "user_id": "user-001",
            "calculation_date": "2026-06-08T12:00:00",
            "entries": entries,
        }
        response = client.post("/api/v1/footprint/log", json=payload)
        assert response.status_code == 422


# ===========================================================================
# Integration Tests: Database Error Simulation (500)
# ===========================================================================


class TestFootprintEndpointDatabaseError:
    """Integration tests simulating Firestore database failures."""

    @pytest.mark.integration
    def test_database_timeout_returns_500(
        self,
        client: TestClient,
        valid_transport_payload: dict,
    ) -> None:
        """Verify simulated database timeout returns 500 with error detail."""
        mock_service = MagicMock()
        mock_service.write_carbon_log.side_effect = TimeoutError(
            "Firestore connection timed out"
        )
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.post(
                "/api/v1/footprint/log", json=valid_transport_payload
            )
            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_database_generic_error_returns_500(
        self,
        client: TestClient,
        valid_transport_payload: dict,
    ) -> None:
        """Verify generic database exception returns 500 with error detail."""
        mock_service = MagicMock()
        mock_service.write_carbon_log.side_effect = RuntimeError(
            "Unexpected Firestore error"
        )
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.post(
                "/api/v1/footprint/log", json=valid_transport_payload
            )
            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_database_permission_error_returns_500(
        self,
        client: TestClient,
        valid_transport_payload: dict,
    ) -> None:
        """Verify permission denied error returns 500 with error detail."""
        mock_service = MagicMock()
        mock_service.write_carbon_log.side_effect = PermissionError(
            "Firestore permission denied"
        )
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.post(
                "/api/v1/footprint/log", json=valid_transport_payload
            )
            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)


# ===========================================================================
# Unit Tests: Consumption Calculation
# ===========================================================================


class TestConsumptionCalculation:
    """Unit tests for consumption emission calculations."""

    @pytest.mark.unit
    def test_clothing_emission(self) -> None:
        """Verify clothing uses correct factor (15.0 kg/item)."""
        result: float = calculate_consumption_emission("clothing", 2)
        assert result == 30.0

    @pytest.mark.unit
    def test_electronics_emission(self) -> None:
        """Verify electronics uses correct factor (100.0 kg/item)."""
        result: float = calculate_consumption_emission("electronics", 1)
        assert result == 100.0

    @pytest.mark.unit
    def test_furniture_emission(self) -> None:
        """Verify furniture uses correct factor (50.0 kg/item)."""
        result: float = calculate_consumption_emission("furniture", 3)
        assert result == 150.0

    @pytest.mark.unit
    def test_general_fallback_emission(self) -> None:
        """Verify general uses correct factor (10.0 kg/item)."""
        result: float = calculate_consumption_emission("general", 5)
        assert result == 50.0

    @pytest.mark.unit
    def test_unknown_type_falls_back_to_general(self) -> None:
        """Verify unknown item type falls back to the general emission factor."""
        result: float = calculate_consumption_emission("books", 2)
        assert result == 20.0

    @pytest.mark.unit
    def test_negative_quantity_raises_value_error(self) -> None:
        """Verify negative quantity raises ValueError."""
        with pytest.raises(ValueError, match="quantity must be non-negative"):
            calculate_consumption_emission("clothing", -1)


# ===========================================================================
# Integration Tests: GET /api/v1/footprint/history/{user_id}
# ===========================================================================


class TestFootprintHistoryEndpoint:
    """Integration tests for the footprint history retrieval endpoint."""

    @pytest.mark.integration
    def test_history_returns_200_with_auth(self, client: TestClient) -> None:
        """Verify history endpoint returns 200 with log entries for authenticated user."""
        app.dependency_overrides[get_current_user] = _override_auth("user-001")
        mock_service = MagicMock()
        mock_service.get_user_logs.return_value = [
            {
                "user_id": "user-001",
                "total_co2e_kg": 5.25,
                "results": [{"category": "transport", "co2e_kg": 5.25}],
                "created_at": "2026-06-08T12:00:00+00:00",
            }
        ]
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.get("/api/v1/footprint/history/user-001")
            assert response.status_code == 200
            data: dict = response.json()
            assert data["user_id"] == "user-001"
            assert data["count"] == 1
            assert data["period_days"] == 30
            assert len(data["logs"]) == 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_history_with_custom_period(self, client: TestClient) -> None:
        """Verify history endpoint accepts period_days query parameter."""
        app.dependency_overrides[get_current_user] = _override_auth("user-001")
        mock_service = MagicMock()
        mock_service.get_user_logs.return_value = []
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.get("/api/v1/footprint/history/user-001?period_days=7")
            assert response.status_code == 200
            mock_service.get_user_logs.assert_called_once_with("user-001", 7)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_history_without_auth_allows_anonymous_access(
        self, client: TestClient
    ) -> None:
        """Verify anonymous (no auth) users can access history — anon IDs bypass ownership check."""
        mock_service = MagicMock()
        mock_service.get_user_logs.return_value = []
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.get("/api/v1/footprint/history/user-001")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_history_cross_user_access_returns_403(self, client: TestClient) -> None:
        """Verify authenticated user cannot access another user's history."""
        app.dependency_overrides[get_current_user] = _override_auth("auth-user-001")
        try:
            response = client.get("/api/v1/footprint/history/different-user-002")
            assert response.status_code == 403
            assert "Access denied" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.integration
    def test_history_database_error_returns_500(self, client: TestClient) -> None:
        """Verify database error during history retrieval returns 500."""
        app.dependency_overrides[get_current_user] = _override_auth("user-001")
        mock_service = MagicMock()
        mock_service.get_user_logs.side_effect = RuntimeError("DB error")
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.get("/api/v1/footprint/history/user-001")
            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_firebase_service, None)


# ===========================================================================
# Integration Tests: GET /api/v1/footprint/summary/{user_id}
# ===========================================================================


class TestFootprintSummaryEndpoint:
    """Integration tests for the footprint summary aggregation endpoint."""

    @pytest.mark.integration
    def test_summary_returns_200(self, client: TestClient) -> None:
        """Verify summary endpoint returns 200 with aggregated data."""
        app.dependency_overrides[get_current_user] = _override_auth("user-001")
        mock_service = MagicMock()
        mock_service.get_user_logs.return_value = [
            {
                "user_id": "user-001",
                "total_co2e_kg": 5.25,
                "results": [
                    {"category": "transport", "co2e_kg": 5.25, "description": "Car"}
                ],
                "created_at": "2026-06-08T12:00:00+00:00",
            },
            {
                "user_id": "user-001",
                "total_co2e_kg": 23.3,
                "results": [
                    {
                        "category": "energy",
                        "co2e_kg": 23.3,
                        "description": "Electricity",
                    }
                ],
                "created_at": "2026-06-07T12:00:00+00:00",
            },
        ]
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.get("/api/v1/footprint/summary/user-001")
            assert response.status_code == 200
            data: dict = response.json()
            assert data["user_id"] == "user-001"
            assert data["total_co2e_kg"] == 28.55
            assert data["entry_count"] == 2
            assert len(data["category_breakdown"]) == 2
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_summary_empty_logs(self, client: TestClient) -> None:
        """Verify summary returns zeros for user with no logs."""
        app.dependency_overrides[get_current_user] = _override_auth("user-001")
        mock_service = MagicMock()
        mock_service.get_user_logs.return_value = []
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.get("/api/v1/footprint/summary/user-001")
            assert response.status_code == 200
            data: dict = response.json()
            assert data["total_co2e_kg"] == 0.0
            assert data["entry_count"] == 0
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_summary_without_auth_allows_anonymous_access(
        self, client: TestClient
    ) -> None:
        """Verify anonymous (no auth) users can access summary — anon IDs bypass ownership check."""
        mock_service = MagicMock()
        mock_service.get_user_logs.return_value = []
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.get("/api/v1/footprint/summary/user-001")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_firebase_service, None)

    @pytest.mark.integration
    def test_summary_database_error_returns_500(self, client: TestClient) -> None:
        """Verify database error during summary retrieval returns 500."""
        app.dependency_overrides[get_current_user] = _override_auth("user-001")
        mock_service = MagicMock()
        mock_service.get_user_logs.side_effect = RuntimeError("DB error")
        app.dependency_overrides[get_firebase_service] = _override_firebase_service(
            mock_service
        )
        try:
            response = client.get("/api/v1/footprint/summary/user-001")
            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_firebase_service, None)
