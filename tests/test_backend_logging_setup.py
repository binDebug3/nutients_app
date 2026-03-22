"""Unit tests for backend logging configuration."""

from __future__ import annotations

import logging


class FakeRotatingFileHandler(logging.Handler):
    """Simple handler that mimics the RotatingFileHandler constructor."""

    def __init__(
        self,
        filename: object,
        maxBytes: int,
        backupCount: int,
        encoding: str,
    ) -> None:
        """Store construction arguments for later inspection.

        Args:
            filename: Target log file path.
            maxBytes: Maximum bytes before rotation.
            backupCount: Number of backup log files.
            encoding: Text encoding.
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


def test_configure_backend_logging_adds_handlers_once(
    load_backend_module: object,
    monkeypatch: object,
    tmp_path: object,
) -> None:
    """Configure backend logging once and reuse handlers on subsequent calls."""
    module = load_backend_module("logging_setup")
    module.__file__ = str(tmp_path / "repo" / "src" / "backend" / "logging_setup.py")
    monkeypatch.setattr(module, "RotatingFileHandler", FakeRotatingFileHandler)

    base_logger = logging.getLogger(module.BASE_LOGGER_NAME)
    for handler in list(base_logger.handlers):
        base_logger.removeHandler(handler)
        handler.close()

    if hasattr(base_logger, "_nutients_backend_logging_configured"):
        delattr(base_logger, "_nutients_backend_logging_configured")

    logger_one = module.configure_backend_logging("compare")
    logger_two = module.configure_backend_logging("join")

    assert logger_one.name == "nutients_app.backend.compare"
    assert logger_two.name == "nutients_app.backend.join"
    assert logger_one.propagate is True
    assert len(base_logger.handlers) == 2
    assert (tmp_path / "repo" / "logs").exists()
