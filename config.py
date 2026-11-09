"""
config.py — Central configuration for AspectLens.
------------------------------------------------
All app-wide constants live here (app name, file paths, chart colours,
platform badge colours) so every other file imports from ONE place.
"""
import os

APP_NAME = "AspectLens"

# st.login() (Streamlit's built-in OIDC) always redirects back to this path.
# It MUST be registered in Google Cloud as an Authorized redirect URI.
OAUTH_CALLBACK_PATH = "/oauth2callback"

# Shown in the sidebar so anyone can verify which code is deployed.
# Bump this whenever you upload a new build.
BUILD = "v6 · 09 Nov 2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _writable(folder: str) -> bool:
    """True when we can actually create a file in `folder`."""
    try:
        probe = os.path.join(folder, ".write_test")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


def _resolve_db_path() -> str:
    """Where the SQLite file lives.

    Order of preference:
      1. ABSA_DB_PATH environment variable (explicit override)
      2. next to this file  (normal case: local run, Streamlit Cloud)
      3. the system temp folder (rare read-only filesystem)

    The fallback means the app still BOOTS instead of crashing with
    'sqlite3.OperationalError: unable to open database file'.
    """
    override = os.environ.get("ABSA_DB_PATH", "").strip()
    if override:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(override)), exist_ok=True)
        except Exception:
            pass
        return override
    if _writable(BASE_DIR):
        return os.path.join(BASE_DIR, "absa.db")
    import tempfile
    return os.path.join(tempfile.gettempdir(), "absa.db")


DB_PATH = _resolve_db_path()   # SQLite file (auto-created)

# ---- Sentiment colours (used by charts + badges) ----
POS_COLOR = "#10b981"   # emerald  = Positive
NEG_COLOR = "#f43f5e"   # rose/red = Negative
NEU_COLOR = "#8b5cf6"   # violet   = Neutral
ACCENT = "#9333ea"      # brand purple
