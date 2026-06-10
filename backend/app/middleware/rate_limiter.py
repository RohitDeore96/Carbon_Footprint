"""Per-IP rate limiter middleware with Firestore-backed distributed tracking.

Provides two implementations:
- ``InMemoryRateLimiterMiddleware``: Thread-safe in-memory rate limiter using
  an ``OrderedDict`` for O(1) eviction. Suitable for single-instance deployments.
- ``RateLimiterMiddleware``: Uses ``FirestoreRateLimiter`` with automatic
  fallback to in-memory tracking when Firestore is unavailable. Suitable for
  multi-instance Cloud Run deployments.

Supports X-Forwarded-For header extraction for deployments behind reverse
proxies (Cloud Run, load balancers).
"""

import asyncio
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.constants import AppConstants

logger = logging.getLogger(__name__)

# Module-level constants for clarity
_RATE_WINDOW_SECONDS: float = 60.0
_MAX_CLIENT_ENTRIES: int = 10_000  # Prevent unbounded memory growth
_TRUSTED_PROXY_COUNT: int = 1  # Cloud Run adds 1 proxy layer
_FIRESTORE_RATE_LIMITS_COLLECTION: str = "rate_limits"


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP address, respecting X-Forwarded-For.

    When deployed behind Cloud Run or any reverse proxy, ``request.client.host``
    returns the proxy's IP. The ``X-Forwarded-For`` header contains the actual
    client IP. We take the IP at position ``-_TRUSTED_PROXY_COUNT`` from the
    right to account for untrusted upstream proxies.

    Validates that extracted IPs are well-formed to prevent header spoofing
    with malformed values that could bypass rate limiting.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        if len(ips) >= _TRUSTED_PROXY_COUNT:
            candidate = ips[-_TRUSTED_PROXY_COUNT]
            if _is_valid_ip(candidate):
                return candidate
    fallback = request.client.host if request.client else "unknown"
    return fallback if _is_valid_ip(fallback) else "unknown"


def _is_valid_ip(ip: str) -> bool:
    """Validate that a string is a well-formed IPv4 or IPv6 address.

    Prevents rate limiter bypass via malformed X-Forwarded-For headers.
    Rejects empty strings, overly long strings, and non-IP values.

    Args:
        ip: The IP address string to validate.

    Returns:
        True if the string appears to be a valid IP address.
    """
    import ipaddress as _ipaddress

    if not ip or len(ip) > 45:  # Max IPv6 length with brackets
        return False
    try:
        _ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _is_window_expired(window_start: float, current_time: float) -> bool:
    """Check whether the current rate-limit window has expired."""
    return (current_time - window_start) >= _RATE_WINDOW_SECONDS


def _build_rate_limit_response() -> JSONResponse:
    """Build a 429 Too Many Requests JSON response with Retry-After header.

    The Retry-After header follows HTTP RFC 7231 Section 7.1.3, informing
    clients when they can safely retry. The value matches the rate limit
    window duration in seconds.
    """
    response = JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )
    response.headers["Retry-After"] = "60"
    return response


class FirestoreRateLimiter:
    """Firestore-backed distributed rate limiter for multi-instance deployments.

    Uses a Firestore collection ``rate_limits`` with document ID = client_ip.
    Each document stores ``window_start`` (Firestore TIMESTAMP) and
    ``request_count`` (integer).

    Falls back to in-memory tracking when Firestore is unavailable, ensuring
    the rate limiter never blocks legitimate traffic due to infrastructure
    issues.
    """

    def __init__(self) -> None:
        """Initialize the FirestoreRateLimiter with an in-memory fallback."""
        self._memory_fallback: OrderedDict[str, dict[str, float | int]] = OrderedDict()
        self._lock: threading.Lock = threading.Lock()
        self._firestore_available: bool = True

    def _get_firestore_client(self) -> Any:
        """Lazily obtain a Firestore client.

        Returns:
            A Firestore client instance, or None if unavailable.
        """
        try:
            from app.middleware.auth import ensure_firebase_initialized
            from firebase_admin import firestore

            ensure_firebase_initialized()
            return firestore.client()
        except Exception as exc:
            logger.warning("Firestore unavailable for rate limiting: %s", exc)
            self._firestore_available = False
            return None

    def _check_and_increment_firestore(
        self, client_ip: str, current_time: float
    ) -> int | None:
        """Check and increment rate limit counters in Firestore.

        Args:
            client_ip: The client IP address.
            current_time: Current epoch time in seconds.

        Returns:
            The updated request count, or None if Firestore is unavailable.
        """
        db = self._get_firestore_client()
        if db is None:
            return None

        try:
            doc_ref = db.collection(_FIRESTORE_RATE_LIMITS_COLLECTION).document(
                client_ip
            )
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                if data is None:
                    # Corrupt document, reset
                    doc_ref.set(
                        {
                            "window_start": datetime.fromtimestamp(
                                current_time, tz=timezone.utc
                            ),
                            "request_count": 1,
                        }
                    )
                    return 1

                window_start = data.get("window_start")
                request_count = int(data.get("request_count", 0))

                # Handle both datetime and timestamp objects
                if isinstance(window_start, datetime):
                    window_epoch = window_start.timestamp()
                else:
                    window_epoch = float(window_start) if window_start else 0.0

                if _is_window_expired(window_epoch, current_time):
                    # Window expired, reset
                    doc_ref.set(
                        {
                            "window_start": datetime.fromtimestamp(
                                current_time, tz=timezone.utc
                            ),
                            "request_count": 1,
                        }
                    )
                    return 1

                # Increment count
                new_count = request_count + 1
                doc_ref.update({"request_count": new_count})
                return new_count
            else:
                # New client, create document
                doc_ref.set(
                    {
                        "window_start": datetime.fromtimestamp(
                            current_time, tz=timezone.utc
                        ),
                        "request_count": 1,
                    }
                )
                return 1
        except Exception as exc:
            logger.warning("Firestore rate limit operation failed: %s", exc)
            self._firestore_available = False
            return None

    def _check_and_increment_memory(self, client_ip: str, current_time: float) -> int:
        """Check and increment rate limit counters in memory (fallback).

        Args:
            client_ip: The client IP address.
            current_time: Current epoch time in seconds.

        Returns:
            The updated request count.
        """
        with self._lock:
            if client_ip not in self._memory_fallback or _is_window_expired(
                float(self._memory_fallback[client_ip]["window_start"]), current_time
            ):
                # Move to end so it's not evicted prematurely
                if client_ip in self._memory_fallback:
                    del self._memory_fallback[client_ip]
                self._memory_fallback[client_ip] = {
                    "window_start": current_time,
                    "request_count": 0,
                }
            self._memory_fallback[client_ip]["request_count"] = (
                int(self._memory_fallback[client_ip]["request_count"]) + 1
            )
            # Evict oldest entries if over limit
            if len(self._memory_fallback) > _MAX_CLIENT_ENTRIES:
                evict_count = len(self._memory_fallback) // 5
                for _ in range(evict_count):
                    self._memory_fallback.popitem(last=False)
            return int(self._memory_fallback[client_ip]["request_count"])

    async def check_and_increment(self, client_ip: str) -> int:
        """Check and increment the rate limit counter for a client.

        Tries Firestore first. If unavailable, falls back to in-memory.

        Args:
            client_ip: The client IP address.

        Returns:
            The current request count for this client in the window.
        """
        current_time = time.time()

        if self._firestore_available:
            count = await asyncio.to_thread(
                self._check_and_increment_firestore, client_ip, current_time
            )
            if count is not None:
                return count
            # Firestore failed, fall through to in-memory

        return self._check_and_increment_memory(client_ip, current_time)


class InMemoryRateLimiterMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing per-IP request rate limits using a sliding window.

    Thread-safe: all mutations to the internal client tracking dict are
    protected by a ``threading.Lock``.  Uses ``OrderedDict`` for O(1)
    eviction of the oldest entries once ``_MAX_CLIENT_ENTRIES`` is reached.
    """

    def __init__(self, app: Callable[..., Any]) -> None:
        """Initialize the rate limiter with an empty tracking dictionary."""
        super().__init__(app)
        self._clients: OrderedDict[str, dict[str, float | int]] = OrderedDict()
        self._lock: threading.Lock = threading.Lock()

    def _reset_client_window(self, client_ip: str, current_time: float) -> None:
        """Reset the rate-limit window for a given client IP."""
        # Move to end so it's not evicted prematurely
        if client_ip in self._clients:
            del self._clients[client_ip]
        self._clients[client_ip] = {"window_start": current_time, "request_count": 0}

    def _increment_request_count(self, client_ip: str) -> int:
        """Increment and return the request count for a client IP."""
        self._clients[client_ip]["request_count"] = (
            int(self._clients[client_ip]["request_count"]) + 1
        )
        return int(self._clients[client_ip]["request_count"])

    _EVICTION_THRESHOLD: float = 0.80  # Trigger eviction at 80% capacity

    def _evict_if_needed(self) -> None:
        """Evict the oldest client entries when the tracking dict approaches the limit.

        Uses FIFO order from OrderedDict — O(1) per eviction instead of
        O(n log n) sorting. Removes the oldest 20% of entries.
        Proactively evicts at 80% capacity to maintain steady-state memory
        usage instead of peaking before eviction.
        """
        threshold = int(_MAX_CLIENT_ENTRIES * self._EVICTION_THRESHOLD)
        if len(self._clients) <= threshold:
            return
        evict_count = len(self._clients) // 5
        for _ in range(evict_count):
            self._clients.popitem(last=False)  # Remove oldest (FIFO)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Check rate limits and either forward the request or return 429."""
        client_ip: str = _get_client_ip(request)
        current_time: float = time.time()

        with self._lock:
            if client_ip not in self._clients or _is_window_expired(
                float(self._clients[client_ip]["window_start"]), current_time
            ):
                self._reset_client_window(client_ip, current_time)
            count: int = self._increment_request_count(client_ip)
            self._evict_if_needed()

        # AI endpoints get a stricter rate limit
        max_requests = (
            AppConstants.RATE_LIMIT_AI_REQUESTS_PER_MINUTE
            if request.url.path.startswith("/api/v1/ai/")
            else AppConstants.RATE_LIMIT_REQUESTS_PER_MINUTE
        )
        if count > max_requests:
            return _build_rate_limit_response()
        return await call_next(request)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing per-IP rate limits with Firestore backend.

    Uses ``FirestoreRateLimiter`` for distributed rate limiting across
    Cloud Run instances. Falls back to in-memory tracking if Firestore
    is unavailable, ensuring graceful degradation.
    """

    def __init__(self, app: Callable[..., Any]) -> None:
        """Initialize the rate limiter with a Firestore-backed tracker."""
        super().__init__(app)
        self._rate_limiter = FirestoreRateLimiter()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Check rate limits and either forward the request or return 429."""
        client_ip: str = _get_client_ip(request)
        count: int = await self._rate_limiter.check_and_increment(client_ip)

        # AI endpoints get a stricter rate limit
        max_requests = (
            AppConstants.RATE_LIMIT_AI_REQUESTS_PER_MINUTE
            if request.url.path.startswith("/api/v1/ai/")
            else AppConstants.RATE_LIMIT_REQUESTS_PER_MINUTE
        )
        if count > max_requests:
            return _build_rate_limit_response()
        return await call_next(request)
