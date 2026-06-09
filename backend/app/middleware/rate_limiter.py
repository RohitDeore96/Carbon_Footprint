"""In-memory rate limiter middleware to throttle requests per client IP."""

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.constants import AppConstants


def _get_client_ip(request: Request) -> str:
    """Extract the client IP address from the request."""
    return request.client.host if request.client else "unknown"


def _is_window_expired(window_start: float, current_time: float) -> bool:
    """Check whether the current rate-limit window has expired."""
    return (current_time - window_start) >= 60.0


def _build_rate_limit_response() -> JSONResponse:
    """Build a 429 Too Many Requests JSON response."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing per-IP request rate limits using a sliding window."""

    def __init__(self, app: object) -> None:
        """Initialize the rate limiter with an empty tracking dictionary."""
        super().__init__(app)
        self._clients: dict[str, dict[str, float | int]] = {}

    def _reset_client_window(self, client_ip: str, current_time: float) -> None:
        """Reset the rate-limit window for a given client IP."""
        self._clients[client_ip] = {"window_start": current_time, "request_count": 0}

    def _increment_request_count(self, client_ip: str) -> int:
        """Increment and return the request count for a client IP."""
        self._clients[client_ip]["request_count"] = (
            int(self._clients[client_ip]["request_count"]) + 1
        )
        return int(self._clients[client_ip]["request_count"])

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Check rate limits and either forward the request or return 429."""
        client_ip: str = _get_client_ip(request)
        current_time: float = time.time()
        if client_ip not in self._clients or _is_window_expired(
            float(self._clients[client_ip]["window_start"]), current_time
        ):
            self._reset_client_window(client_ip, current_time)
        count: int = self._increment_request_count(client_ip)
        if count > AppConstants.RATE_LIMIT_REQUESTS_PER_MINUTE:
            return _build_rate_limit_response()
        return await call_next(request)
