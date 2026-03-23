"""Streamlit frontend for nutrient filtering and food lookup."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

import streamlit as st

from auth_store import create_user, get_user_password_hash, password_matches
from logging_setup import configure_app_logging


APP_PATH = Path(__file__).resolve()
APP_DIR = APP_PATH.parent
REPO_ROOT = APP_PATH.parents[3]
USER_DB_PATH = APP_DIR / ".streamlit" / "users.db"
LOGGER_MAP = configure_app_logging(REPO_ROOT)
log = LOGGER_MAP["app"]
auth_log = LOGGER_MAP["auth"]
query_log = LOGGER_MAP["query"]

QUERY_LIMIT = 200

DIETARY_TOGGLE_LABELS: List[Tuple[str, str]] = [
    ("gluten_free", "Gluten Free"),
    ("vegan", "Vegan"),
    ("vegetarian", "Vegetarian"),
    ("dairy_free", "Dairy Free"),
    ("nut_free", "Nut-Free"),
]


@dataclass(frozen=True)
class NutrientSpec:
    """
    UI and SQL metadata for a nutrient filter.

    Args:
        key: Stable session-state key prefix.
        label: Display name in the UI.
        db_column: Column name in the `food_nutrition` table.
        bounds: Inclusive min and max allowed values.
        defaults: Default min and max values.
    """

    key: str
    label: str
    db_column: str
    bounds: Tuple[float, float]
    defaults: Tuple[float, float]


NUTRIENT_SPECS: List[NutrientSpec] = [
    NutrientSpec(
        "kilocalories",
        "Kilocalories",
        "kilocalories",
        (0.0, 1200.0),
        (100.0, 700.0),
    ),
    NutrientSpec("fat", "Fat", "fat", (0.0, 100.0), (5.0, 40.0)),
    NutrientSpec(
        "saturated_fat",
        "Saturated Fat",
        "saturated_fat",
        (0.0, 50.0),
        (0.0, 15.0),
    ),
    NutrientSpec(
        "sugar",
        "Sugar",
        "sugar",
        (0.0, 120.0),
        (0.0, 40.0),
    ),
    NutrientSpec("sodium", "Sodium", "sodium", (0.0, 5000.0), (50.0, 1500.0)),
    NutrientSpec(
        "cholesterol",
        "Cholesterol",
        "cholesterol",
        (0.0, 300.0),
        (0.0, 75.0),
    ),
    NutrientSpec("protein", "Protein", "Protein", (0.0, 100.0), (10.0, 60.0)),
    NutrientSpec(
        "carbs",
        "Carbs",
        "carbs",
        (0.0, 150.0),
        (10.0, 80.0),
    ),
    NutrientSpec("iron", "Iron", "iron", (0.0, 45.0), (2.0, 18.0)),
    NutrientSpec("calcium", "Calcium", "calcium", (0.0, 1500.0), (100.0, 900.0)),
    NutrientSpec("potassium", "Potassium", "potassium", (0.0, 5000.0), (200.0, 3500.0)),
    NutrientSpec("fiber", "Fiber", "fiber", (0.0, 80.0), (5.0, 35.0)),
    NutrientSpec("vitamin_a", "Vitamin A", "vitamin_a", (0.0, 3000.0), (100.0, 900.0)),
    NutrientSpec(
        "vitamin_b",
        "Vitamin B",
        "vitamin_b",
        (0.0, 10.0),
        (0.1, 2.0),
    ),
    NutrientSpec(
        "vitamin_c",
        "Vitamin C",
        "vitamin_c",
        (0.0, 2000.0),
        (10.0, 250.0),
    ),
    NutrientSpec(
        "vitamin_d",
        "Vitamin D",
        "vitamin_d",
        (0.0, 200.0),
        (2.0, 50.0),
    ),
    NutrientSpec(
        "vitamin_e",
        "Vitamin E",
        "vitamin_e",
        (0.0, 100.0),
        (1.0, 20.0),
    ),
    NutrientSpec(
        "vitamin_k",
        "Vitamin K",
        "vitamin_k",
        (0.0, 500.0),
        (5.0, 150.0),
    ),
]


def _any_key(spec: NutrientSpec) -> str:
    """
    Return the session-state key for the Any toggle.

    Args:
        spec: Nutrient specification.

    Returns:
        Session-state key.
    """
    log.info(
        "Building Any toggle key", extra={"event": "ui.key.any", "nutrient": spec.key}
    )
    return f"{spec.key}_any"


def _slider_key(spec: NutrientSpec) -> str:
    """
    Return the session-state key for the range slider.

    Args:
        spec: Nutrient specification.

    Returns:
        Session-state key.
    """
    log.info(
        "Building slider key", extra={"event": "ui.key.slider", "nutrient": spec.key}
    )
    return f"{spec.key}_slider"


def _min_key(spec: NutrientSpec) -> str:
    """
    Return the session-state key for the min input.

    Args:
        spec: Nutrient specification.

    Returns:
        Session-state key.
    """
    log.info(
        "Building min input key", extra={"event": "ui.key.min", "nutrient": spec.key}
    )
    return f"{spec.key}_min"


def _max_key(spec: NutrientSpec) -> str:
    """
    Return the session-state key for the max input.

    Args:
        spec: Nutrient specification.

    Returns:
        Session-state key.
    """
    log.info(
        "Building max input key", extra={"event": "ui.key.max", "nutrient": spec.key}
    )
    return f"{spec.key}_max"


def _coerce_float(value: object, fallback: float) -> float:
    """
    Convert a value to float with a fallback.

    Args:
        value: Raw value from session state.
        fallback: Value returned when conversion fails.

    Returns:
        Float value.
    """
    log.info("Coercing numeric value", extra={"event": "ui.value.coerce"})
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _clamp(value: float, lower: float, upper: float) -> float:
    """
    Clamp value into an inclusive range.

    Args:
        value: Value to clamp.
        lower: Inclusive lower bound.
        upper: Inclusive upper bound.

    Returns:
        Clamped value.
    """
    log.info("Clamping numeric value", extra={"event": "ui.value.clamp"})
    return max(lower, min(value, upper))


def _initialize_nutrient_state(spec: NutrientSpec) -> None:
    """
    Seed session state keys for a nutrient filter.

    Args:
        spec: Nutrient specification.
    """
    log.info(
        "Initializing nutrient session state",
        extra={"event": "ui.nutrient.initialize", "nutrient": spec.key},
    )
    any_key = _any_key(spec)
    slider_key = _slider_key(spec)
    min_key = _min_key(spec)
    max_key = _max_key(spec)

    if any_key not in st.session_state:
        st.session_state[any_key] = True

    if slider_key not in st.session_state:
        st.session_state[slider_key] = spec.defaults

    if min_key not in st.session_state:
        st.session_state[min_key] = spec.defaults[0]

    if max_key not in st.session_state:
        st.session_state[max_key] = spec.defaults[1]


def _sync_inputs_from_slider(spec: NutrientSpec) -> None:
    """
    Keep min and max inputs aligned with the slider selection.

    Args:
        spec: Nutrient specification.
    """
    log.info(
        "Syncing numeric inputs from slider",
        extra={"event": "ui.sync.from_slider", "nutrient": spec.key},
    )
    slider_value = st.session_state[_slider_key(spec)]
    slider_min, slider_max = tuple(slider_value)
    st.session_state[_min_key(spec)] = float(slider_min)
    st.session_state[_max_key(spec)] = float(slider_max)


def _sync_slider_from_inputs(spec: NutrientSpec) -> None:
    """
    Keep slider aligned with manual min and max inputs.

    Args:
        spec: Nutrient specification.
    """
    log.info(
        "Syncing slider from numeric inputs",
        extra={"event": "ui.sync.from_inputs", "nutrient": spec.key},
    )
    lower, upper = spec.bounds
    raw_min = _coerce_float(st.session_state.get(_min_key(spec)), spec.defaults[0])
    raw_max = _coerce_float(st.session_state.get(_max_key(spec)), spec.defaults[1])
    bounded_min = _clamp(raw_min, lower, upper)
    bounded_max = _clamp(raw_max, lower, upper)
    st.session_state[_min_key(spec)] = bounded_min
    st.session_state[_max_key(spec)] = bounded_max

    if bounded_min < bounded_max:
        st.session_state[_slider_key(spec)] = (bounded_min, bounded_max)


def _is_invalid_range(spec: NutrientSpec) -> bool:
    """
    Return True when active manual bounds are invalid.

    Args:
        spec: Nutrient specification.

    Returns:
        Whether the current min/max pair is invalid.
    """
    log.info(
        "Validating nutrient range",
        extra={"event": "ui.validate.range", "nutrient": spec.key},
    )
    if st.session_state.get(_any_key(spec), False):
        return False
    min_value = _coerce_float(st.session_state.get(_min_key(spec)), spec.defaults[0])
    max_value = _coerce_float(st.session_state.get(_max_key(spec)), spec.defaults[1])
    return min_value >= max_value


def _render_nutrient_filter(spec: NutrientSpec) -> bool:
    """
    Render one nutrient filter row and return invalid-state status.

    Args:
        spec: Nutrient specification.

    Returns:
        True when the filter has an invalid min/max pair.
    """
    log.info(
        "Rendering nutrient filter",
        extra={"event": "ui.nutrient.render", "nutrient": spec.key},
    )
    _initialize_nutrient_state(spec)
    header_controls = st.columns([0.56, 0.1, 0.17, 0.17])

    with header_controls[0]:
        st.markdown(f"**{spec.label}**")

    with header_controls[1]:
        st.toggle("", key=_any_key(spec), label_visibility="collapsed")
        st.write("Any" if st.session_state[_any_key(spec)] else "")

    is_any_enabled = bool(st.session_state[_any_key(spec)])

    with header_controls[2]:
        st.number_input(
            "Min",
            min_value=spec.bounds[0],
            max_value=spec.bounds[1],
            key=_min_key(spec),
            on_change=_sync_slider_from_inputs,
            args=(spec,),
            disabled=is_any_enabled,
        )

    with header_controls[3]:
        st.number_input(
            "Max",
            min_value=spec.bounds[0],
            max_value=spec.bounds[1],
            key=_max_key(spec),
            on_change=_sync_slider_from_inputs,
            args=(spec,),
            disabled=is_any_enabled,
        )

    st.slider(
        "Range",
        min_value=spec.bounds[0],
        max_value=spec.bounds[1],
        key=_slider_key(spec),
        value=spec.defaults,
        on_change=_sync_inputs_from_slider,
        args=(spec,),
        disabled=is_any_enabled,
    )

    has_invalid_range = _is_invalid_range(spec)

    if has_invalid_range:
        st.warning(f"{spec.label}: min must be less than max.")

    return has_invalid_range


def _render_dietary_toggles() -> Dict[str, bool]:
    """
    Render top-of-page dietary preference toggles.

    Returns:
        Mapping of dietary preference keys to enabled states.
    """
    log.info("Rendering dietary toggles", extra={"event": "ui.dietary.render"})
    st.subheader("Dietary Preferences")
    preference_columns = st.columns([1.0] * len(DIETARY_TOGGLE_LABELS))
    dietary_preferences: Dict[str, bool] = {}

    for column, (preference_key, label) in zip(
        preference_columns, DIETARY_TOGGLE_LABELS
    ):
        with column:
            toggle_key = f"dietary_{preference_key}"
            dietary_preferences[preference_key] = st.toggle(
                label,
                key=toggle_key,
                value=False,
            )

    return dietary_preferences


def _format_sql_number(value: float) -> str:
    """
    Format numeric values for SQL literal injection.

    Args:
        value: Float value.

    Returns:
        Stable numeric literal string.
    """
    log.info(
        "Formatting SQL numeric literal", extra={"event": "query.sql.format_numeric"}
    )
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _build_where_clauses(specs: List[NutrientSpec]) -> List[str]:
    """
    Build SQL filter clauses from nutrient selections.

    Args:
        specs: Nutrient specifications.

    Returns:
        SQL predicate fragments.
    """
    query_log.info(
        "Building nutrient SQL predicates", extra={"event": "query.sql.where_build"}
    )
    clauses: List[str] = []

    for spec in specs:
        if st.session_state.get(_any_key(spec), False):
            continue

        min_value = _coerce_float(
            st.session_state.get(_min_key(spec)), spec.defaults[0]
        )
        max_value = _coerce_float(
            st.session_state.get(_max_key(spec)), spec.defaults[1]
        )
        min_literal = _format_sql_number(min_value)
        max_literal = _format_sql_number(max_value)
        clauses.append(f'"{spec.db_column}" >= {min_literal}')
        clauses.append(f'"{spec.db_column}" <= {max_literal}')

    if not clauses:
        return ["1=1"]
    return clauses


def _build_food_query(specs: List[NutrientSpec]) -> str:
    """
    Build the SQL query for the food table.

    Args:
        specs: Nutrient specifications.

    Returns:
        SQL query string.
    """
    query_log.info("Constructing food SQL query", extra={"event": "query.sql.build"})
    where_sql = "\n        AND ".join(_build_where_clauses(specs))
    return f"""
        WITH nutrient_view AS (
            SELECT
                fdc_id,
                food_name,
                serving_size,
                "Energy [id:1008]" AS kilocalories,
                "Total lipid (fat)" AS fat,
                "Fatty acids, total saturated" AS saturated_fat,
                COALESCE("Sugars, Total", "Total Sugars") AS sugar,
                "Sodium, Na" AS sodium,
                Cholesterol AS cholesterol,
                Protein AS protein,
                COALESCE(
                    "Carbohydrate, by difference",
                    "Carbohydrate, by summation"
                ) AS carbs,
                "Iron, Fe" AS iron,
                "Calcium, Ca" AS calcium,
                "Potassium, K" AS potassium,
                "Fiber, total dietary" AS fiber,
                "Vitamin A, RAE" AS vitamin_a,
                Thiamin AS vitamin_b,
                "Vitamin C, total ascorbic acid" AS vitamin_c,
                "Vitamin D (D2 + D3)" AS vitamin_d,
                "Vitamin E (alpha-tocopherol)" AS vitamin_e,
                "Vitamin K (phylloquinone)" AS vitamin_k
            FROM food_nutrition
        )
        SELECT
            fdc_id,
            Value,
            food_name,
            serving_size,
            kilocalories,
            fat,
            saturated_fat,
            sugar,
            sodium,
            cholesterol,
            protein,
            carbs,
            iron,
            calcium,
            potassium,
            fiber,
            vitamin_a,
            vitamin_b,
            vitamin_c,
            vitamin_d,
            vitamin_e,
            vitamin_k
        FROM nutrient_view
        WHERE {where_sql}
        ORDER BY protein DESC
        LIMIT {QUERY_LIMIT}
    """


def _normalize_username(username: str) -> str:
    """
    Normalize usernames before lookup or creation.

    Args:
        username: Raw username input.

    Returns:
        Trimmed username.
    """
    auth_log.info(
        "Normalizing username for authentication",
        extra={"event": "auth.username_normalized"},
    )
    return username.strip()


def _get_secret_login_map() -> dict[str, str]:
    """
    Return configured secret credentials as a plain dictionary.

    Returns:
        Secret credential mapping keyed by username.
    """
    auth_log.info(
        "Loading credential mapping from Streamlit secrets",
        extra={"event": "auth.secrets_lookup"},
    )
    login_map = st.secrets.get("passwords", {})

    if login_map is None:
        return {}

    if not isinstance(login_map, Mapping):
        log.error(
            "Login credentials secret is not a mapping",
            extra={
                "event": "auth.secrets_invalid_type",
                "value_type": type(login_map).__name__,
            },
        )
        return {}

    return {str(key): str(value) for key, value in login_map.items()}


def credentials_match(username: str, password: str) -> bool:
    """
    Validate a username and password pair from the login JSON mapping.

    Args:
        username: The username entered by the user.
        password: The password entered by the user.

    Returns:
        True when the username exists and the mapped password matches exactly.
    """
    auth_log.info(
        "Login attempt started",
        extra={"event": "auth.login_attempt", "username": username},
    )
    normalized_username = _normalize_username(username)

    if not normalized_username or not password:
        auth_log.warning(
            "Login failed because required credentials were missing",
            extra={
                "event": "auth.login_invalid_input",
                "username": normalized_username,
            },
        )
        return False

    stored_password_hash = get_user_password_hash(USER_DB_PATH, normalized_username)

    if stored_password_hash is not None:
        is_authenticated = password_matches(password, stored_password_hash)
    else:
        secret_login_map = _get_secret_login_map()
        stored_secret_password = secret_login_map.get(normalized_username, "")
        is_authenticated = password_matches(password, stored_secret_password)

    auth_event = "auth.login_success" if is_authenticated else "auth.login_failed"

    if is_authenticated:
        auth_log.info(
            "Login succeeded",
            extra={"event": auth_event, "username": normalized_username},
        )
    else:
        auth_log.warning(
            "Login failed",
            extra={"event": auth_event, "username": normalized_username},
        )

    return is_authenticated


def create_account(username: str, password: str) -> bool:
    """
    Create a new user account in the local credential store.

    Args:
        username: Requested username.
        password: Requested password.

    Returns:
        True when the account is created successfully.
    """
    normalized_username = _normalize_username(username)
    auth_log.info(
        "Signup attempt started",
        extra={"event": "auth.signup_attempt", "username": normalized_username},
    )

    if not normalized_username:
        st.error("Username is required")
        return False

    if not password.strip():
        st.error("Password is required")
        return False

    if normalized_username in _get_secret_login_map():
        st.error("Username already exists")
        auth_log.warning(
            "Signup failed because the username exists in Streamlit secrets",
            extra={"event": "auth.signup_conflict", "username": normalized_username},
        )
        return False

    if get_user_password_hash(USER_DB_PATH, normalized_username) is not None:
        st.error("Username already exists")
        auth_log.warning(
            "Signup failed because the username exists in the local credential store",
            extra={"event": "auth.signup_conflict", "username": normalized_username},
        )
        return False

    if not create_user(USER_DB_PATH, normalized_username, password):
        st.error("Username already exists")
        return False

    auth_log.info(
        "Signup succeeded",
        extra={"event": "auth.signup_success", "username": normalized_username},
    )
    return True


def check_password() -> bool:
    """
    Validate user credentials using username and password.

    Returns a boolean indicating whether the user has successfully authenticated.
    """
    log.info("Running login gate check", extra={"event": "auth.gate_check"})

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.subheader("Login or Sign Up")
        with st.form("auth_login_form", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_submitted = st.form_submit_button("Login")

        normalized_username = _normalize_username(username)

        if login_submitted:
            if credentials_match(username=username, password=password):
                st.session_state.authenticated = True
                st.session_state.current_username = normalized_username
                st.rerun()
            else:
                st.error("Invalid username or password")
                return False

        if st.button("Sign Up"):
            if create_account(username=username, password=password):
                st.session_state.authenticated = True
                st.session_state.current_username = normalized_username
                st.rerun()
            return False

        return False

    return st.session_state.authenticated


if not check_password():
    st.stop()

# 2. THE DATABASE CONNECTION
# This connects to the URL you put in secrets.toml
conn = st.connection("postgresql", type="sql")

st.title("Nutrient Goal Finder")
dietary_preferences = _render_dietary_toggles()
_ = dietary_preferences

# 3. THE UI & ALGORITHM
invalid_ranges: Dict[str, bool] = {}

for nutrient in NUTRIENT_SPECS:
    invalid_ranges[nutrient.key] = _render_nutrient_filter(nutrient)

has_invalid_ranges = any(invalid_ranges.values())

if st.button("Find Foods", disabled=has_invalid_ranges):
    query_log.info(
        "Food query started",
        extra={
            "event": "db.query_started",
            "active_filters": sum(
                1
                for nutrient in NUTRIENT_SPECS
                if not st.session_state.get(_any_key(nutrient), False)
            ),
            "invalid_ranges": has_invalid_ranges,
        },
    )
    started_at = time.perf_counter()

    query = _build_food_query(NUTRIENT_SPECS)

    try:
        df = conn.query(query)
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        query_log.exception(
            "Food query failed",
            extra={"event": "db.query_failed", "duration_ms": duration_ms},
        )
        st.error("Unable to fetch foods. Please try again.")
        st.stop()

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    query_log.info(
        "Food query succeeded",
        extra={
            "event": "db.query_succeeded",
            "duration_ms": duration_ms,
            "row_count": len(df),
        },
    )
    st.table(df)
