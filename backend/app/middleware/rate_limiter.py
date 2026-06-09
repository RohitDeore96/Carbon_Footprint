"""In-memory rate limiter middleware to throttle requests per client IP."""

import threading
import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.constants import AppConstants

# Module-level constants for clarity
_RATE_WINDOW_SECONDS: float = 60.0
_MAX_CLIENT_ENTRIES: int = 10_000  # Prevent unbounded memory growth


def _get_client_ip(request: Request) -> str:
    """Extract the client IP address from the request."""
    return request.client.host if request.client else "unknown"


def _is_window_expired(window_start: float, current_time: float) -> bool:
    """Check whether the current rate-limit window has expired."""
    return (current_time - window_start) >= _RATE_WINDOW_SECONDS


def _build_rate_limit_response() -> JSONResponse:
    """Build a 429 Too Many Requests JSON response."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing per-IP request rate limits using a sliding window.

    Thread-safe: all mutations to the internal client tracking dict are
    protected by a ``threading.Lock``.  Evicts the oldest entries once
    ``_MAX_CLIENT_ENTRIES`` is reached to prevent unbounded memory growth.
    """

    def __init__(self, app: object) -> None:
        """Initialize the rate limiter with an empty tracking dictionary."""
        super().__init__(app)
        self._clients: dict[str, dict[str, float | int]] = {}
        self._lock: threading.Lock = threading.Lock()

    def _reset_client_window(self, client_ip: str, current_time: float) -> None:
        """Reset the rate-limit window for a given client IP."""
        self._clients[client_ip] = {"window_start": current_time, "request_count": 0}

    def _increment_request_count(self, client_ip: str) -> int:
        """Increment and return the request count for a client IP."""
        self._clients[client_ip]["request_count"] = (
            int(self._clients[client_ip]["request_count"]) + 1
        )
        return int(self._clients[client_ip]["request_count"])

    def _evict_if_needed(self) -> None:
        """Evict the oldest client entries when the tracking dict exceeds the limit."""
        if len(self._clients) <= _MAX_CLIENT_ENTRIES:
            return
        # Remove the 20% oldest entries by window_start
        sorted_clients = sorted(
            self._clients.items(), key=lambda item: float(item[1]["window_start"])
        )
        evict_count = len(self._clients) // 5
        for ip, _ in sorted_clients[:evict_count]:
            del self._clients[ip]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
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

        if count > AppConstants.RATE_LIMIT_REQUESTS_PER_MINUTE:
            return _build_rate_limit_response()
        return await call_next(request)
