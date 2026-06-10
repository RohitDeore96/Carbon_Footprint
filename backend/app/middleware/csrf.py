"""CSRF protection middleware using custom header verification.

Enforces that state-changing requests (POST, PUT, DELETE) include a
``X-Requested-With`` header or a valid ``Origin``/``Referer`` that
matches the server's allowed origins. This prevents cross-site request
forgery attacks where a malicious site could submit forms on behalf of
an authenticated user.

This approach is recommended by OWASP for API-based applications that
use token-based authentication (like Firebase ID tokens) rather than
cookies. Since the backend uses ``Authorization: Bearer`` tokens, the
primary CSRF vector is already mitigated — this middleware adds
defense-in-depth for same-origin contexts.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.constants import AppConstants

logger = logging.getLogger(__name__)

_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})

# Admin paths have their own key-based authentication (X-Admin-Key header)
# and are typically called by Cloud Scheduler, not browsers.
_ADMIN_PATH_PREFIX: str = "/api/v1/admin"

# X-Requested-With is automatically added by XMLHttpRequest/fetch from browsers
# but cannot be added by simple HTML forms — this is the CSRF protection mechanism
_CSRF_SAFE_HEADERS: frozenset[str] = frozenset({"X-Requested-With"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces CSRF protection on state-changing requests.

    Validates that POST, PUT, and DELETE requests originate from the
    application's own frontend by checking for either:
    1. An ``X-Requested-With`` header (set by XMLHttpRequest/fetch)
    2. A matching ``Origin`` or ``Referer`` header against allowed origins

    Safe methods (GET, HEAD, OPTIONS) are always allowed through.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        """Validate CSRF headers on state-changing requests."""
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        # Admin paths use their own X-Admin-Key authentication and are
        # typically invoked by Cloud Scheduler, not browsers.
        if request.url.path.startswith(_ADMIN_PATH_PREFIX):
            return await call_next(request)

        # Requests with Authorization header (Bearer tokens) are inherently
        # CSRF-safe: browsers do not automatically attach custom Authorization
        # headers in cross-origin requests. Token-based auth provides stronger
        # CSRF protection than Origin checks alone.
        if request.headers.get("authorization", "").startswith("Bearer "):
            return await call_next(request)

        # Admin requests with X-Admin-Key header are server-to-server
        # (e.g., Cloud Scheduler) and do not originate from browsers.
        if request.headers.get("x-admin-key"):
            return await call_next(request)

        # Check for X-Requested-With header (AJAX requests)
        # Header names are case-insensitive per HTTP spec
        requested_with = request.headers.get("x-requested-with", "")
        if requested_with.lower() == "xmlhttprequest":
            return await call_next(request)

        # Check Origin header against allowed origins
        origin = request.headers.get("origin")
        if origin and origin in AppConstants.CORS_ALLOWED_ORIGINS:
            return await call_next(request)

        # Check Referer header as fallback
        referer = request.headers.get("referer")
        if referer:
            for allowed_origin in AppConstants.CORS_ALLOWED_ORIGINS:
                if referer.startswith(allowed_origin):
                    return await call_next(request)

        # Log and reject if no valid CSRF indicator found
        logger.warning(
            "CSRF check failed for %s %s: no X-Requested-With, Origin, or Referer header "
            "matching allowed origins",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF validation failed. Missing required header."},
        )
