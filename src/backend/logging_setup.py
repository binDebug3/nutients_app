"""Shared logging configuration for backend scripts.

This module sets up one-time console and rotating file logging for backend jobs.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


MAX_LOG_FILE_BYTES = 5 * 1024 * 1024
BACKUP_LOG_FILE_COUNT = 5
BASE_LOGGER_NAME = "nutients_app.backend"


def configure_backend_logging(logger_name: str) -> logging.Logger:
    """Configure backend logging and return a child logger.

    Args:
        logger_name: Logical name of the script/module logger.

    Returns:
        Configured logger instance.
    """
    backend_dir = Path(__file__).resolve().parent
    repo_root = backend_dir.parents[1]
    log_dir = repo_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    base_logger = logging.getLogger(BASE_LOGGER_NAME)
    if not getattr(base_logger, "_nutients_backend_logging_configured", False):
        base_logger.setLevel(logging.INFO)
        base_logger.propagate = False

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )

        file_handler = RotatingFileHandler(
            log_dir / "backend.log",
            maxBytes=MAX_LOG_FILE_BYTES,
            backupCount=BACKUP_LOG_FILE_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(module)s | %(message)s"
            )
        )

        base_logger.addHandler(console_handler)
        base_logger.addHandler(file_handler)
        base_logger._nutients_backend_logging_configured = True  # type: ignore[attr-defined]
        base_logger.info("Backend logging configured. Log directory: %s", log_dir)

    logger = logging.getLogger(f"{BASE_LOGGER_NAME}.{logger_name}")
    logger.setLevel(logging.INFO)
    logger.propagate = True
    return logger
