"""
AspectLens — Aspect-Based Sentiment Analytics  (main entry point)
=================================================================
Run / deploy THIS file:   streamlit run app.py

This file stays THIN on purpose — it only:
  1. makes sure the code next to it is complete     (staging, below)
  2. sets page config + theme                       (styles.py)
  3. initialises the database                       (database.py)
  4. draws the sidebar + routing                    (views/*.py)

All real logic lives in the modules below:
  config.py      constants (colours, paths, app name, writable DB path)
  database.py    SQLite: users, activity logs, analysis history
  auth.py        passwords, Gmail validation, login sessions
  google_auth.py real "Continue with Google" (OAuth 2.0)
  catalog.py     built-in 5,000-item product catalog + generated demo reviews
  nlp_engine.py  aspect-sentiment NLP
  charts.py      Plotly dashboard figures
  ui_helpers.py  reusable cards / avatars / badges
  views/         one file per screen (login, analysis, profile, history, admin)

Deploy-proofing notes
---------------------
* If a zip of this project sits next to app.py, its missing files are unpacked
  automatically (some upload paths drop folders — that is what used to cause
  "ModuleNotFoundError: No module named 'views'").
* Files are loaded from `views/` directly even if `views/__init__.py` is absent.
* Any unexpected failure is rendered as a readable card with a "Reload" button
  instead of Streamlit's redacted "Error running app" traceback.
"""
import os
import sys
import zipfile

import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))


# ===========================================================================
# 0. SELF-HEALING: unpack a bundled zip if the code beside this file is partial
# ===========================================================================

def _extract_missing(zip_path: str, dest: str) -> list:
    """Extract every entry of `zip_path` missing under `dest`.

    Crucially this NEVER overwrites an existing file: whatever is already in the
    repo wins, so a redeploy can never be clobbered by an old bundle.
    """
    written = []
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                name = info.filename
                if name.endswith("/") or "__MACOSX" in name:
                    continue
                # A single wrapping folder (e.g. "aspectlens/app.py") -> strip it.
                parts = [p for p in name.split("/") if p not in ("", ".")]
                if not parts:
                    continue
                if len(parts) > 1 and parts[0] in {
                    "aspectlens", "aspectlens-clean", "aspectlens-deploy", "app"
                }:
                    parts = parts[1:]
                target = os.path.join(dest, *parts)
                if os.path.exists(target):
                    continue
                os.makedirs(os.path.dirname(target) or dest, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    out.write(src.read())
                written.append("/".join(parts))
    except Exception as exc:            # never let staging break the boot
        print(f"[app] zip staging skipped: {exc}", file=sys.stderr)
    return written


def _stage_bundle():
    """If app.py, views/ and the modules are not all present, unzip a bundle."""
    needed = ["config.py", "views/login.py", "views/analysis.py"]
    if all(os.path.exists(os.path.join(_HERE, n)) for n in needed):
        return []
    for zpath in sorted(
        os.path.join(_HERE, f) for f in os.listdir(_HERE) if f.lower().endswith(".zip")
    ):
        files = _extract_missing(zpath, _HERE)
        if all(os.path.exists(os.path.join(_HERE, n)) for n in needed):
            print(f"[app] unpacked {len(files)} file(s) from {os.path.basename(zpath)}")
            return files
    return []


_stage_bundle()


# ===========================================================================
# 1. PAGE SETUP  (must be the first Streamlit call)
# ===========================================================================

st.set_page_config(
    page_title="AspectLens • Aspect Sentiment Analytics",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===========================================================================
# 2. IMPORTS  (project modules, loaded defensively)
# ===========================================================================

import traceback                         # noqa: E402
from datetime import datetime            # noqa: E402

_CONFIG_ERROR = None
try:
    from config import APP_NAME, DB_PATH
    from styles import apply_custom_css
    from database import init_db, log_event
    from ui_helpers import avatar_html
    from google_auth import handle_oauth_callback
except Exception as _exc:                # pragma: no cover
    _CONFIG_ERROR = _exc
    APP_NAME, DB_PATH = "AspectLens", "absa.db"

if _CONFIG_ERROR is None:
    apply_custom_css()


# ---------- screens ----------

class _Stub:
    """Placeholder that re-raises the import error if a page is ever called."""

    def __init__(self, exc):
        self._exc = exc

    def __getattr__(self, item):
        raise self._exc


def _load_screens():
    """Import the five screens.

    Tries the normal package import first, then loads each file straight from
    `views/`. That second path still works when `views/__init__.py` never made
    it into the repository (the folder itself missing is a different problem,
    reported by `_show_setup_problem`).
    """
    try:
        from views import admin, analysis, history, login, profile
        return login, analysis, profile, history, admin
    except ImportError:
        pass

    import importlib.util

    screens = {}
    for name in ("login", "analysis", "profile", "history", "admin"):
        path = os.path.join(_HERE, "views", f"{name}.py")
        if not os.path.isfile(path):
            raise ModuleNotFoundError(
                f"No module named 'views' — expected {path}", name="views"
            )
        spec = importlib.util.spec_from_file_location(f"aspectlens_views_{name}", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        screens[name] = module
    return (screens["login"], screens["analysis"], screens["profile"],
            screens["history"], screens["admin"])


try:
    login, analysis, profile, history, admin = _load_screens()
    _SCREENS_ERROR = None
except Exception as _exc:                # pragma: no cover
    _SCREENS_ERROR = _exc
    login = analysis = profile = history = admin = _Stub(_exc)


# ===========================================================================
# 3. HELPER SCREENS (only shown when something is genuinely wrong)
# ===========================================================================

def _runtime_facts() -> str:
    """A compact block of facts, shown only inside a collapsed expander."""
    views_dir = os.path.join(_HERE, "views")
    try:
        py_files = sorted(f for f in os.listdir(_HERE) if f.endswith(".py"))
    except Exception:
        py_files = []
    try:
        view_files = sorted(f for f in os.listdir(views_dir)) if os.path.isdir(views_dir) else []
    except Exception:
        view_files = []
    return "\n".join([
        f"python         : {sys.version.split()[0]}",
        f"streamlit      : {st.__version__}",
        f"app folder     : {_HERE}",
        f"database       : {DB_PATH}",
        f"views/ present : {os.path.isdir(views_dir)}",
        f"views/ files   : {', '.join(view_files) if view_files else '(none)'}",
        f"root .py files : {', '.join(py_files) if py_files else '(none)'}",
    ])


def _show_setup_problem(exc: BaseException):
    st.error("**Setup problem — some project files are not next to `app.py`.**")
    st.markdown(
        "The app is running, but it cannot find the screen modules it needs.\n\n"
        "**Fastest fix**\n\n"
        "1. Download **`aspectlens-deploy.zip`** from the Drive folder.\n"
        "2. Put **every file from the zip** in the root of your GitHub repo — "
        "`app.py`, the `.py` modules, `requirements.txt` **and the `views` folder**.\n"
        "3. On Streamlit Cloud: **Manage app → Reboot app**.\n\n"
        "If the `views` folder keeps disappearing, keep `aspectlens-deploy.zip` "
        "in the repo root as well: this file unpacks whatever is missing on the "
        "next start. Nothing is ever overwritten."
    )
    with st.expander("Technical detail"):
        st.code(_runtime_facts())
        st.code("".join(traceback.format_exception_only(type(exc), exc)).strip())
    st.stop()


def _show_boot_error(exc: BaseException):
    """Last line of defence: a readable card instead of a redacted traceback."""
    print("[app] boot failed:", file=sys.stderr)
    traceback.print_exc()

    st.error("**Something went wrong while starting the app.**")
    st.markdown(
        "The page below can be reloaded without redeploying.\n\n"
        "If it keeps happening, open **Technical detail** and share that text — "
        "it names the exact file and line."
    )
    if st.button("🔄 Reload the app", type="primary"):
        st.rerun()
    with st.expander("Technical detail"):
        st.code(_runtime_facts())
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:])
    st.stop()


# ===========================================================================
# 4. SIDEBAR + ROUTER
# ===========================================================================

def sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"""
        <div style="display:flex; gap:12px; align-items:center; margin-bottom:6px;">
          {avatar_html(user, 'sm')}
          <div><div style="font-weight:800;">{user['username']}</div>
          <div class="small-note">{user['email']}</div></div>
        </div>""", unsafe_allow_html=True)
        st.markdown(f'<div class="brand-mini">💜 {APP_NAME}</div>', unsafe_allow_html=True)
        st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)
        options = ["🛍️ Products", "👤 My Account"]
        if user.get("is_admin"):
            options.append("🛡️ Admin Panel")
        page = st.radio(
            "Navigate", options, label_visibility="collapsed",
            index=options.index(st.session_state.get("page", "🛍️ Products"))
            if st.session_state.get("page") in options else 0,
        )
        if page != st.session_state.get("page"):
            st.session_state.page = page
            log_event(user, "navigate", f"Opened {page}")
            st.rerun()
        st.markdown("---")
        login_t = st.session_state.get("login_time")
        if login_t:
            mins = int((datetime.now() - login_t).total_seconds() // 60)
            st.caption(f"🟢 Session live • {mins} min • id {st.session_state.get('session_id', '')}")
        if st.button("🚪 Logout", type="secondary", width="stretch"):
            dur = ""
            if login_t:
                delta = datetime.now() - login_t
                dur = f"Session duration {str(delta).split('.')[0]}"
            log_event(user, "logout", f"User left the website. {dur}")
            for k in ["user", "page", "catalog_product_id", "catalog_analysis", "catalog_query",
                      "catalog_category", "show_google", "login_time", "session_id"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown("---")
        with st.expander("ℹ️ How it works"):
            st.caption("1️⃣ Type a product in the search box.\n\n"
                       "2️⃣ Pick it from the suggestions that appear.\n\n"
                       "3️⃣ The analysis runs instantly — verdict, 8 aspects, charts.\n\n"
                       "4️⃣ Its reviews are listed underneath.\n\n"
                       "All review text is generated demo data.")


def _boot():
    init_db()

    # Google redirects back to the app with ?code=... — this must run BEFORE the
    # login gate, otherwise the user is shown the login screen again and the
    # handshake silently dies.
    if "user" not in st.session_state or st.session_state.user is None:
        google_profile, oauth_error = handle_oauth_callback()
        if oauth_error:
            st.session_state["oauth_error"] = oauth_error
        if google_profile:
            login.login_with_google_profile(google_profile)

    if "user" not in st.session_state or st.session_state.user is None:
        login.auth_page()
        st.markdown("<div class='small-note' style='text-align:center; margin-top:26px;'>"
                    "AspectLens • 100% free & open — Streamlit + SQLite + Plotly • No paid APIs</div>",
                    unsafe_allow_html=True)
        return

    sidebar()
    page = st.session_state.get("page", "🛍️ Products")
    if page == "🛍️ Products":
        analysis.page_analysis()
    elif page == "👤 My Account":
        profile.page_profile()
        st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)
        history.page_history()
    elif page == "🛡️ Admin Panel":
        admin.page_admin()


if _CONFIG_ERROR is not None:
    _show_setup_problem(_CONFIG_ERROR)
elif _SCREENS_ERROR is not None:
    _show_setup_problem(_SCREENS_ERROR)
else:
    try:
        _boot()
    except Exception as _boot_exc:
        _show_boot_error(_boot_exc)
