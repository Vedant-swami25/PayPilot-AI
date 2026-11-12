from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "cvv",
    "card_number",
    "private_key",
)

_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_BASIC_RE = re.compile(r"(Basic\s+)[A-Za-z0-9+/=]+", re.IGNORECASE)


def _redact_string(value: str) -> str:
    value = _BEARER_RE.sub(r"\1[REDACTED]", value)
    value = _BASIC_RE.sub(r"\1[REDACTED]", value)
    return value


def redact_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive fields in dictionaries, lists, and strings."""
    if isinstance(data, dict):
        sanitized: dict[Any, Any] = {}
        for key, value in data.items():
            key_str = str(key).lower()
            if any(fragment in key_str for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = redact_sensitive_data(value)
        return sanitized
    if isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    if isinstance(data, tuple):
        return tuple(redact_sensitive_data(item) for item in data)
    if isinstance(data, str):
        return _redact_string(data)
    return data


def _redaction_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    return redact_sensitive_data(event_dict)


def configure_logging(debug: bool = False, app_env: str = "development") -> None:
    """Configure structured logging with automatic secret redaction."""
    log_level = logging.DEBUG if debug else logging.INFO

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _redaction_processor,
    ]

    if app_env == "development":
        renderer: Any = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    # Quiet noisy third-party loggers unless debugging
    logging.getLogger("httpx").setLevel(logging.WARNING if not debug else logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def get_logger(name: str = "paypilot") -> structlog.stdlib.BoundLogger:
    """Return a structured logger bound to the given module name."""
    return structlog.get_logger(name)


def bind_request_context(**kwargs: Any) -> None:
    """Bind correlation fields (request_id, user_id, workflow_id) into log context."""
    structlog.contextvars.bind_contextvars(**redact_sensitive_data(kwargs))


def clear_request_context() -> None:
    """Clear per-request structured logging context."""
    structlog.contextvars.clear_contextvars()

