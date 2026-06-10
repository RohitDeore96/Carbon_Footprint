"""Structured error logging module for the Carbon Footprint Awareness Platform.

Provides a ``log_error`` function that emits structured JSON log entries
for 500-level errors, making it easier to search, filter, and aggregate
errors in production log-management systems (Cloud Logging, Datadog, etc.).
"""

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any


def log_error(
    exception: Exception,
    context: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
    request_path: str = "",
) -> None:
    """Log an exception as a structured JSON entry.

    Args:
        exception: The exception to log.
        context: Optional dictionary with additional context (e.g. user_id, endpoint).
        logger: The logger instance to use. Falls back to the module logger.
        request_path: The request URL path, if available.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    environment = os.environ.get("ENVIRONMENT", "development")

    error_entry: dict[str, Any] = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "error_type": type(exception).__name__,
        "error_message": str(exception),
        "stack_trace": traceback.format_exc(),
        "context": context or {},
        "request_path": request_path,
        "environment": environment,
    }

    logger.error("Structured error: %s", json.dumps(error_entry, default=str))
