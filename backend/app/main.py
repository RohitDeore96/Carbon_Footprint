"""Main FastAPI application entry point for the Carbon Footprint Awareness Platform."""

import asyncio
import logging
import signal
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.constants import AppConstants
from app.middleware.auth import ensure_firebase_initialized
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes.footprint import router as footprint_router
from app.routes.ai_routes import router as ai_router
from app.routes.admin import router as admin_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application metrics (Prometheus-compatible)
# ---------------------------------------------------------------------------

_request_count: dict[str, int] = {}
_error_count: dict[str, int] = {}

# ---------------------------------------------------------------------------
# Graceful shutdown support
# ---------------------------------------------------------------------------

_shutdown_event: asyncio.Event = asyncio.Event()
_in_flight_requests: int = 0


def _signal_handler(signum: int, frame: object) -> None:
    """Handle SIGTERM by setting the shutdown event.

    Cloud Run sends SIGTERM before terminating the container.
    Setting the event allows the lifespan to begin graceful shutdown
    while in-flight requests complete.
    """
    logger.info("Received signal %d, initiating graceful shutdown...", signum)
    _shutdown_event.set()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan: initialize services on startup, cleanup on shutdown.

    On startup, initializes Firebase Admin SDK eagerly and registers a
    SIGTERM handler for graceful shutdown on Cloud Run.

    On shutdown, cancels pending asyncio tasks, waits briefly for
    in-flight requests to complete, and closes Firestore connections.
    """
    # Startup: Initialize Firebase Admin SDK eagerly so that token
    # verification works on the very first authenticated request.
    logger.info("Initializing Firebase Admin SDK at startup...")
    ensure_firebase_initialized()

    # Register SIGTERM handler for graceful shutdown on Cloud Run
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
        logger.info("SIGTERM handler registered for graceful shutdown")
    except (OSError, ValueError):
        # signal.signal may fail if not in main thread — acceptable on some platforms
        logger.debug(
            "Could not register SIGTERM handler (non-main thread or unsupported)"
        )

    logger.info("Application startup complete")
    yield

    # Shutdown: drain in-flight requests and cleanup resources
    logger.info("Application shutting down, draining in-flight requests...")

    # Wait up to 10 seconds for in-flight requests to complete
    for _ in range(100):
        if _in_flight_requests <= 0:
            break
        await asyncio.sleep(0.1)

    # Cancel pending asyncio tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if tasks:
        logger.info("Cancelling %d pending tasks...", len(tasks))
        for task in tasks:
            task.cancel()
        # Wait briefly for cancellation to propagate
        await asyncio.gather(*tasks, return_exceptions=True)

    # Close Firestore client connections to release gRPC channels
    try:
        from firebase_admin import firestore as firebase_firestore

        client = firebase_firestore.client()
        client.close()
        logger.info("Firestore client closed")
    except Exception as exc:
        logger.debug("Firestore client close skipped: %s", exc)

    logger.info("Application shutdown complete")


def _configure_cors(application: FastAPI) -> None:
    """Apply CORS middleware with explicit origins from constants."""
    application.add_middleware(
        CORSMiddleware,
        allow_origins=AppConstants.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=AppConstants.CORS_ALLOWED_METHODS,
        allow_headers=AppConstants.CORS_ALLOWED_HEADERS,
    )


def _configure_security_headers(application: FastAPI) -> None:
    """Apply OWASP security headers middleware."""
    application.add_middleware(SecurityHeadersMiddleware)


def _configure_request_id(application: FastAPI) -> None:
    """Apply request ID propagation middleware for distributed tracing.

    Generates a unique X-Request-ID per request and propagates it
    to the response header and structured log context. This enables
    correlation of logs across Cloud Run instances and simplifies
    debugging of distributed request flows.
    """
    application.add_middleware(RequestIdMiddleware)


def _configure_csrf(application: FastAPI) -> None:
    """Apply CSRF protection middleware for state-changing requests."""
    application.add_middleware(CSRFMiddleware)


def _configure_rate_limiter(application: FastAPI) -> None:
    """Apply Firestore-backed rate limiter with in-memory fallback."""
    application.add_middleware(RateLimiterMiddleware)


def _register_health_route(application: FastAPI) -> None:
    """Register the health check endpoint."""

    @application.get("/health")
    async def health_check() -> dict[str, str]:
        """Return the current health status and API version."""
        return {"status": "healthy", "version": "1.0.0"}


def _register_metrics_route(application: FastAPI) -> None:
    """Register the Prometheus-compatible /metrics endpoint.

    Exposes request counts and error counts in Prometheus exposition format.
    This provides essential production observability for Cloud Run deployments
    without requiring external dependencies like prometheus-client.
    """

    @application.get("/metrics")
    async def metrics() -> Response:
        """Return Prometheus-compatible metrics in text exposition format."""
        lines = [
            "# HELP http_requests_total Total HTTP requests by endpoint",
            "# TYPE http_requests_total counter",
        ]
        for endpoint, count in sorted(_request_count.items()):
            safe_label = endpoint.replace("/", "_").strip("_")
            lines.append(f'http_requests_total{{endpoint="{safe_label}"}} {count}')

        lines.extend(
            [
                "",
                "# HELP http_errors_total Total HTTP errors by endpoint",
                "# TYPE http_errors_total counter",
            ]
        )
        for endpoint, count in sorted(_error_count.items()):
            safe_label = endpoint.replace("/", "_").strip("_")
            lines.append(f'http_errors_total{{endpoint="{safe_label}"}} {count}')

        lines.extend(
            [
                "",
                "# HELP http_in_flight_requests Current in-flight requests",
                "# TYPE http_in_flight_requests gauge",
                f"http_in_flight_requests {_in_flight_requests}",
            ]
        )

        return Response(
            content="\n".join(lines) + "\n",
            media_type="text/plain; version=0.0.4",
        )


def _register_footprint_routes(application: FastAPI) -> None:
    """Register the carbon footprint logging router."""
    application.include_router(footprint_router)


def _register_ai_routes(application: FastAPI) -> None:
    """Register the AI sustainability insights router."""
    application.include_router(ai_router)


def _register_admin_routes(application: FastAPI) -> None:
    """Register the admin operations router."""
    application.include_router(admin_router)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID to every request.

    Generates a UUID4 request identifier and attaches it to:
    - The ``X-Request-ID`` response header (client-visible)
    - The ``X-Request-ID`` request state (available to downstream handlers)

    If the client sends an ``X-Request-ID`` header, it is preserved
    and forwarded, enabling end-to-end trace correlation across
    microservice boundaries.

    Also tracks in-flight request count and request/error metrics
    for the ``/metrics`` endpoint.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Inject request ID into the request/response cycle."""
        global _in_flight_requests
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Track in-flight requests and metrics
        _in_flight_requests += 1
        endpoint = request.url.path
        _request_count[endpoint] = _request_count.get(endpoint, 0) + 1

        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            # Track errors (4xx/5xx)
            if response.status_code >= 400:
                _error_count[endpoint] = _error_count.get(endpoint, 0) + 1

            return response
        finally:
            _in_flight_requests -= 1


def create_app() -> FastAPI:
    """Factory function that constructs and configures the FastAPI application."""
    application: FastAPI = FastAPI(
        title="Carbon Footprint Awareness Platform API",
        description=(
            "Track carbon emissions from daily activities, get AI-powered sustainability "
            "insights using Google Gemini, and reduce your environmental impact. "
            "Supports transport, energy, diet, and consumption categories."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    _configure_cors(application)
    _configure_security_headers(application)
    _configure_csrf(application)
    _configure_request_id(application)
    _configure_rate_limiter(application)
    _register_health_route(application)
    _register_metrics_route(application)
    _register_footprint_routes(application)
    _register_ai_routes(application)
    _register_admin_routes(application)
    return application


app: FastAPI = create_app()
