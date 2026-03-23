"""Unit tests for the Streamlit frontend app."""

from __future__ import annotations

import sqlite3
from types import ModuleType

import pandas as pd

from conftest import FRONTEND_APP_DIR


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


def test_credentials_match_accepts_hashed_secret_credentials(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Authenticate when the username exists in secrets with a hashed password."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_hashed_secret_credentials",
    )
    hashed_password = module.create_user.__globals__["hash_password"]("secret")
    fake_streamlit.secrets = {"passwords": {"alice": hashed_password}}

    result = module.credentials_match("alice", "secret")

    assert result is True


def test_credentials_match_accepts_legacy_plaintext_secret_credentials(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Authenticate when the username exists in secrets with a legacy plain-text value."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_plaintext_secret_credentials",
    )
    fake_streamlit.secrets = {"passwords": {"alice": "secret"}}

    assert module.credentials_match("alice", "secret") is True


def test_create_account_persists_hashed_local_credentials(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
    tmp_path: object,
) -> None:
    """Persist new accounts to the local credential store with hashed passwords."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_create_account",
    )
    module.USER_DB_PATH = tmp_path / "users.db"

    assert module.create_account("alice", "secret") is True
    assert module.credentials_match("alice", "secret") is True

    with sqlite3.connect(module.USER_DB_PATH) as connection:
        stored_password_hash = connection.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            ("alice",),
        ).fetchone()[0]

    assert stored_password_hash != "secret"
    assert stored_password_hash.startswith("pbkdf2_sha256$")


def test_check_password_sets_authenticated_and_requests_rerun_on_login(
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
    module.st.button_values = [True, False]
    monkeypatch.setattr(module, "credentials_match", lambda username, password: True)

    result = module.check_password()

    assert result is False
    assert module.st.session_state.authenticated is True
    assert module.st.session_state.current_username == "alice"
    assert module.st.rerun_called is True


def test_check_password_sets_authenticated_and_requests_rerun_on_signup(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
    monkeypatch: object,
) -> None:
    """Set the authenticated flag and trigger rerun when signup succeeds."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_check_password_signup",
    )
    module.st.session_state.authenticated = False
    module.st.text_inputs = {"Username": "alice", "Password": "secret"}
    module.st.button_values = [False, True]
    monkeypatch.setattr(module, "create_account", lambda username, password: True)

    result = module.check_password()

    assert result is False
    assert module.st.session_state.authenticated is True
    assert module.st.session_state.current_username == "alice"
    assert module.st.rerun_called is True


def test_check_password_authenticates_with_form_submit(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
    monkeypatch: object,
) -> None:
    """Authenticate through form submission to support Enter-key login."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_check_password_form_submit",
    )
    module.st.session_state.authenticated = False
    module.st.text_inputs = {"Username": "alice", "Password": "secret"}
    module.st.button_values = [True]
    monkeypatch.setattr(module, "credentials_match", lambda username, password: True)

    result = module.check_password()

    assert result is False
    assert module.st.session_state.authenticated is True
    assert module.st.session_state.current_username == "alice"
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


def test_invalid_range_shows_warning_and_disables_query_submit(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Show warning text and skip query when an active nutrient range is invalid."""
    fake_streamlit.button_values = [True]
    fake_streamlit.toggle_values = {"protein_any": False}
    fake_streamlit.number_values = {
        "protein_min": 30.0,
        "protein_max": 10.0,
    }

    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_invalid_range_submit",
    )

    assert module.st.connection_instance.queries == []
    assert any(
        "Protein: min must be less than max." in warning
        for warning in module.st.warnings
    )


def test_manual_input_updates_slider_state_for_valid_values(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Sync the slider tuple when manual min and max inputs change to a valid range."""
    module = _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_manual_sync",
    )
    protein_spec = next(spec for spec in module.NUTRIENT_SPECS if spec.key == "protein")

    module.st.session_state[module._min_key(protein_spec)] = 15.0
    module.st.session_state[module._max_key(protein_spec)] = 55.0
    module._sync_slider_from_inputs(protein_spec)

    assert module.st.session_state[module._slider_key(protein_spec)] == (15.0, 55.0)


def test_any_toggle_disables_manual_nutrient_controls(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Disable min, max, and slider controls when the Any toggle is enabled."""
    _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_any_disables_manual_controls",
    )

    protein_control_calls = [
        call
        for call in fake_streamlit.number_input_calls
        if call["key"] in {"protein_min", "protein_max"}
    ]
    protein_slider_calls = [
        call for call in fake_streamlit.slider_calls if call["key"] == "protein_slider"
    ]

    assert len(protein_control_calls) == 2
    assert all(bool(call["disabled"]) for call in protein_control_calls)
    assert len(protein_slider_calls) == 1
    assert bool(protein_slider_calls[0]["disabled"]) is True


def test_manual_nutrient_controls_enabled_when_any_toggle_is_off(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Keep min, max, and slider controls enabled when the Any toggle is disabled."""
    fake_streamlit.toggle_values = {"protein_any": False}

    _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_manual_controls_enabled",
    )

    protein_control_calls = [
        call
        for call in fake_streamlit.number_input_calls
        if call["key"] in {"protein_min", "protein_max"}
    ]
    protein_slider_calls = [
        call for call in fake_streamlit.slider_calls if call["key"] == "protein_slider"
    ]

    assert len(protein_control_calls) == 2
    assert all(bool(call["disabled"]) is False for call in protein_control_calls)
    assert len(protein_slider_calls) == 1
    assert bool(protein_slider_calls[0]["disabled"]) is False


def test_top_dietary_preference_toggles_are_initialized(
    load_module: object,
    fake_streamlit: ModuleType,
    frontend_logging_module: ModuleType,
) -> None:
    """Render top dietary toggles and initialize their session-state keys."""
    _load_frontend_app(
        load_module,
        fake_streamlit,
        frontend_logging_module,
        "test_frontend_app_top_dietary_toggles",
    )

    assert "dietary_gluten_free" in fake_streamlit.session_state
    assert "dietary_vegan" in fake_streamlit.session_state
    assert "dietary_vegetarian" in fake_streamlit.session_state
    assert "dietary_dairy_free" in fake_streamlit.session_state
    assert "dietary_nut_free" in fake_streamlit.session_state
