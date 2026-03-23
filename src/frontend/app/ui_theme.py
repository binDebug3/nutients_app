"""Dark UI theme tokens and styling helpers for Streamlit frontend."""

from typing import Dict, List


FILTER_HEADER_COLUMNS: List[float] = [0.56, 0.22, 0.22]
FILTER_ROW_COLUMNS: List[float] = [0.24, 0.11, 0.45, 0.1, 0.1]
SUMMARY_COLUMNS: List[float] = [1.0, 1.0, 1.15]


THEME_TOKENS: Dict[str, str] = {
    "bg": "#090b10",
    "surface": "#101521",
    "surface_alt": "#161c2b",
    "text": "#ecf2ff",
    "muted": "#9fb0d4",
    "accent": "#4fd1ff",
    "accent_alt": "#42f5d1",
    "warning": "#f6c85f",
    "danger": "#ff7b8e",
    "border": "#2a3550",
}


def _css_from_tokens() -> str:
    """
    Build the global CSS string for the dark playful-modern theme.

    Returns:
        CSS string using centralized theme tokens.
    """
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap');

:root {{
  --bg: {THEME_TOKENS["bg"]};
  --surface: {THEME_TOKENS["surface"]};
  --surface-alt: {THEME_TOKENS["surface_alt"]};
  --text: {THEME_TOKENS["text"]};
  --muted: {THEME_TOKENS["muted"]};
  --accent: {THEME_TOKENS["accent"]};
  --accent-alt: {THEME_TOKENS["accent_alt"]};
  --warning: {THEME_TOKENS["warning"]};
  --danger: {THEME_TOKENS["danger"]};
  --border: {THEME_TOKENS["border"]};
}}

html, body, [class*="css"] {{
  font-family: "Manrope", "Segoe UI", sans-serif;
}}

[data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(1100px 550px at 3% -8%, rgba(79, 209, 255, 0.16), transparent 58%),
    radial-gradient(900px 480px at 104% -10%, rgba(66, 245, 209, 0.14), transparent 55%),
    var(--bg);
  color: var(--text);
}}

[data-testid="stHeader"] {{
  background: transparent;
}}

[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, rgba(16, 21, 33, 0.92), rgba(16, 21, 33, 0.72));
  border-right: 1px solid var(--border);
}}

h1, h2, h3, h4 {{
  color: var(--text);
  letter-spacing: 0.01em;
}}

div[data-testid="stMarkdownContainer"] p {{
  color: var(--muted);
}}

div.stButton > button {{
  background: linear-gradient(135deg, rgba(79, 209, 255, 0.22), rgba(66, 245, 209, 0.2));
  border: 1px solid rgba(79, 209, 255, 0.5);
  color: var(--text);
  border-radius: 12px;
  font-weight: 700;
  transition: transform 0.12s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}}

div.stButton > button:hover {{
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(79, 209, 255, 0.18);
  border-color: rgba(79, 209, 255, 0.85);
}}

div.stButton > button:focus {{
  outline: none;
  box-shadow: 0 0 0 0.2rem rgba(79, 209, 255, 0.35);
}}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {{
  background-color: var(--surface-alt);
  border-color: var(--border);
}}

div[data-baseweb="slider"],
div[data-baseweb="slider"] > div {{
  background-color: transparent !important;
  border-color: transparent;
}}

div[data-baseweb="slider"] [role="slider"] {{
  background: var(--danger) !important;
  border: 2px solid rgba(9, 11, 16, 0.95);
  border-radius: 999px;
  box-shadow: none;
}}

div[data-testid="stDataFrame"] div[role="grid"],
div[data-testid="stTable"] table {{
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}}

div[data-testid="stDataFrame"] div[role="columnheader"] {{
  background: rgba(79, 209, 255, 0.08);
  color: var(--text);
  font-weight: 700;
}}

div[data-testid="stDataFrame"] div[role="gridcell"] {{
  color: var(--text);
  font-size: 0.86rem;
}}

.app-surface {{
  background: linear-gradient(180deg, rgba(22, 28, 43, 0.86), rgba(16, 21, 33, 0.86));
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 0.9rem 1rem;
  margin: 0.35rem 0 0.7rem 0;
}}

.metric-card {{
  background: linear-gradient(180deg, rgba(22, 28, 43, 0.95), rgba(14, 18, 30, 0.95));
  border: 1px solid rgba(79, 209, 255, 0.33);
  border-radius: 16px;
  padding: 0.8rem 0.9rem;
  min-height: 112px;
}}

.metric-label {{
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}

.metric-value {{
  color: var(--text);
  font-size: 1.45rem;
  font-weight: 800;
  margin-top: 0.25rem;
}}

.status-ok {{
  color: var(--accent-alt);
}}

.status-unknown {{
  color: var(--warning);
}}

.top-picks {{
  color: var(--text);
  background: rgba(79, 209, 255, 0.12);
  border: 1px solid rgba(79, 209, 255, 0.38);
  border-radius: 10px;
  padding: 0.5rem 0.7rem;
  margin: 0.45rem 0 0.8rem 0;
}}
</style>
"""


def safe_markdown(
    streamlit_module: object, body: str, unsafe_html: bool = False
) -> None:
    """
    Render markdown while remaining compatible with test doubles.

    Args:
        streamlit_module: Streamlit module-like object.
        body: Markdown or HTML content.
        unsafe_html: Whether to request unsafe HTML rendering.
    """
    if not hasattr(streamlit_module, "markdown"):
        return
    try:
        streamlit_module.markdown(body, unsafe_allow_html=unsafe_html)
    except TypeError:
        streamlit_module.markdown(body)


def apply_dark_theme(streamlit_module: object) -> None:
    """
    Apply centralized dark theme styles to Streamlit UI.

    Args:
        streamlit_module: Streamlit module-like object.
    """
    safe_markdown(streamlit_module, _css_from_tokens(), unsafe_html=True)
