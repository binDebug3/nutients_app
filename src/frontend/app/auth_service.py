"""Authentication service for Streamlit login and signup flows."""

from pathlib import Path
from typing import Mapping, Optional

from auth_store import (
    create_remote_user,
    create_user,
    get_remote_user_password_hash,
    get_user_password_hash,
    password_matches,
)


class AuthService:
    """
    Authenticate and create users using local DB and Streamlit secrets.

    Args:
        streamlit_module: Streamlit module or fake module in tests.
        auth_logger: Logger for authentication events.
        app_logger: Logger for app-level authentication events.
        user_db_path: Path to local user database.
    """

    def __init__(
        self,
        streamlit_module: object,
        auth_logger: object,
        app_logger: object,
        user_db_path: Path,
    ) -> None:
        """
        Initialize dependencies for authentication operations.

        Args:
            streamlit_module: Streamlit module-like object.
            auth_logger: Auth-specific logger.
            app_logger: App-level logger.
            user_db_path: Path to sqlite user database.
        """
        self._st = streamlit_module
        self._auth_log = auth_logger
        self._log = app_logger
        self.user_db_path = user_db_path
        self._postgres_url = self._resolve_postgres_url()

    def _resolve_postgres_url(self) -> Optional[str]:
        """
        Resolve Postgres URL from Streamlit secrets.

        Returns:
            Postgres URL when configured, otherwise None.
        """
        self._auth_log.info(
            "Resolving Postgres auth connection URL",
            extra={"event": "auth.remote_url_resolve"},
        )
        connections = self._st.secrets.get("connections", {})
        if isinstance(connections, Mapping):
            postgresql = connections.get("postgresql", {})
            if isinstance(postgresql, Mapping):
                url = postgresql.get("url")
                if isinstance(url, str) and url.strip():
                    return url.strip()
        direct_url = self._st.secrets.get("POSTGRES_URL")
        if isinstance(direct_url, str) and direct_url.strip():
            return direct_url.strip()
        return None

    def normalize_username(self, username: str) -> str:
        """
        Normalize usernames before lookup or creation.

        Args:
            username: Raw username input.

        Returns:
            Trimmed username.
        """
        self._auth_log.info(
            "Normalizing username for authentication",
            extra={
                "event": "auth.username_normalized",
                "raw_username": username,
                "normalized_len": len(username.strip()),
            },
        )
        return username.strip()

    def get_secret_login_map(self) -> dict[str, str]:
        """
        Return configured secret credentials as a plain dictionary.

        Returns:
            Secret credential mapping keyed by username.
        """
        self._auth_log.info(
            "Loading credential mapping from Streamlit secrets",
            extra={"event": "auth.secrets_lookup"},
        )
        login_map = self._st.secrets.get("passwords", {})
        if login_map is None:
            return {}
        if not isinstance(login_map, Mapping):
            self._log.error(
                "Login credentials secret is not a mapping",
                extra={
                    "event": "auth.secrets_invalid_type",
                    "value_type": type(login_map).__name__,
                },
            )
            return {}
        return {str(key): str(value) for key, value in login_map.items()}

    def credentials_match(self, username: str, password: str) -> bool:
        """
        Validate a username and password pair.

        Args:
            username: Username entered by the user.
            password: Password entered by the user.

        Returns:
            True when credentials are accepted.
        """
        self._auth_log.info(
            "Login attempt started",
            extra={"event": "auth.login_attempt", "username": username},
        )
        normalized_username = self.normalize_username(username)
        if not normalized_username or not password:
            self._auth_log.warning(
                "Login failed because required credentials were missing",
                extra={
                    "event": "auth.login_invalid_input",
                    "username": normalized_username,
                },
            )
            return False
        stored_password_hash: Optional[str]
        if self._postgres_url:
            stored_password_hash = get_remote_user_password_hash(
                self._postgres_url,
                normalized_username,
            )
        else:
            stored_password_hash = get_user_password_hash(
                self.user_db_path,
                normalized_username,
            )
        if stored_password_hash is not None:
            is_authenticated = password_matches(password, stored_password_hash)
        else:
            secret_login_map = self.get_secret_login_map()
            stored_secret_password = secret_login_map.get(normalized_username, "")
            is_authenticated = password_matches(password, stored_secret_password)
        self._log_auth_result(normalized_username, is_authenticated)
        return is_authenticated

    def create_account(self, username: str, password: str) -> bool:
        """
        Create a new user account in the local credential store.

        Args:
            username: Requested username.
            password: Requested password.

        Returns:
            True when the account is created successfully.
        """
        self._auth_log.info(
            "create_account called",
            extra={
                "event": "auth.create_account_called",
                "username_arg": username,
                "username_len": len(username),
                "password_len": len(password),
            },
        )
        normalized_username = self.normalize_username(username)
        self._auth_log.info(
            "Signup attempt started",
            extra={
                "event": "auth.signup_attempt",
                "username": normalized_username,
                "normalized_len": len(normalized_username),
            },
        )
        if not self._validate_signup_input(normalized_username, password):
            return False
        if self._username_exists(normalized_username):
            self._show_dismissible_error("Username already exists")
            return False
        if self._postgres_url:
            created = create_remote_user(
                self._postgres_url,
                normalized_username,
                password,
            )
        else:
            created = create_user(self.user_db_path, normalized_username, password)
        if not created:
            self._show_dismissible_error("Failed to create account")
            return False
        self._auth_log.info(
            "Signup succeeded",
            extra={"event": "auth.signup_success", "username": normalized_username},
        )
        return True

    def check_password(self) -> bool:
        """
        Validate user credentials using username and password.

        Returns:
            Whether the user is authenticated.
        """
        self._log.info("Running login gate check", extra={"event": "auth.gate_check"})
        if "authenticated" not in self._st.session_state:
            self._st.session_state.authenticated = False
        if self._st.session_state.authenticated:
            return True

        username, password, login_submitted, signup_submitted = self._render_auth_form()
        self._log.info(
            "Form rendered",
            extra={
                "event": "auth.form_rendered",
                "username_from_form": username,
                "password_from_form": "***" if password else "",
                "login_submitted": login_submitted,
                "signup_submitted": signup_submitted,
            },
        )
        username_from_state = self._st.session_state.get(
            "auth_username_input", ""
        ).strip()
        password_from_state = self._st.session_state.get("auth_password_input", "")
        self._log.info(
            "Session state auth inputs",
            extra={
                "event": "auth.session_state_read",
                "username_from_state_len": len(username_from_state),
                "username_from_state": username_from_state,
                "password_from_state_len": len(password_from_state),
                "password_from_state": "***" if password_from_state else "",
                "session_state_keys": list(self._st.session_state.keys()),
            },
        )
        normalized_username = self.normalize_username(username_from_state)
        self._log.info(
            "Username normalized",
            extra={
                "event": "auth.username_normalized_in_check",
                "raw_username": username_from_state,
                "normalized_username": normalized_username,
                "normalized_len": len(normalized_username),
            },
        )
        if login_submitted:
            self._log.info(
                "Login submit detected",
                extra={"event": "auth.login_submit_detected"},
            )
            return self._handle_login_submit(
                username_from_state,
                password_from_state,
                normalized_username,
            )
        if signup_submitted:
            self._log.info(
                "Sign Up button clicked",
                extra={
                    "event": "auth.signup_button_clicked",
                    "username": username_from_state,
                    "username_len": len(username_from_state),
                    "password_len": len(password_from_state),
                },
            )
            return self._handle_signup_submit(
                username_from_state,
                password_from_state,
                normalized_username,
            )
        return False

    def _validate_signup_input(self, normalized_username: str, password: str) -> bool:
        """
        Validate required signup inputs.

        Args:
            normalized_username: Trimmed username.
            password: Raw password text.

        Returns:
            True when required fields are valid.
        """
        self._auth_log.info(
            "Validating signup input",
            extra={
                "event": "auth.signup_validate",
                "normalized_username": normalized_username,
                "normalized_username_len": len(normalized_username),
                "password_len": len(password),
                "password_empty": not password or not password.strip(),
            },
        )
        if not normalized_username:
            self._auth_log.warning(
                "Signup validation failed: username is empty",
                extra={
                    "event": "auth.signup_validate_fail_username",
                    "username": normalized_username,
                },
            )
            self._show_dismissible_error("Username is required")
            return False
        if not password.strip():
            self._auth_log.warning(
                "Signup validation failed: password is empty",
                extra={
                    "event": "auth.signup_validate_fail_password",
                    "username": normalized_username,
                },
            )
            self._show_dismissible_error("Password is required")
            return False
        self._auth_log.info(
            "Signup input validation passed",
            extra={
                "event": "auth.signup_validate_pass",
                "username": normalized_username,
            },
        )
        return True

    def _username_exists(self, normalized_username: str) -> bool:
        """
        Check whether a username exists in secrets or local store.

        Args:
            normalized_username: Trimmed username.

        Returns:
            True when the username already exists.
        """
        self._auth_log.info(
            "Checking username uniqueness",
            extra={"event": "auth.signup_uniqueness", "username": normalized_username},
        )
        if normalized_username in self.get_secret_login_map():
            self._auth_log.warning(
                "Signup failed because the username exists in Streamlit secrets",
                extra={
                    "event": "auth.signup_conflict",
                    "username": normalized_username,
                },
            )
            return True

        if self._postgres_url:
            existing_password_hash = get_remote_user_password_hash(
                self._postgres_url,
                normalized_username,
            )
        else:
            existing_password_hash = get_user_password_hash(
                self.user_db_path,
                normalized_username,
            )

        if existing_password_hash is not None:
            self._auth_log.warning(
                "Signup failed because the username exists in the credential store",
                extra={
                    "event": "auth.signup_conflict",
                    "username": normalized_username,
                },
            )
            return True
        return False

    def _log_auth_result(
        self, normalized_username: str, is_authenticated: bool
    ) -> None:
        """
        Log the outcome of an authentication attempt.

        Args:
            normalized_username: Trimmed username.
            is_authenticated: Whether auth succeeded.
        """
        auth_event = "auth.login_success" if is_authenticated else "auth.login_failed"
        if is_authenticated:
            self._auth_log.info(
                "Login succeeded",
                extra={"event": auth_event, "username": normalized_username},
            )
        else:
            self._auth_log.warning(
                "Login failed",
                extra={"event": auth_event, "username": normalized_username},
            )

    def _render_auth_form(self) -> tuple[str, str, bool, bool]:
        """
        Render login form and return entered credentials.

        Returns:
            Username, password, login submit state, and signup submit state.
        """
        self._auth_log.info("Rendering auth form", extra={"event": "auth.form_render"})
        self._st.subheader("Login or Sign Up")
        with self._st.form("auth_login_form", clear_on_submit=False):
            username = self._st.text_input(
                "Username",
                key="auth_username_input",
            )
            password = self._st.text_input(
                "Password",
                type="password",
                key="auth_password_input",
            )
            login_col, signup_col = self._st.columns([1, 1])
            with login_col:
                login_submitted = self._st.form_submit_button("Login")
            with signup_col:
                signup_submitted = self._st.form_submit_button("Sign Up")
        self._auth_log.info(
            "Auth form rendering complete",
            extra={
                "event": "auth.form_render_complete",
                "username_from_form_return": username,
                "username_len": len(username),
                "password_len": len(password),
                "login_submitted": login_submitted,
                "signup_submitted": signup_submitted,
                "session_state_username": self._st.session_state.get(
                    "auth_username_input", "<not set>"
                ),
                "session_state_password_len": len(
                    self._st.session_state.get("auth_password_input", "")
                ),
            },
        )
        return username, password, login_submitted, signup_submitted

    def _show_dismissible_error(self, message: str) -> None:
        """
        Show an error message that auto-dismisses after 10 seconds.

        Args:
            message: Error message text.
        """
        if hasattr(self._st, "toast"):
            self._st.toast(message, icon="❌")
        else:
            error_placeholder = self._st.empty()
            with error_placeholder.container():
                self._st.error(message)

    def _handle_login_submit(
        self,
        username: str,
        password: str,
        normalized_username: str,
    ) -> bool:
        """
        Process login form submission.

        Args:
            username: Raw username.
            password: Raw password.
            normalized_username: Trimmed username.

        Returns:
            False because a rerun is requested on success.
        """
        self._auth_log.info(
            "Processing login submit",
            extra={
                "event": "auth.login_submit",
                "username_arg": username,
                "username_len": len(username),
                "password_len": len(password),
                "normalized_username_arg": normalized_username,
            },
        )
        is_match = self.credentials_match(username=username, password=password)
        self._auth_log.info(
            "Login credentials validation result",
            extra={
                "event": "auth.login_credentials_match",
                "is_match": is_match,
                "username": normalized_username,
            },
        )
        if is_match:
            self._auth_log.info(
                "Login successful, setting authenticated state",
                extra={
                    "event": "auth.login_success",
                    "username": normalized_username,
                },
            )
            self._st.session_state.authenticated = True
            self._st.session_state.current_username = normalized_username
            self._st.rerun()
        else:
            self._auth_log.warning(
                "Login failed due to invalid credentials",
                extra={
                    "event": "auth.login_fail_invalid",
                    "username": normalized_username,
                },
            )
            self._show_dismissible_error("Invalid username or password")
        return False

    def _handle_signup_submit(
        self,
        username: str,
        password: str,
        normalized_username: str,
    ) -> bool:
        """
        Process signup button submission.

        Args:
            username: Raw username.
            password: Raw password.
            normalized_username: Trimmed username.

        Returns:
            False because a rerun is requested on success.
        """
        self._auth_log.info(
            "Processing signup submit",
            extra={
                "event": "auth.signup_submit",
                "username_arg": username,
                "username_len": len(username),
                "password_len": len(password),
                "normalized_username_arg": normalized_username,
            },
        )
        account_created = self.create_account(username=username, password=password)
        self._auth_log.info(
            "Account creation attempt result",
            extra={
                "event": "auth.signup_create_account_result",
                "account_created": account_created,
                "username": normalized_username,
            },
        )
        if account_created:
            self._auth_log.info(
                "Signup successful, setting authenticated state",
                extra={
                    "event": "auth.signup_success",
                    "username": normalized_username,
                },
            )
            self._st.session_state.authenticated = True
            self._st.session_state.current_username = normalized_username
            self._st.rerun()
        return False
