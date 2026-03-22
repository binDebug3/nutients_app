"""Application logging configuration for the Streamlit frontend.

This module configures one-time logging with console output and rotating file
handlers in the repository `logs` directory.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict


MAX_LOG_FILE_BYTES = 5 * 1024 * 1024
BACKUP_LOG_FILE_COUNT = 5


class JsonLogFormatter(logging.Formatter):
    """Render log records as JSON lines for easy filtering and analysis."""

    _STANDARD_FIELDS = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format one log record into a JSON string.

        Args:
            record: The logging record to format.

        Returns:
            JSON string containing standard and custom fields.
        """
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": record.getMessage(),
        }

        event_name = getattr(record, "event", None)
        if event_name is not None:
            payload["event"] = event_name

        for key, value in record.__dict__.items():
            if key in self._STANDARD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def _build_rotating_file_handler(log_file_path: Path) -> RotatingFileHandler:
    """Create a rotating file handler with JSON log formatting.

    Args:
        log_file_path: Absolute output path for the log file.

    Returns:
        Configured rotating file handler.
    """
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=MAX_LOG_FILE_BYTES,
        backupCount=BACKUP_LOG_FILE_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JsonLogFormatter())
    return file_handler


def configure_app_logging(repo_root: Path) -> Dict[str, logging.Logger]:
    """Configure app, auth, and query loggers once for Streamlit reruns.

    Args:
        repo_root: Repository root path for creating the logs directory.

    Returns:
        Logger dictionary keyed by area (`app`, `auth`, `query`).
    """
    log_dir = repo_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    app_logger = logging.getLogger("nutients_app")
    auth_logger = logging.getLogger("nutients_app.auth")
    query_logger = logging.getLogger("nutients_app.query")

    if getattr(app_logger, "_nutients_logging_configured", False):
        return {"app": app_logger, "auth": auth_logger, "query": query_logger}

    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    app_file_handler = _build_rotating_file_handler(log_dir / "app.log")
    auth_file_handler = _build_rotating_file_handler(log_dir / "auth.log")
    query_file_handler = _build_rotating_file_handler(log_dir / "query.log")

    app_logger.addHandler(console_handler)
    app_logger.addHandler(app_file_handler)

    auth_logger.setLevel(logging.INFO)
    auth_logger.propagate = True
    auth_logger.addHandler(auth_file_handler)

    query_logger.setLevel(logging.INFO)
    query_logger.propagate = True
    query_logger.addHandler(query_file_handler)

    app_logger._nutients_logging_configured = True  # type: ignore[attr-defined]
    app_logger.info(
        "Application logging configured",
        extra={"event": "app.logging_configured", "log_dir": str(log_dir)},
    )

    return {"app": app_logger, "auth": auth_logger, "query": query_logger}
