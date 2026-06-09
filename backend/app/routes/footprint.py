"""Carbon footprint logging route with Pydantic validation and Firestore persistence."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.middleware.auth import get_current_user
from app.schemas import CarbonCalculationRequest, CarbonCalculationResponse
from app.services.firebase_service import FirebaseService
from app.utils.entry_processor import process_all_entries, sum_total_emissions

router: APIRouter = APIRouter(prefix="/api/v1/footprint", tags=["footprint"])


def _get_firebase_service() -> FirebaseService:
    """Obtain a FirebaseService instance for database operations.

    Returns:
        A configured FirebaseService instance.
    """
    return FirebaseService()


def _serialize_results(results: list) -> list[dict[str, object]]:
    """Convert a list of EmissionResult models to serializable dictionaries.

    Args:
        results: List of EmissionResult Pydantic models.

    Returns:
        List of plain dictionaries suitable for Firestore storage.
    """
    return [result.model_dump() for result in results]


@router.post(
    "/log",
    response_model=CarbonCalculationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_footprint(
    payload: CarbonCalculationRequest,
    authenticated_uid: str = Depends(get_current_user),
) -> CarbonCalculationResponse:
    """Ingest, calculate, and persist carbon footprint activity entries.

    If a valid Firebase ID token is provided in the Authorization header,
    the authenticated UID overrides the user_id in the payload for security.

    Args:
        payload: Validated carbon calculation request with activity entries.
        authenticated_uid: UID from Firebase ID token, or "anonymous" if none provided.

    Returns:
        A response containing individual results, total CO2e, and Firestore document ID.

    Raises:
        HTTPException: 500 if the database write fails.
    """
    # Use authenticated UID if available, otherwise use the payload's user_id
    effective_user_id = (
        authenticated_uid if authenticated_uid != "anonymous" else payload.user_id
    )
    results = process_all_entries(payload.entries)
    total_co2e_kg: float = sum_total_emissions(results)
    document_id: str = _write_to_firestore(
        effective_user_id, payload, total_co2e_kg, results
    )
    return _build_response(effective_user_id, total_co2e_kg, results, document_id)


@router.get(
    "/history/{user_id}",
    status_code=status.HTTP_200_OK,
)
async def get_footprint_history(
    user_id: str,
    period_days: int = Query(
        default=30, ge=1, le=365, description="Lookback period in days"
    ),
    authenticated_uid: str = Depends(get_current_user),
) -> dict:
    """Retrieve a user's carbon footprint history from Firestore.

    If a valid Firebase ID token is provided, ensures the authenticated
    user can only access their own data.

    Args:
        user_id: The unique identifier of the user.
        period_days: Number of days to look back (default 30, max 365).
        authenticated_uid: UID from Firebase ID token, or "anonymous" if none provided.

    Returns:
        A dictionary containing the user's carbon log entries and count.

    Raises:
        HTTPException: 500 if the database read fails.
    """
    effective_user_id = (
        authenticated_uid if authenticated_uid != "anonymous" else user_id
    )
    try:
        service: FirebaseService = _get_firebase_service()
        logs = service.get_user_logs(effective_user_id, period_days)
        return {
            "user_id": effective_user_id,
            "logs": logs,
            "count": len(logs),
            "period_days": period_days,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Database read failed: {exc}"
        ) from exc


@router.get(
    "/summary/{user_id}",
    status_code=status.HTTP_200_OK,
)
async def get_footprint_summary(
    user_id: str,
    period_days: int = Query(
        default=30, ge=1, le=365, description="Lookback period in days"
    ),
    authenticated_uid: str = Depends(get_current_user),
) -> dict:
    """Retrieve an aggregated carbon footprint summary for a user.

    If a valid Firebase ID token is provided, ensures the authenticated
    user can only access their own data.

    Args:
        user_id: The unique identifier of the user.
        period_days: Number of days to look back (default 30, max 365).
        authenticated_uid: UID from Firebase ID token, or "anonymous" if none provided.

    Returns:
        A dictionary containing the total CO2e, entry count, and category breakdown.

    Raises:
        HTTPException: 500 if the database read fails.
    """
    effective_user_id = (
        authenticated_uid if authenticated_uid != "anonymous" else user_id
    )
    try:
        service: FirebaseService = _get_firebase_service()
        logs = service.get_user_logs(effective_user_id, period_days)
        total_co2e = round(sum(log.get("total_co2e_kg", 0) for log in logs), 4)
        category_map: dict[str, float] = {}
        for log in logs:
            for result in log.get("results", []):
                cat = result.get("category", "unknown")
                category_map[cat] = category_map.get(cat, 0) + result.get("co2e_kg", 0)
        breakdown = [
            {"category": cat, "total_co2e_kg": round(co2e, 4)}
            for cat, co2e in category_map.items()
        ]
        return {
            "user_id": effective_user_id,
            "period_days": period_days,
            "total_co2e_kg": total_co2e,
            "entry_count": len(logs),
            "category_breakdown": breakdown,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Database read failed: {exc}"
        ) from exc


def _write_to_firestore(
    effective_user_id: str,
    payload: CarbonCalculationRequest,
    total_co2e_kg: float,
    results: list,
) -> str:
    """Delegate the Firestore write and handle database errors.

    Args:
        effective_user_id: The resolved user ID (authenticated or from payload).
        payload: The original validated request payload.
        total_co2e_kg: Aggregated emissions total.
        results: List of EmissionResult models.

    Returns:
        The Firestore document ID of the persisted record.

    Raises:
        HTTPException: 500 with detail message if the write operation fails.
    """
    try:
        service: FirebaseService = _get_firebase_service()
        return service.write_carbon_log(
            effective_user_id,
            total_co2e_kg,
            _serialize_results(results),
            payload.calculation_date,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Database write failed: {exc}"
        ) from exc


def _build_response(
    effective_user_id: str,
    total_co2e_kg: float,
    results: list,
    document_id: str,
) -> CarbonCalculationResponse:
    """Assemble the API response model from computed data.

    Args:
        effective_user_id: The resolved user ID (authenticated or from payload).
        total_co2e_kg: Total emissions in kg CO2e.
        results: List of per-entry EmissionResult models.
        document_id: Firestore document ID of the persisted log.

    Returns:
        A fully populated CarbonCalculationResponse.
    """
    return CarbonCalculationResponse(
        user_id=effective_user_id,
        total_co2e_kg=total_co2e_kg,
        entry_count=len(results),
        results=results,
        document_id=document_id,
    )
