import json
import time
from pathlib import Path
from typing import Dict

import streamlit as st

from logging_setup import configure_app_logging


APP_PATH = Path(__file__).resolve()
REPO_ROOT = APP_PATH.parents[3]
LOGIN_JSON_PATH = APP_PATH.parents[4] / "secrets" / "passwords" / "logins.json"
LOGGER_MAP = configure_app_logging(REPO_ROOT)
log = LOGGER_MAP["app"]
auth_log = LOGGER_MAP["auth"]
query_log = LOGGER_MAP["query"]

# 1. THE LOGIN GATE
# For a quick start, we use a simple password.
# You can swap this for Google Login later.


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

    if not LOGIN_JSON_PATH.exists():
        log.error("Login credentials file was not found at %s", LOGIN_JSON_PATH)
        return False

    with LOGIN_JSON_PATH.open("r", encoding="utf-8") as file_handle:
        login_map: Dict[str, str] = json.load(file_handle)

    if not isinstance(login_map, dict):
        log.error("Login credentials file is not a JSON object")
        return False

    is_authenticated = login_map.get(username) == password

    if is_authenticated:
        auth_log.info(
            "Login succeeded",
            extra={"event": "auth.login_success", "username": username},
        )
    else:
        auth_log.warning(
            "Login failed",
            extra={"event": "auth.login_failed", "username": username},
        )

    return is_authenticated


def check_password() -> bool:
    """
    Validate user credentials using username and password.

    Returns a boolean indicating whether the user has successfully authenticated.
    """
    log.info("Running login gate check", extra={"event": "auth.gate_check"})

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if credentials_match(username=username, password=password):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid username or password")
                return False

        return False

    return st.session_state.authenticated


if not check_password():
    st.stop()

# 2. THE DATABASE CONNECTION
# This connects to the URL you put in secrets.toml
conn = st.connection("postgresql", type="sql")

st.title("Nutrient Goal Finder")

# 3. THE UI & ALGORITHM
# Let's say you want to find foods high in Protein but low in Carbs
protein_target = st.slider("Minimum Protein (g)", 0, 50, 20)
carb_max = st.slider("Maximum Carbs (g)", 0, 100, 10)

if st.button("Find Foods"):
    query_log.info(
        "Food query started",
        extra={
            "event": "db.query_started",
            "protein_target": protein_target,
            "carb_max": carb_max,
        },
    )
    started_at = time.perf_counter()

    # Note the double quotes for column names with spaces/commas
    query = f"""
        SELECT food_name, serving_size, "Protein", "Carbohydrate, by difference"
        FROM food_nutrition
        WHERE "Protein" >= {protein_target} 
        AND "Carbohydrate, by difference" <= {carb_max}
        ORDER BY "Protein" DESC
        LIMIT 20
    """

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
