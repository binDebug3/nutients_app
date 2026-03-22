"""Unit tests for frontend logging setup."""

from __future__ import annotations

import json
import logging

from conftest import FRONTEND_APP_DIR


class FakeRotatingFileHandler(logging.Handler):
    """Simple rotating handler stand-in for tests."""

    def __init__(
        self,
        filename: object,
        maxBytes: int,
        backupCount: int,
        encoding: str,
    ) -> None:
        """Store constructor arguments.

        Args:
            filename: Target log file.
            maxBytes: Maximum bytes before rotation.
            backupCount: Number of rotated backups.
            encoding: Handler encoding.
        """
        super().__init__()
        self.filename = filename
        self.max_bytes = maxBytes
        self.backup_count = backupCount
        self.encoding = encoding

    def emit(self, record: logging.LogRecord) -> None:
        """Consume log records without writing anywhere.

        Args:
            record: Log record emitted by logging.
        """
        _ = record


def test_json_log_formatter_includes_event_and_custom_fields(
    load_module: object,
) -> None:
    """Format records as JSON with custom extras and event names included."""
    module = load_module(
        "test_frontend_logging_setup",
        FRONTEND_APP_DIR / "logging_setup.py",
        prepend_paths=[FRONTEND_APP_DIR],
        clear_modules=["logging_setup"],
    )
    formatter = module.JsonLogFormatter()
    record = logging.LogRecord(
        name="nutients_app.query",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="query complete",
        args=(),
        exc_info=None,
    )
    record.event = "db.query_succeeded"
    record.row_count = 5

    payload = json.loads(formatter.format(record))

    assert payload["event"] == "db.query_succeeded"
    assert payload["row_count"] == 5
    assert payload["message"] == "query complete"


def test_configure_app_logging_sets_handlers_once(
    load_module: object,
    monkeypatch: object,
    tmp_path: object,
) -> None:
    """Configure app, auth, and query loggers without duplicating handlers."""
    module = load_module(
        "test_frontend_logging_setup_configure",
        FRONTEND_APP_DIR / "logging_setup.py",
        prepend_paths=[FRONTEND_APP_DIR],
        clear_modules=["logging_setup"],
    )
    monkeypatch.setattr(module, "RotatingFileHandler", FakeRotatingFileHandler)

    logger_map_one = module.configure_app_logging(tmp_path)
    logger_map_two = module.configure_app_logging(tmp_path)

    assert sorted(logger_map_one.keys()) == ["app", "auth", "query"]
    assert logger_map_two["app"] is logger_map_one["app"]
    assert len(logger_map_one["app"].handlers) == 2
    assert len(logger_map_one["auth"].handlers) == 1
    assert len(logger_map_one["query"].handlers) == 1
