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


class FakeColumn:
    """Simple column wrapper that proxies widget calls to FakeStreamlit."""

    def __init__(self, streamlit_module: "FakeStreamlit") -> None:
        """
        Initialize the fake column wrapper.

        Args:
            streamlit_module: Parent fake Streamlit module.
        """
        self._streamlit_module = streamlit_module

    def __enter__(self) -> "FakeColumn":
        """Allow usage with `with` blocks for layout sections."""
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        """
        Exit a `with` block.

        Args:
            exc_type: Exception type.
            exc_val: Exception value.
            exc_tb: Traceback object.

        Returns:
            False to propagate exceptions.
        """
        _ = (exc_type, exc_val, exc_tb)
        return False

    def toggle(
        self,
        label: str,
        key: str | None = None,
        value: bool = False,
        label_visibility: str | None = None,
    ) -> bool:
        """
        Proxy toggle calls to the parent module.

        Args:
            label: Toggle label.
            key: Session-state key.
            value: Default value.
            label_visibility: Label visibility option.

        Returns:
            Toggle state.
        """
        return self._streamlit_module.toggle(
            label,
            key=key,
            value=value,
            label_visibility=label_visibility,
        )

    def number_input(
        self,
        label: str,
        min_value: float,
        max_value: float,
        key: str | None = None,
        value: float | None = None,
        on_change: object | None = None,
        args: tuple[object, ...] | None = None,
        disabled: bool = False,
    ) -> float:
        """
        Proxy number input calls to the parent module.

        Args:
            label: Number input label.
            min_value: Minimum allowed value.
            max_value: Maximum allowed value.
            key: Session-state key.
            value: Default value.
            on_change: Optional callback.
            args: Callback arguments.
            disabled: Whether the widget is disabled.

        Returns:
            Number input value.
        """
        return self._streamlit_module.number_input(
            label,
            min_value=min_value,
            max_value=max_value,
            key=key,
            value=value,
            on_change=on_change,
            args=args,
            disabled=disabled,
        )

    def slider(
        self,
        label: str,
        min_value: float,
        max_value: float,
        value: tuple[float, float] | float,
        key: str | None = None,
        on_change: object | None = None,
        args: tuple[object, ...] | None = None,
        disabled: bool = False,
    ) -> tuple[float, float] | float:
        """
        Proxy slider calls to the parent module.

        Args:
            label: Slider label.
            min_value: Minimum allowed value.
            max_value: Maximum allowed value.
            value: Default slider value.
            key: Session-state key.
            on_change: Optional callback.
            args: Callback arguments.
            disabled: Whether the widget is disabled.

        Returns:
            Slider value.
        """
        return self._streamlit_module.slider(
            label,
            min_value=min_value,
            max_value=max_value,
            value=value,
            key=key,
            on_change=on_change,
            args=args,
            disabled=disabled,
        )

    def write(self, message: object) -> None:
        """
        Proxy writes to the parent module.

        Args:
            message: Text or value to display.
        """
        self._streamlit_module.write(message)


class FakeForm:
    """Simple form wrapper that proxies form widgets to FakeStreamlit."""

    def __init__(self, streamlit_module: "FakeStreamlit") -> None:
        """
        Initialize the fake form wrapper.

        Args:
            streamlit_module: Parent fake Streamlit module.
        """
        self._streamlit_module = streamlit_module

    def __enter__(self) -> "FakeForm":
        """Allow usage with `with` blocks for forms."""
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        """
        Exit a form `with` block.

        Args:
            exc_type: Exception type.
            exc_val: Exception value.
            exc_tb: Traceback object.

        Returns:
            False to propagate exceptions.
        """
        _ = (exc_type, exc_val, exc_tb)
        return False

    def text_input(self, label: str, type: str | None = None) -> str:
        """
        Proxy text input calls to the parent module.

        Args:
            label: Input label.
            type: Optional input type.

        Returns:
            Text input value.
        """
        return self._streamlit_module.text_input(label, type=type)

    def form_submit_button(self, label: str) -> bool:
        """
        Proxy form submit calls to the parent module.

        Args:
            label: Submit button label.

        Returns:
            Submit state.
        """
        return self._streamlit_module.form_submit_button(label)


class FakeStreamlit(types.ModuleType):
    """Small Streamlit replacement for importing the frontend app module."""

    def __init__(self) -> None:
        """Initialize fake Streamlit state and call trackers."""
        super().__init__("streamlit")
        self.session_state = SessionState(authenticated=True)
        self.connection_result = pd.DataFrame()
        self.connection_instance = FakeConnection(self.connection_result)
        self.text_inputs: dict[str, str] = {}
        self.number_values: dict[str, float] = {}
        self.toggle_values: dict[str, bool] = {}
        self.slider_values: dict[str, tuple[float, float] | float] = {}
        self.button_values: list[bool] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.writes: list[object] = []
        self.number_input_calls: list[dict[str, object]] = []
        self.slider_calls: list[dict[str, object]] = []
        self.secrets: dict[str, object] = {"passwords": {}}
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

    def button(self, label: str, disabled: bool = False) -> bool:
        """Return the next configured button state.

        Args:
            label: Button label.
            disabled: Whether the button is disabled.

        Returns:
            Next boolean state, or False when no value is queued.
        """
        _ = label
        if disabled:
            return False
        if self.button_values:
            return self.button_values.pop(0)
        return False

    def form(self, key: str, clear_on_submit: bool = False) -> FakeForm:
        """
        Return a fake form context manager.

        Args:
            key: Form key.
            clear_on_submit: Whether Streamlit would clear widgets after submit.

        Returns:
            Fake form wrapper.
        """
        _ = (key, clear_on_submit)
        return FakeForm(self)

    def form_submit_button(self, label: str) -> bool:
        """
        Return the next configured form submit state.

        Args:
            label: Submit button label.

        Returns:
            Next boolean state, or False when no value is queued.
        """
        return self.button(label)

    def toggle(
        self,
        label: str,
        key: str | None = None,
        value: bool = False,
        label_visibility: str | None = None,
    ) -> bool:
        """
        Return configured toggle value.

        Args:
            label: Toggle label.
            key: Session-state key.
            value: Default value.
            label_visibility: Label visibility option.

        Returns:
            Toggle state.
        """
        _ = (label, label_visibility)
        resolved_key = key or label
        if resolved_key in self.toggle_values:
            resolved_value = self.toggle_values[resolved_key]
        elif resolved_key in self.session_state:
            resolved_value = bool(self.session_state[resolved_key])
        else:
            resolved_value = value
        self.session_state[resolved_key] = resolved_value
        return resolved_value

    def number_input(
        self,
        label: str,
        min_value: float,
        max_value: float,
        key: str | None = None,
        value: float | None = None,
        on_change: object | None = None,
        args: tuple[object, ...] | None = None,
        disabled: bool = False,
    ) -> float:
        """
        Return configured numeric input value.

        Args:
            label: Input label.
            min_value: Minimum allowed value.
            max_value: Maximum allowed value.
            key: Session-state key.
            value: Default value.
            on_change: Optional callback.
            args: Optional callback arguments.
            disabled: Whether the widget is disabled.

        Returns:
            Numeric value.
        """
        _ = (label, min_value, max_value, on_change, args)
        resolved_key = key or label

        self.number_input_calls.append({"key": resolved_key, "disabled": disabled})

        if resolved_key in self.number_values:
            resolved_value = float(self.number_values[resolved_key])
        elif resolved_key in self.session_state:
            resolved_value = float(self.session_state[resolved_key])
        elif value is not None:
            resolved_value = float(value)
        else:
            resolved_value = float(min_value)

        self.session_state[resolved_key] = resolved_value
        return resolved_value

    def error(self, message: str) -> None:
        """Record an error message.

        Args:
            message: Error text displayed by the app.
        """
        self.errors.append(message)

    def success(self, message: str) -> None:
        """Accept success messages from the app.

        Args:
            message: Success text displayed by the app.
        """
        _ = message

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

    def slider(
        self,
        label: str,
        min_value: float,
        max_value: float,
        value: tuple[float, float] | float,
        key: str | None = None,
        on_change: object | None = None,
        args: tuple[object, ...] | None = None,
        disabled: bool = False,
    ) -> tuple[float, float] | float:
        """Return the provided default slider value.

        Args:
            label: Slider label.
            min_value: Minimum slider value.
            max_value: Maximum slider value.
            value: Default slider value.
            key: Session-state key.
            on_change: Optional callback.
            args: Optional callback arguments.
            disabled: Whether the widget is disabled.

        Returns:
            The default or configured slider value.
        """
        _ = (label, min_value, max_value, on_change, args)
        resolved_key = key or label

        self.slider_calls.append({"key": resolved_key, "disabled": disabled})

        if resolved_key in self.slider_values:
            resolved_value = self.slider_values[resolved_key]
        elif resolved_key in self.session_state:
            resolved_value = self.session_state[resolved_key]
        else:
            resolved_value = value

        self.session_state[resolved_key] = resolved_value
        return resolved_value

    def warning(self, message: str) -> None:
        """
        Record a warning message.

        Args:
            message: Warning text displayed by the app.
        """
        self.warnings.append(message)

    def write(self, message: object) -> None:
        """
        Record text output.

        Args:
            message: Text or value written by the app.
        """
        self.writes.append(message)

    def markdown(self, body: str) -> None:
        """
        Accept markdown output.

        Args:
            body: Markdown body.
        """
        _ = body

    def columns(self, spec: list[float]) -> list[FakeColumn]:
        """
        Return fake column wrappers.

        Args:
            spec: Width ratios for generated columns.

        Returns:
            List of fake columns.
        """
        return [FakeColumn(self) for _ in spec]

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
