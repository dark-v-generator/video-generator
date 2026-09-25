"""
Centralized logging configuration for the Video Generator application.

This module provides consistent logging setup across the entire application,
ensuring proper log levels, formatting, and handlers are configured.
"""

import logging
import sys
from typing import Optional
from .secrets import secrets


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
        "src.api",
        "src.repositories",
        "src.proxies",
    ]

    # Our application loggers honor secrets.debug, independent from root level
    log_level = logging.DEBUG if secrets.debug else logging.INFO

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
