"""Structured error tracking service with optional Cloud Error Reporting integration.

Provides a centralized error reporting interface that can be extended to
integrate with Google Cloud Error Reporting, Sentry, or similar services.
In the default configuration, errors are logged via the structured logging
module (``app.utils.error_logging``) which is compatible with Cloud Logging.

To enable Cloud Error Reporting integration:
1. Set the ``ERROR_TRACKING_PROVIDER`` environment variable to ``cloud``
2. Ensure the Cloud Run service account has the ``roles/errorreporting.writer`` role
3. Errors will be reported to Cloud Error Reporting automatically

To enable Sentry integration:
1. Set ``ERROR_TRACKING_PROVIDER=sentry``
2. Set ``SENTRY_DSN=<your-dsn>`` environment variable
3. Install sentry-sdk: ``pip install sentry-sdk``
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_ERROR_TRACKING_PROVIDER: str = os.environ.get("ERROR_TRACKING_PROVIDER", "logging")


def report_error(
    exception: Exception,
    context: dict[str, Any] | None = None,
    request_path: str = "",
    user_id: str = "",
) -> None:
    """Report an error to the configured error tracking service.

    This is a unified interface that dispatches to the appropriate
    error tracking backend based on configuration. Falls back to
    structured logging if no external provider is configured.

    Args:
        exception: The exception to report.
        context: Optional dictionary with additional context.
        request_path: The request URL path, if available.
        user_id: The authenticated user ID, if available.
    """
    from app.utils.error_logging import log_error

    # Always log locally regardless of provider
    log_error(
        exception,
        context=context,
        logger=logger,
        request_path=request_path,
    )

    if _ERROR_TRACKING_PROVIDER == "sentry":
        _report_to_sentry(exception, context, request_path, user_id)
    elif _ERROR_TRACKING_PROVIDER == "cloud":
        _report_to_cloud_error_reporting(exception, context, request_path, user_id)
    # Default "logging" provider: already handled by log_error above


def _report_to_sentry(
    exception: Exception,
    context: dict[str, Any] | None,
    request_path: str,
    user_id: str,
) -> None:
    """Report an error to Sentry (if sentry-sdk is installed).

    Args:
        exception: The exception to report.
        context: Optional context dictionary.
        request_path: The request URL path.
        user_id: The authenticated user ID.
    """
    try:
        import sentry_sdk

        sentry_sdk.set_context(
            "request",
            {
                "path": request_path,
                "user_id": user_id,
                **(context or {}),
            },
        )
        sentry_sdk.capture_exception(exception)
    except ImportError:
        logger.warning("sentry-sdk not installed; falling back to structured logging")
    except Exception as exc:
        logger.warning("Failed to report error to Sentry: %s", exc)


def _report_to_cloud_error_reporting(
    exception: Exception,
    context: dict[str, Any] | None,
    request_path: str,
    user_id: str,
) -> None:
    """Report an error to Google Cloud Error Reporting.

    Cloud Error Reporting automatically ingests structured JSON logs
    from Cloud Logging when errors are logged at ERROR severity with
    proper formatting. This function enhances the log entry with
    Cloud Error Reporting specific fields.

    Args:
        exception: The exception to report.
        context: Optional context dictionary.
        request_path: The request URL path.
        user_id: The authenticated user ID.
    """
    import json
    from datetime import datetime, timezone

    error_payload = {
        "eventTime": datetime.now(tz=timezone.utc).isoformat(),
        "serviceContext": {
            "service": "carbon-footprint-api",
            "version": "1.0.0",
        },
        "message": f"{type(exception).__name__}: {exception}",
        "context": {
            "httpRequest": {"url": request_path},
            "user": user_id,
            "reportLocation": {
                "filePath": context.get("file", "") if context else "",
                "functionName": context.get("function", "") if context else "",
            },
        },
    }
    logger.error(
        "Cloud Error Report: %s",
        json.dumps(error_payload, default=str),
    )
