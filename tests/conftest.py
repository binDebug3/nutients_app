"""Shared pytest fixtures and import helpers for nutrients_app tests."""

from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "src" / "backend"
FRONTEND_APP_DIR = REPO_ROOT / "src" / "frontend" / "app"
NEON_DIR = BACKEND_DIR / "neon"


class SessionState(dict):
    """Dictionary-backed object that mimics Streamlit session state."""

    def __getattr__(self, name: str) -> object:
        """Read state values through attribute access.

        Args:
            name: Attribute name to look up.

        Returns:
            Stored value.

        Raises:
            AttributeError: If the key is not present.
        """
        if name not in self:
            raise AttributeError(name)
        return self[name]

    def __setattr__(self, name: str, value: object) -> None:
        """Write state values through attribute access.

        Args:
            name: Attribute name to store.
            value: Value to store.
        """
        self[name] = value


class FakeConnection:
    """Minimal fake Streamlit SQL connection."""

    def __init__(self, result: pd.DataFrame | None = None) -> None:
        """Initialize the fake connection.

        Args:
            result: DataFrame returned by query calls.
        """
        self.result = result if result is not None else pd.DataFrame()
        self.queries: list[str] = []

    def query(self, sql_query: str) -> pd.DataFrame:
        """Record and return a canned SQL result.

        Args:
            sql_query: Query string provided by the app.

        Returns:
            The configured result DataFrame.
        """
        self.queries.append(sql_query)
        return self.result


class FakeStreamlit(types.ModuleType):
    """Small Streamlit replacement for importing the frontend app module."""

    def __init__(self) -> None:
        """Initialize fake Streamlit state and call trackers."""
        super().__init__("streamlit")
        self.session_state = SessionState(authenticated=True)
        self.connection_result = pd.DataFrame()
        self.connection_instance = FakeConnection(self.connection_result)
        self.text_inputs: dict[str, str] = {}
        self.button_values: list[bool] = []
        self.errors: list[str] = []
        self.tables: list[pd.DataFrame] = []
        self.titles: list[str] = []
        self.subheaders: list[str] = []
        self.rerun_called = False
        self.stop_called = False

    def subheader(self, text: str) -> None:
        """Record a subheader call.

        Args:
            text: Subheader text.
        """
        self.subheaders.append(text)

    def text_input(self, label: str, type: str | None = None) -> str:
        """Return a configured input value.

        Args:
            label: Input label.
            type: Optional input type.

        Returns:
            Configured value for the label.
        """
        _ = type
        return self.text_inputs.get(label, "")

    def button(self, label: str) -> bool:
        """Return the next configured button state.

        Args:
            label: Button label.

        Returns:
            Next boolean state, or False when no value is queued.
        """
        _ = label
        if self.button_values:
            return self.button_values.pop(0)
        return False

    def error(self, message: str) -> None:
        """Record an error message.

        Args:
            message: Error text displayed by the app.
        """
        self.errors.append(message)

    def rerun(self) -> None:
        """Record that a rerun was requested."""
        self.rerun_called = True

    def stop(self) -> None:
        """Record that Streamlit stop was requested."""
        self.stop_called = True

    def connection(self, name: str, type: str) -> FakeConnection:
        """Return the fake SQL connection.

        Args:
            name: Connection name.
            type: Connection type.

        Returns:
            Fake connection instance.
        """
        _ = (name, type)
        self.connection_instance = FakeConnection(self.connection_result)
        return self.connection_instance

    def title(self, text: str) -> None:
        """Record title text.

        Args:
            text: Title text.
        """
        self.titles.append(text)

    def slider(self, label: str, minimum: int, maximum: int, default: int) -> int:
        """Return the provided default slider value.

        Args:
            label: Slider label.
            minimum: Minimum slider value.
            maximum: Maximum slider value.
            default: Default slider value.

        Returns:
            The default slider value.
        """
        _ = (label, minimum, maximum)
        return default

    def table(self, frame: pd.DataFrame) -> None:
        """Record a displayed table.

        Args:
            frame: DataFrame rendered by the app.
        """
        self.tables.append(frame)


def _clear_logger(name: str) -> None:
    """Remove handlers and custom flags from a named logger.

    Args:
        name: Logger name to reset.
    """
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    for attribute in [
        "_nutients_backend_logging_configured",
        "_nutients_logging_configured",
    ]:
        if hasattr(logger, attribute):
            delattr(logger, attribute)

    logger.propagate = True
    logger.setLevel(logging.NOTSET)


@pytest.fixture(autouse=True)
def reset_named_loggers() -> Iterator[None]:
    """Reset app loggers before and after each test."""
    logger_names = [
        "nutients_app.backend",
        "nutients_app",
        "nutients_app.auth",
        "nutients_app.query",
        "nutients_app.backend.neon.init_db",
    ]
    for logger_name in logger_names:
        _clear_logger(logger_name)

    yield

    for logger_name in logger_names:
        _clear_logger(logger_name)


@pytest.fixture
def load_module() -> object:
    """Provide a helper to import modules directly from file paths."""

    def _load_module(
        module_name: str,
        file_path: Path,
        prepend_paths: Iterable[Path] | None = None,
        clear_modules: Iterable[str] | None = None,
        injected_modules: dict[str, types.ModuleType] | None = None,
    ) -> types.ModuleType:
        """Import a module from a file with temporary import adjustments.

        Args:
            module_name: Unique module name to register for the import.
            file_path: Source file to import.
            prepend_paths: Paths to temporarily add to sys.path.
            clear_modules: Existing module names to remove before import.
            injected_modules: Temporary module objects to insert into sys.modules.

        Returns:
            Imported module object.
        """
        previous_sys_path = list(sys.path)
        previous_modules: dict[str, types.ModuleType | None] = {}

        try:
            for name in clear_modules or []:
                sys.modules.pop(name, None)

            for name, module in (injected_modules or {}).items():
                previous_modules[name] = sys.modules.get(name)
                sys.modules[name] = module

            for path in reversed([str(path_item) for path_item in prepend_paths or []]):
                if path not in sys.path:
                    sys.path.insert(0, path)

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            assert spec is not None
            assert spec.loader is not None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
        finally:
            sys.path[:] = previous_sys_path
            for name, previous_module in previous_modules.items():
                if previous_module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous_module

    return _load_module


@pytest.fixture
def load_backend_module(load_module: object) -> object:
    """Provide a helper for importing backend modules."""

    def _load_backend_module(module_stem: str) -> types.ModuleType:
        """Import a backend module by file stem.

        Args:
            module_stem: File stem without the `.py` suffix.

        Returns:
            Imported module object.
        """
        return load_module(
            f"test_backend_{module_stem}",
            BACKEND_DIR / f"{module_stem}.py",
            prepend_paths=[BACKEND_DIR],
            clear_modules=["logging_setup"],
        )

    return _load_backend_module


@pytest.fixture
def fake_streamlit() -> FakeStreamlit:
    """Provide a reusable fake Streamlit module."""
    return FakeStreamlit()


@pytest.fixture
def frontend_logging_module() -> types.ModuleType:
    """Provide a fake frontend logging_setup module for app imports."""
    module = types.ModuleType("logging_setup")
    module.configure_app_logging = lambda repo_root: {
        "app": logging.getLogger("nutients_app"),
        "auth": logging.getLogger("nutients_app.auth"),
        "query": logging.getLogger("nutients_app.query"),
    }
    return module
