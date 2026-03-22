"""Unit tests for the Streamlit frontend app."""

from __future__ import annotations

import io
from types import ModuleType

import pandas as pd

from conftest import FRONTEND_APP_DIR


class FakeLoginPath:
    """Simple fake path object for login credential checks."""

    def __init__(self, exists: bool) -> None:
        """Store whether the path should appear to exist.

        Args:
            exists: Existence result returned by exists().
        """
        self._exists = exists

    def exists(self) -> bool:
        """Return the configured existence flag.

        Returns:
            Whether the fake path exists.
        """
        return self._exists

    def open(self, mode: str, encoding: str) -> io.StringIO:
        """Return a dummy in-memory file handle.

        Args:
            mode: Open mode.
            encoding: File encoding.

        Returns:
            In-memory text stream.
        """
        _ = (mode, encoding)
        return io.StringIO("ignored")


def _load_frontend_app(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
    module_name: str,
) -> ModuleType:
    """Import the frontend app with fake Streamlit and logging modules.

    Args:
        load_module: Shared file-based module loader fixture.
        fake_streamlit: Fake Streamlit module.
        frontend_logging_module: Fake frontend logging_setup module.
        module_name: Unique module name for the import.

    Returns:
        Imported frontend app module.
    """
    return load_module(
        module_name,
        FRONTEND_APP_DIR / "app.py",
        prepend_paths=[FRONTEND_APP_DIR],
        clear_modules=["logging_setup", "streamlit"],
        injected_modules={
            "streamlit": fake_streamlit,
            "logging_setup": frontend_logging_module,
        },
    )


def test_credentials_match_returns_true_for_exact_match(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
    monkeypatch: object,
) -> None:
    """Authenticate when the username exists and the password matches exactly."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_credentials_success",
    )
    module.LOGIN_JSON_PATH = FakeLoginPath(True)
    monkeypatch.setattr(module.json, "load", lambda handle: {"alice": "secret"})

    result = module.credentials_match("alice", "secret")

    assert result is True


def test_credentials_match_rejects_missing_credentials_file(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Return False when the login mapping file does not exist."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_credentials_missing_file",
    )
    module.LOGIN_JSON_PATH = FakeLoginPath(False)

    assert module.credentials_match("alice", "secret") is False


def test_check_password_sets_authenticated_and_requests_rerun(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
    monkeypatch: object,
) -> None:
    """Set the authenticated flag and trigger rerun when login succeeds."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_check_password",
    )
    module.st.session_state.authenticated = False
    module.st.text_inputs = {"Username": "alice", "Password": "secret"}
    module.st.button_values = [True]
    monkeypatch.setattr(module, "credentials_match", lambda username, password: True)

    result = module.check_password()

    assert result is False
    assert module.st.session_state.authenticated is True
    assert module.st.rerun_called is True


def test_query_button_runs_and_displays_results(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Import the app with the search button enabled and verify the query result table."""
    fake_streamlit.button_values = [True]
    fake_streamlit.connection_result = pd.DataFrame(
        {
            "food_name": ["Greek Yogurt"],
            "serving_size": ["1 cup"],
            "Protein": [20.0],
            "Carbohydrate, by difference": [8.0],
        }
    )

    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_query",
    )

    assert module.st.connection_instance.queries
    assert len(module.st.tables) == 1
    assert module.st.tables[0]["food_name"].tolist() == ["Greek Yogurt"]
