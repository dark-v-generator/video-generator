"""
Centralized logging configuration for the Video Generator application.

This module provides consistent logging setup across the entire application,
ensuring proper log levels, formatting, and handlers are configured.
"""

import logging
import sys
from typing import Optional
from .config import settings


def configure_logging(
    format_string: Optional[str] = None,
    include_file_handler: bool = False,
    log_file_path: str = "app.log",
) -> None:
    """
    Configure logging for the application.

    Args:
        format_string: Custom format string for log messages
        include_file_handler: Whether to include file logging
        log_file_path: Path to log file if file handler is enabled
    """
    # Default format string
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )

    # Configure handlers
    handlers = [logging.StreamHandler(sys.stdout)]

    if include_file_handler:
        handlers.append(logging.FileHandler(log_file_path))

    # Configure root logger
    logging.basicConfig(
        level=logging.WARNING,
        format=format_string,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Configure specific loggers
    _configure_application_loggers()
    _configure_third_party_loggers()


def _configure_application_loggers() -> None:
    """Configure loggers for our application modules."""
    app_loggers = [
        "src",
        "src.services",
        "src.services.history_service",
        "src.services.config_service",
        "src.services.video_service",
        "src.services.speech_service",
        "src.services.captions_service",
        "src.services.cover_service",
        "src.api",
        "src.repositories",
        "src.proxies",
    ]

    # Our application loggers honor settings.debug, independent from root level
    log_level = logging.DEBUG if settings.debug else logging.INFO

    for logger_name in app_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)


def _configure_third_party_loggers() -> None:
    """Configure third-party library loggers to log only errors by default."""
    # Set common third-party loggers to ERROR to suppress info/warnings
    third_party_loggers = [
        "uvicorn",
        "uvicorn.access",
        "fastapi",
        "httpx",
        "urllib3",
        "requests",
        "asyncio",
        "multipart",
        "pydub",
        "pytubefix",
        "fsspec",
    ]
    for name in third_party_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_function_call(func_name: str, **kwargs) -> None:
    """
    Log a function call with its parameters.

    Args:
        func_name: Name of the function being called
        **kwargs: Function parameters to log
    """
    logger = logging.getLogger("src.services")
    if logger.isEnabledFor(logging.DEBUG):
        params = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.debug(f"Calling {func_name}({params})")


def log_progress_event(event, service_name: str = "unknown") -> None:
    """
    Log progress events in a consistent format.

    Args:
        event: Progress event to log
        service_name: Name of the service generating the event
    """
    logger = logging.getLogger(f"src.services.{service_name}")

    if hasattr(event, "status") and hasattr(event, "message"):
        # This is a ProgressEvent
        logger.info(f"Progress [{event.status}]: {event.message}")
        if hasattr(event, "progress") and event.progress is not None:
            logger.debug(f"Progress: {event.progress}%")
        if hasattr(event, "details") and event.details:
            logger.debug(f"Details: {event.details}")
    else:
        # Avoid logging raw binary or large payloads; log summary instead
        try:
            if isinstance(event, (bytes, bytearray)):
                logger.info(f"Event: bytes payload ({len(event)} bytes)")
            else:
                logger.info(f"Event: {type(event).__name__}")
        except Exception:
            logger.info("Event: <unprintable>")
