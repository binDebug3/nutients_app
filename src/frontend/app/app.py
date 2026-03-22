import json
import logging
from pathlib import Path
from typing import Dict

import streamlit as st


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

APP_PATH = Path(__file__).resolve()
LOGIN_JSON_PATH = APP_PATH.parents[4] / "secrets" / "passwords" / "logins.json"
print("start")
print("App path:", LOGIN_JSON_PATH)

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
    log.info("Checking credentials for username: %s", username)

    if not LOGIN_JSON_PATH.exists():
        log.error("Login credentials file was not found at %s", LOGIN_JSON_PATH)
        return False

    with LOGIN_JSON_PATH.open("r", encoding="utf-8") as file_handle:
        login_map: Dict[str, str] = json.load(file_handle)

    if not isinstance(login_map, dict):
        log.error("Login credentials file is not a JSON object")
        return False

    return login_map.get(username) == password


def check_password() -> bool:
    """
    Validate user credentials using username and password.

    Returns a boolean indicating whether the user has successfully authenticated.
    """
    log.info("Running login gate check")

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
    # Note the double quotes for column names with spaces/commas
    query = f"""
        SELECT food_name, serving_size, "Protein", "Carbohydrate, by difference"
        FROM food_nutrition
        WHERE "Protein" >= {protein_target} 
        AND "Carbohydrate, by difference" <= {carb_max}
        ORDER BY "Protein" DESC
        LIMIT 20
    """

    df = conn.query(query)
    st.table(df)
