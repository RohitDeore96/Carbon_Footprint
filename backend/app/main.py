"""Main FastAPI application entry point for the Carbon Footprint Awareness Platform."""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.constants import AppConstants
from app.middleware.auth import ensure_firebase_initialized
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes.footprint import router as footprint_router
from app.routes.ai_routes import router as ai_router
from app.routes.admin import router as admin_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan: initialize services on startup, cleanup on shutdown."""
    # Startup: Initialize Firebase Admin SDK eagerly so that token
    # verification works on the very first authenticated request.
    logger.info("Initializing Firebase Admin SDK at startup...")
    ensure_firebase_initialized()
    logger.info("Application startup complete")
    yield
    # Shutdown: no special cleanup needed
    logger.info("Application shutdown")


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


def _configure_rate_limiter(application: FastAPI) -> None:
    """Apply Firestore-backed rate limiter with in-memory fallback."""
    application.add_middleware(RateLimiterMiddleware)


def _register_health_route(application: FastAPI) -> None:
    """Register the health check endpoint."""

    @application.get("/health")
    async def health_check() -> dict[str, str]:
        """Return the current health status and API version."""
        return {"status": "healthy", "version": "1.0.0"}


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
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Inject request ID into the request/response cycle."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


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
    _configure_request_id(application)
    _configure_rate_limiter(application)
    _register_health_route(application)
    _register_footprint_routes(application)
    _register_ai_routes(application)
    _register_admin_routes(application)
    return application


app: FastAPI = create_app()
