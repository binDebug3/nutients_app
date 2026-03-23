"""Streamlit frontend for nutrient filtering and food lookup."""

import time
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

from auth_service import AuthService
from auth_store import create_user, get_user_password_hash, password_matches
from filters_ui import FilterPanel
from logging_setup import configure_app_logging
from models import DIETARY_TOGGLE_LABELS, NUTRIENT_SPECS, NutrientSpec
from optimize import OptimizationResult, Simplex, SliderBounds
from query_builder import FoodQueryBuilder
from recommendation_view import RecommendationView
from state_manager import NutrientStateManager


APP_PATH = Path(__file__).resolve()
APP_DIR = APP_PATH.parent
REPO_ROOT = APP_PATH.parents[3]
USER_DB_PATH = APP_DIR / ".streamlit" / "users.db"
LOGGER_MAP = configure_app_logging(REPO_ROOT)
log = LOGGER_MAP["app"]
auth_log = LOGGER_MAP["auth"]
query_log = LOGGER_MAP["query"]

STATE_MANAGER = NutrientStateManager(st, log)
FILTER_PANEL = FilterPanel(st, log, STATE_MANAGER)
QUERY_BUILDER = FoodQueryBuilder(query_log)
AUTH_SERVICE = AuthService(st, auth_log, log, USER_DB_PATH)
RECOMMENDATION_VIEW = RecommendationView(st, log)

# Kept for test compatibility that introspects these imported symbols from app.py.
_ = (create_user, get_user_password_hash, password_matches)


def _any_key(spec: NutrientSpec) -> str:
    """
    Return the session-state key for the Any toggle.

    Args:
        spec: Nutrient specification.

    Returns:
        Session-state key.
    """
    return STATE_MANAGER.any_key(spec)


def _slider_key(spec: NutrientSpec) -> str:
    """
    Return the session-state key for the range slider.

    Args:
        spec: Nutrient specification.

    Returns:
        Session-state key.
    """
    return STATE_MANAGER.slider_key(spec)


def _min_key(spec: NutrientSpec) -> str:
    """
    Return the session-state key for the min input.

    Args:
        spec: Nutrient specification.

    Returns:
        Session-state key.
    """
    return STATE_MANAGER.min_key(spec)


def _max_key(spec: NutrientSpec) -> str:
    """
    Return the session-state key for the max input.

    Args:
        spec: Nutrient specification.

    Returns:
        Session-state key.
    """
    return STATE_MANAGER.max_key(spec)


def _sync_slider_from_inputs(spec: NutrientSpec) -> None:
    """
    Keep slider aligned with manual min and max inputs.

    Args:
        spec: Nutrient specification.
    """
    STATE_MANAGER.sync_slider_from_inputs(spec)


def _build_slider_bounds(specs: List[NutrientSpec]) -> SliderBounds:
    """
    Build optimization bounds from current nutrient slider controls.

    Args:
        specs: Nutrient specifications.

    Returns:
        Dataclass containing per-nutrient min and max limits.
    """
    return STATE_MANAGER.build_slider_bounds(specs)


def _build_where_clauses(specs: List[NutrientSpec]) -> List[str]:
    """
    Build SQL filter clauses.

    Args:
        specs: Nutrient specifications.

    Returns:
        SQL predicate fragments.
    """
    return QUERY_BUILDER.build_where_clauses(specs)


def _build_food_query(specs: List[NutrientSpec]) -> str:
    """
    Build the SQL query for the food table.

    Args:
        specs: Nutrient specifications.

    Returns:
        SQL query string.
    """
    return QUERY_BUILDER.build_food_query(specs)


def _render_dietary_toggles() -> Dict[str, bool]:
    """
    Render top-of-page dietary preference toggles.

    Returns:
        Mapping of dietary preference keys to enabled states.
    """
    _ = DIETARY_TOGGLE_LABELS
    return FILTER_PANEL.render_dietary_toggles(NUTRIENT_SPECS)


def _render_nutrient_filter(spec: NutrientSpec) -> bool:
    """
    Render one nutrient filter row and return invalid-state status.

    Args:
        spec: Nutrient specification.

    Returns:
        True when the filter has an invalid min/max pair.
    """
    return FILTER_PANEL.render_nutrient_filter(spec)


def _render_recommendation_summary(
    result: OptimizationResult,
    recommended_row_count: int,
    dietary_preferences: Dict[str, bool],
) -> None:
    """
    Render high-level recommendation metrics and active dietary preferences.

    Args:
        result: Optimization result from the solver.
        recommended_row_count: Number of selected food rows.
        dietary_preferences: Dietary toggle states.
    """
    RECOMMENDATION_VIEW.render_recommendation_summary(
        result,
        recommended_row_count,
        dietary_preferences,
    )


def _render_recommended_foods(
    df: object,
    result: OptimizationResult,
    dietary_preferences: Dict[str, bool],
    active_nutrient_columns: List[str],
    bounds: SliderBounds,
) -> None:
    """
    Render ranked food recommendations with an expressive results layout.

    Args:
        df: Candidate foods DataFrame returned by SQL query.
        result: Optimization result from the solver.
        dietary_preferences: Dietary toggle states.
        active_nutrient_columns: Nutrient columns where Any is off.
        bounds: Active nutrient bounds from current filter state.
    """
    RECOMMENDATION_VIEW.render_recommended_foods(
        df,
        result,
        dietary_preferences,
        active_nutrient_columns=active_nutrient_columns,
        nutrient_bounds=bounds,
    )


def credentials_match(username: str, password: str) -> bool:
    """
    Validate a username and password pair.

    Args:
        username: The username entered by the user.
        password: The password entered by the user.

    Returns:
        True when credentials are accepted.
    """
    AUTH_SERVICE.user_db_path = USER_DB_PATH
    return AUTH_SERVICE.credentials_match(username, password)


def create_account(username: str, password: str) -> bool:
    """
    Create a new user account in the local credential store.

    Args:
        username: Requested username.
        password: Requested password.

    Returns:
        True when the account is created successfully.
    """
    AUTH_SERVICE.user_db_path = USER_DB_PATH
    return AUTH_SERVICE.create_account(username, password)


def check_password() -> bool:
    """
    Validate user credentials using username and password.

    Returns:
        Whether the user has successfully authenticated.
    """
    log.info("Running login gate check", extra={"event": "auth.gate_check"})
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated:
        return True

    st.subheader("Login or Sign Up")
    with st.form("auth_login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_col, signup_col = st.columns([1, 1])
        with login_col:
            login_submitted = st.form_submit_button("Login")
        with signup_col:
            signup_submitted = st.form_submit_button("Sign Up")

    normalized_username = AUTH_SERVICE.normalize_username(username)
    log.info(
        "Auth form submit state",
        extra={
            "event": "auth.form_submit_state",
            "username_len": len(username),
            "password_len": len(password),
            "login_submitted": login_submitted,
            "signup_submitted": signup_submitted,
        },
    )

    if login_submitted:
        if credentials_match(username=username, password=password):
            st.session_state.authenticated = True
            st.session_state.current_username = normalized_username
            st.rerun()
        else:
            st.error("Invalid username or password")
        return False

    if signup_submitted:
        if create_account(username=username, password=password):
            st.session_state.authenticated = True
            st.session_state.current_username = normalized_username
            st.rerun()
        return False
    return False


def _run_food_query(
    conn: object, dietary_preferences: Dict[str, bool]
) -> Optional[object]:
    """
    Execute food query and return dataframe or None when failed.

    Args:
        conn: Streamlit SQL connection.
        dietary_preferences: Dietary toggle states.

    Returns:
        DataFrame when query succeeds, otherwise None.
    """
    query_log.info(
        "Food query started",
        extra={
            "event": "db.query_started",
            "active_dietary_filters": sum(
                int(enabled) for enabled in dietary_preferences.values()
            ),
        },
    )
    started_at = time.perf_counter()
    try:
        query = _build_food_query(NUTRIENT_SPECS)
        df = conn.query(query)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        query_log.info(
            "Food query succeeded",
            extra={
                "event": "db.query_succeeded",
                "duration_ms": duration_ms,
                "row_count": len(df),
            },
        )
        return df
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        query_log.exception(
            "Food query failed",
            extra={"event": "db.query_failed", "duration_ms": duration_ms},
        )
        st.error("Unable to fetch foods. Please try again.")
        return None


def _run_optimization(
    df: object,
    bounds: SliderBounds,
    max_servings_per_food: float,
) -> Optional[OptimizationResult]:
    """
    Run the optimizer with current slider bounds.

    Args:
        df: Food candidate dataframe.

    Returns:
        Optimization result, or None when optimization fails.
    """
    try:
        log.info(
            "Starting optimization",
            extra={
                "event": "optimizer.started",
                "max_servings_per_food": max_servings_per_food,
            },
        )
        optimizer = Simplex(
            df,
            bounds,
            max_servings_per_food=max_servings_per_food,
        )
        return optimizer.run()
    except Exception:
        query_log.exception(
            "Optimization failed",
            extra={"event": "optimizer.failed", "row_count": len(df)},
        )
        st.error("Unable to compute recommendations. Showing candidate foods instead.")
        st.table(df)
        return None


def run_app() -> None:
    """
    Execute the Streamlit nutrient finder workflow.
    """
    if not check_password():
        st.stop()
    conn = st.connection("postgresql", type="sql")
    st.title("Nutrient Goal Finder")
    dietary_preferences = _render_dietary_toggles()

    max_servings_per_food = st.selectbox(
        "Max servings per food:",
        options=[round(value * 0.5, 1) for value in range(1, 21)],
        index=7,
        key="max_servings_per_food",
    )

    invalid_ranges = FILTER_PANEL.render_all_nutrients(NUTRIENT_SPECS)
    has_invalid_ranges = any(invalid_ranges.values())
    if not st.button("Find Foods", disabled=has_invalid_ranges):
        return

    log.info(
        "Find Foods button clicked",
        extra={
            "event": "find_foods.clicked",
            "max_servings_per_food": max_servings_per_food,
        },
    )

    bounds = _build_slider_bounds(NUTRIENT_SPECS)
    active_nutrient_columns = [
        spec.db_column
        for spec in NUTRIENT_SPECS
        if any(
            value is not None
            for value in (
                bounds.minimums.get(spec.db_column),
                bounds.maximums.get(spec.db_column),
            )
        )
    ]

    df = _run_food_query(conn, dietary_preferences)
    if df is None:
        st.stop()
    if len(df) == 0:
        st.warning("No foods matched the selected filters.")
        st.stop()

    with st.spinner("Computing recommendations..."):
        optimization_result = _run_optimization(
            df,
            bounds,
            max_servings_per_food,
        )
    if optimization_result is not None:
        log.info(
            "Optimization completed",
            extra={
                "event": "optimization.completed",
                "selected_foods_count": len(optimization_result.selected_foods),
            },
        )
        _render_recommended_foods(
            df,
            optimization_result,
            dietary_preferences,
            active_nutrient_columns,
            bounds,
        )


run_app()
