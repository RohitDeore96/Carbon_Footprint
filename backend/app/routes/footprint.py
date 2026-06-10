"""Carbon footprint logging route with Pydantic validation and Firestore persistence."""

import asyncio
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.middleware.auth import get_current_user, verify_user_access
from app.schemas import (
    CarbonCalculationRequest,
    CarbonCalculationResponse,
    EmissionResult,
)
from app.services.firebase_service import FirebaseService
from app.utils.entry_processor import process_all_entries, sum_total_emissions
from app.utils.error_logging import log_error

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/v1/footprint", tags=["footprint"])


_firebase_service_instance: FirebaseService | None = None


def get_firebase_service() -> FirebaseService:
    """FastAPI dependency that provides a singleton FirebaseService instance.

    Returns the same FirebaseService across all requests within a process.
    The Firestore client internally shares a gRPC channel, so reusing
    the wrapper avoids unnecessary object allocation and GC pressure.

    Returns:
        A configured FirebaseService instance.
    """
    global _firebase_service_instance
    if _firebase_service_instance is None:
        _firebase_service_instance = FirebaseService()
    return _firebase_service_instance


def _serialize_results(results: list[EmissionResult]) -> list[dict[str, object]]:
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
    service: FirebaseService = Depends(get_firebase_service),
) -> CarbonCalculationResponse:
    """Ingest, calculate, and persist carbon footprint activity entries.

    The authenticated UID always overrides the user_id in the payload
    for security, preventing users from writing data under another identity.

    Args:
        payload: Validated carbon calculation request with activity entries.
        authenticated_uid: UID from Firebase ID token, or generated anonymous ID if none provided.

    Returns:
        A response containing individual results, total CO2e, and Firestore document ID.

    Raises:
        HTTPException: 500 if the database write fails.
    """
    effective_user_id = verify_user_access(
        authenticated_uid, payload.user_id, context="footprint/log"
    )
    results = process_all_entries(payload.entries)
    total_co2e_kg: float = sum_total_emissions(results)
    # Sanitize description fields as defense-in-depth against XSS
    for entry in payload.entries:
        if entry.description:
            entry.description = _sanitize_description(entry.description)
    document_id: str = await asyncio.to_thread(
        _write_to_firestore, service, effective_user_id, payload, total_co2e_kg, results
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
    service: FirebaseService = Depends(get_firebase_service),
) -> dict:
    """Retrieve a user's carbon footprint history from Firestore.

    All users (including anonymous) can only access their own data.
    Anonymous users receive a unique ID per session, ensuring isolation.

    Args:
        user_id: The unique identifier of the user.
        period_days: Number of days to look back (default 30, max 365).
        authenticated_uid: UID from Firebase ID token, or generated anonymous ID if none provided.

    Returns:
        A dictionary containing the user's carbon log entries and count.

    Raises:
        HTTPException: 403 if user tries to access another user's data.
        HTTPException: 500 if the database read fails.
    """
    effective_user_id = verify_user_access(
        authenticated_uid, user_id, context="footprint"
    )
    try:
        logs = await asyncio.to_thread(
            service.get_user_logs, effective_user_id, period_days
        )
        return {
            "user_id": effective_user_id,
            "logs": logs,
            "count": len(logs),
            "period_days": period_days,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log_error(
            exc,
            context={"user_id": effective_user_id, "endpoint": "history"},
            logger=logger,
            request_path=f"/api/v1/footprint/history/{user_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
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
    service: FirebaseService = Depends(get_firebase_service),
) -> dict:
    """Retrieve an aggregated carbon footprint summary for a user.

    All users (including anonymous) can only access their own data.
    Anonymous users receive a unique ID per session, ensuring isolation.

    Args:
        user_id: The unique identifier of the user.
        period_days: Number of days to look back (default 30, max 365).
        authenticated_uid: UID from Firebase ID token, or generated anonymous ID if none provided.

    Returns:
        A dictionary containing the total CO2e, entry count, and category breakdown.

    Raises:
        HTTPException: 403 if user tries to access another user's data.
        HTTPException: 500 if the database read fails.
    """
    effective_user_id = verify_user_access(
        authenticated_uid, user_id, context="footprint"
    )
    try:
        logs = await asyncio.to_thread(
            service.get_user_logs, effective_user_id, period_days
        )
        # Single-pass aggregation: merge total and category in one loop
        total_co2e = 0.0
        category_map: dict[str, float] = {}
        for log in logs:
            total_co2e += log.get("total_co2e_kg", 0)
            for result in log.get("results", []):
                cat = result.get("category", "unknown")
                category_map[cat] = category_map.get(cat, 0) + result.get("co2e_kg", 0)
        total_co2e = round(total_co2e, 4)
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
    except HTTPException:
        raise
    except Exception as exc:
        log_error(
            exc,
            context={"user_id": effective_user_id, "endpoint": "summary"},
            logger=logger,
            request_path=f"/api/v1/footprint/summary/{user_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


def _sanitize_description(text: str) -> str:
    """Strip HTML/script tags from user-provided description text.

    Defense-in-depth measure: even though React auto-escapes JSX,
    the raw data stored in Firestore could be consumed by non-React
    clients in the future. Stripping HTML tags at the API boundary
    prevents stored XSS across all consumers.

    Args:
        text: User-provided description string.

    Returns:
        The input text with all HTML tags removed.
    """
    return re.sub(r"<[^>]*>", "", text)


def _write_to_firestore(
    service: FirebaseService,
    effective_user_id: str,
    payload: CarbonCalculationRequest,
    total_co2e_kg: float,
    results: list[EmissionResult],
) -> str:
    """Delegate the Firestore write and handle database errors.

    Args:
        service: The FirebaseService instance to use for the write.
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
        return service.write_carbon_log(
            effective_user_id,
            total_co2e_kg,
            _serialize_results(results),
            payload.calculation_date,
        )
    except Exception as exc:
        log_error(
            exc,
            context={"effective_user_id": effective_user_id, "endpoint": "log"},
            logger=logger,
            request_path="/api/v1/footprint/log",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


def _build_response(
    effective_user_id: str,
    total_co2e_kg: float,
    results: list[EmissionResult],
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
