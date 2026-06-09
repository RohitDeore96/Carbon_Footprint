"""In-memory rate limiter middleware to throttle requests per client IP.

Supports X-Forwarded-For header extraction for deployments behind
reverse proxies (Cloud Run, load balancers). Uses OrderedDict for
O(1) eviction of oldest entries instead of O(n log n) sorting.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.constants import AppConstants

# Module-level constants for clarity
_RATE_WINDOW_SECONDS: float = 60.0
_MAX_CLIENT_ENTRIES: int = 10_000  # Prevent unbounded memory growth
_TRUSTED_PROXY_COUNT: int = 1  # Cloud Run adds 1 proxy layer


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP address, respecting X-Forwarded-For.

    When deployed behind Cloud Run or any reverse proxy, ``request.client.host``
    returns the proxy's IP. The ``X-Forwarded-For`` header contains the actual
    client IP. We take the IP at position ``-_TRUSTED_PROXY_COUNT`` from the
    right to account for untrusted upstream proxies.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        if len(ips) >= _TRUSTED_PROXY_COUNT:
            return ips[-_TRUSTED_PROXY_COUNT]
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

    def _evict_if_needed(self) -> None:
        """Evict the oldest client entries when the tracking dict exceeds the limit.

        Uses FIFO order from OrderedDict — O(1) per eviction instead of
        O(n log n) sorting. Removes the oldest 20% of entries.
        """
        if len(self._clients) <= _MAX_CLIENT_ENTRIES:
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

        if count > AppConstants.RATE_LIMIT_REQUESTS_PER_MINUTE:
            return _build_rate_limit_response()
        return await call_next(request)
