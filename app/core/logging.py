"""Structured logging configuration."""

import logging
import sys

import structlog
from structlog.processors import TimeStamper, add_log_level, format_exc_info
from structlog.stdlib import ExtraAdder, filter_by_level

from app.core.config import settings


def configure_logging() -> None:
    """Configure structured JSON logging for the application."""
    shared_processors: list[structlog.types.Processor] = [
        filter_by_level,
        add_log_level,
        TimeStamper(fmt="iso"),
        ExtraAdder(),
        format_exc_info,
    ]

    if settings.debug:
        # Pretty printing in development
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
    else:
        # JSON logging in production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(serializer=__import__("orjson").dumps),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
