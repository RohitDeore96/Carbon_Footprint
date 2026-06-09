"""OWASP-compliant security headers middleware for HTTP response hardening."""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.constants import AppConstants


def _inject_csp_header(response: Response) -> None:
    """Inject Content-Security-Policy header."""
    response.headers["Content-Security-Policy"] = AppConstants.CSP_POLICY


def _inject_frame_options_header(response: Response) -> None:
    """Inject X-Frame-Options header."""
    response.headers["X-Frame-Options"] = AppConstants.X_FRAME_OPTIONS


def _inject_hsts_header(response: Response) -> None:
    """Inject Strict-Transport-Security header with includeSubDomains and preload."""
    response.headers["Strict-Transport-Security"] = (
        f"max-age={AppConstants.HSTS_MAX_AGE}; includeSubDomains; preload"
    )


def _inject_content_type_options_header(response: Response) -> None:
    """Inject X-Content-Type-Options header."""
    response.headers["X-Content-Type-Options"] = AppConstants.X_CONTENT_TYPE_OPTIONS


def _inject_referrer_policy_header(response: Response) -> None:
    """Inject Referrer-Policy header."""
    response.headers["Referrer-Policy"] = AppConstants.REFERRER_POLICY


def _inject_permissions_policy_header(response: Response) -> None:
    """Inject Permissions-Policy header to restrict browser features."""
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that injects OWASP-recommended security headers into every response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request and inject security headers into the response."""
        response: Response = await call_next(request)
        _inject_csp_header(response)
        _inject_frame_options_header(response)
        _inject_hsts_header(response)
        _inject_content_type_options_header(response)
        _inject_referrer_policy_header(response)
        _inject_permissions_policy_header(response)
        return response
