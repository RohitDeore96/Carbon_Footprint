"""Carbon footprint logging route with Pydantic validation and Firestore persistence."""

import asyncio
import logging
import re
import threading

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
_singleton_lock: threading.Lock = threading.Lock()


def get_firebase_service() -> FirebaseService:
    """FastAPI dependency that provides a thread-safe singleton FirebaseService instance.

    Returns the same FirebaseService across all requests within a process.
    The Firestore client internally shares a gRPC channel, so reusing
    the wrapper avoids unnecessary object allocation and GC pressure.
    Uses a threading.Lock to ensure thread-safe initialization, protecting
    against race conditions in multi-threaded ASGI workers.

    Returns:
        A configured FirebaseService instance.
    """
    global _firebase_service_instance
    if _firebase_service_instance is None:
        with _singleton_lock:
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
    # Validate non-empty after sanitization to prevent blank entries from
    # HTML-only inputs like "<script>alert(1)</script>" → ""
    for entry in payload.entries:
        if entry.description:
            entry.description = _sanitize_description(entry.description)
        if not entry.description or not entry.description.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Description must contain non-whitespace text after sanitization.",
            )
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
    page: int = Query(default=1, ge=1, description="Page number for pagination"),
    page_size: int = Query(
        default=20, ge=1, le=100, description="Number of entries per page"
    ),
    authenticated_uid: str = Depends(get_current_user),
    service: FirebaseService = Depends(get_firebase_service),
) -> dict:
    """Retrieve a user's carbon footprint history from Firestore with pagination.

    All users (including anonymous) can only access their own data.
    Anonymous users receive a unique ID per session, ensuring isolation.
    Supports cursor-free pagination with page/page_size parameters.

    Args:
        user_id: The unique identifier of the user.
        period_days: Number of days to look back (default 30, max 365).
        page: Page number (1-indexed, default 1).
        page_size: Number of entries per page (default 20, max 100).
        authenticated_uid: UID from Firebase ID token, or generated anonymous ID if none provided.

    Returns:
        A dictionary containing the user's carbon log entries, pagination info, and count.

    Raises:
        HTTPException: 403 if user tries to access another user's data.
        HTTPException: 500 if the database read fails.
    """
    effective_user_id = verify_user_access(
        authenticated_uid, user_id, context="footprint"
    )
    try:
        all_logs = await asyncio.to_thread(
            service.get_user_logs, effective_user_id, period_days
        )
        # Apply pagination
        total_count = len(all_logs)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_logs = all_logs[start_idx:end_idx]
        return {
            "user_id": effective_user_id,
            "logs": paginated_logs,
            "count": total_count,
            "period_days": period_days,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total_count + page_size - 1) // page_size),
            "has_next": end_idx < total_count,
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


_FIRESTORE_WRITE_MAX_RETRIES: int = 3
_FIRESTORE_WRITE_BACKOFF_BASE: float = 0.5  # seconds


def _write_to_firestore(
    service: FirebaseService,
    effective_user_id: str,
    payload: CarbonCalculationRequest,
    total_co2e_kg: float,
    results: list[EmissionResult],
) -> str:
    """Delegate the Firestore write with retry logic for transient errors.

    Implements exponential backoff for transient Firestore errors (network
    timeouts, service unavailable) to prevent data loss from temporary
    infrastructure issues. Non-retryable errors fail immediately.

    Args:
        service: The FirebaseService instance to use for the write.
        effective_user_id: The resolved user ID (authenticated or from payload).
        payload: The original validated request payload.
        total_co2e_kg: Aggregated emissions total.
        results: List of EmissionResult models.

    Returns:
        The Firestore document ID of the persisted record.

    Raises:
        HTTPException: 500 with detail message if all retries fail.
    """
    import time as time_module

    last_exc: Exception | None = None
    for attempt in range(_FIRESTORE_WRITE_MAX_RETRIES + 1):
        try:
            return service.write_carbon_log(
                effective_user_id,
                total_co2e_kg,
                _serialize_results(results),
                payload.calculation_date,
            )
        except Exception as exc:
            last_exc = exc
            # Only retry on transient errors (network, timeout, service unavailable)
            is_transient = any(
                kw in str(exc).lower()
                for kw in (
                    "timeout",
                    "unavailable",
                    "connection",
                    "network",
                    "deadline",
                )
            )
            if not is_transient or attempt >= _FIRESTORE_WRITE_MAX_RETRIES:
                log_error(
                    exc,
                    context={
                        "effective_user_id": effective_user_id,
                        "endpoint": "log",
                        "attempt": attempt + 1,
                    },
                    logger=logger,
                    request_path="/api/v1/footprint/log",
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error",
                ) from exc
            backoff = min(_FIRESTORE_WRITE_BACKOFF_BASE * (2**attempt), 4.0)
            logger.warning(
                "Firestore write attempt %d/%d failed (transient): %s. Retrying in %.1fs...",
                attempt + 1,
                _FIRESTORE_WRITE_MAX_RETRIES + 1,
                exc,
                backoff,
            )
            time_module.sleep(backoff)
    # Should not reach here, but satisfy type checker
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from last_exc


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
