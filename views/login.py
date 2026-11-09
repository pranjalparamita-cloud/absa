"""
views/login.py — one screen, two ways in.

  1. "Continue with Google" — uses Streamlit's built-in st.login() (OIDC).
  2. Email + password        — plus "Create account", same form.

WHY st.login() AND NOT A HAND-BUILT URL
---------------------------------------
The previous version built the Google URL itself and relied on the browser
following a <meta http-equiv="refresh">. When that markup is rendered inside a
framed context, Google refuses to display its OAuth screen and answers with

    403. That's an error.
    We're sorry, but you do not have access to this page.

`st.login()` hands the redirect to the Streamlit SERVER, which issues a real
302 before any HTML is sent. The consent screen is therefore always a top-level
page and can never be framed — the 403 cannot happen.

Streamlit's own redirect always ends in /oauth2callback, so that exact URL must
be registered in Google Cloud (see GOOGLE_SETUP.md).
"""
import io
import re
import secrets

import requests
import streamlit as st
from PIL import Image

from auth import do_login, valid_username, valid_gmail, password_issues
from config import APP_NAME, BUILD, OAUTH_CALLBACK_PATH
from database import get_user_by_login, get_user_by_id, create_user, log_event
from google_auth import (is_google_configured, build_auth_url, redirect_to_google,
                         diagnose, explain_403, native_login_configured,
                         current_native_user)


def login_with_google_profile(profile):
    """Find-or-create the account for a verified Google email, then log in."""
    email = profile["email"].strip().lower()
    user = get_user_by_login(email)
    if user is None:                                 # first time with this Gmail
        base = re.sub(r"[^A-Za-z0-9_]", "_", email.split("@")[0])[:16] or "user"
        uname, i = base, 1
        while get_user_by_login(uname):
            i += 1
            uname = f"{base}{i}"
        user = create_user(uname, email, secrets.token_urlsafe(16), provider="google")
        log_event(user, "signup", f"Registered via Google ({uname})")
    # Optional: cache the Google avatar locally. Fully guarded — a failed
    # download must never block login.
    if profile.get("picture") and not (user.get("profile_pic") or ""):
        try:
            resp = requests.get(profile["picture"], timeout=5)
            if resp.ok and resp.content:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img.thumbnail((256, 256))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                import base64
                from database import update_user
                update_user(user["id"], profile_pic=base64.b64encode(buf.getvalue()).decode())
                user = get_user_by_id(user["id"])
        except Exception:
            pass                      # avatar is cosmetic; never fatal
    do_login(user, via="google")


def _native_google_button():
    """Primary button: Streamlit's built-in OIDC login."""
    if st.button("🌐  Continue with Google", type="primary", width="stretch",
                 key="google_native"):
        st.login()                    # server-side redirect — cannot be framed
    return


def _legacy_google_button():
    """Fallback for the old GOOGLE_CLIENT_ID style secrets."""
    if st.button("🌐  Continue with Google", type="primary", width="stretch",
                 key="google_signin"):
        st.session_state["go_google"] = True
        st.rerun()


def _google_setup_panel():
    """Shown when no Google configuration at all is present."""
    st.button("🌐  Continue with Google", type="primary", width="stretch", disabled=True)
    st.warning("**Google login is off** — no Google credentials were found.\n\n"
               "Add the `[auth]` block shown in **GOOGLE_SETUP.md** under "
               "**Manage app → Settings → Secrets**, then reboot.")
    if st.button("🔍 Check my Google settings", width="stretch", key="diag_btn"):
        st.session_state["show_diag"] = True


def _diagnostics():
    """Real checks against Google, so no one is left staring at a 403 page."""
    st.markdown("#### 🔍 Google login check")
    st.caption("This reads your app secrets and asks Google whether they work.")

    if native_login_configured():
        st.success("✅ `[auth]` secrets found — Streamlit native login (st.login) is active.")
        try:
            auth = st.secrets["auth"]
            cid = str(auth.get("client_id", ""))
            meta = str(auth.get("server_metadata_url", ""))
            st.code(f"client_id            : ...{cid[-32:]}\n"
                    f"server_metadata_url  : {meta}\n"
                    f"redirect_uri needed  : https://<your-app>.streamlit.app{OAUTH_CALLBACK_PATH}")
            if cid and not cid.endswith(".apps.googleusercontent.com"):
                st.error("client_id does not end with '.apps.googleusercontent.com' — it is "
                         "probably the client SECRET pasted into the id field.")
        except Exception as exc:
            st.warning(f"Could not read the [auth] section: {exc}")
    else:
        st.info("No `[auth]` block found, so the app is using the legacy "
                "GOOGLE_CLIENT_ID path. The checks below test those values.")
        for level, msg in diagnose():
            {"ok": st.success, "warn": st.warning, "bad": st.error}[level](msg)

    st.markdown("##### If Google still shows *403 — you do not have access to this page*")
    for i, reason in enumerate(explain_403(), 1):
        st.markdown(f"{i}. {reason}")
    st.info("**The 403 is almost always the Google ACCOUNT, not the code.** "
            "Google Cloud → **Google Auth Platform** → **Audience** → "
            "**Test users** → **+ ADD USERS** → the exact Gmail you sign in with → "
            "**Save** → wait 10 minutes. Or click **Publish app** — this app only asks "
            "for name, email and profile, which needs no Google review.")
    st.markdown("**Redirect URI that must be registered in Google Cloud**")
    st.code(f"https://YOUR-APP.streamlit.app{OAUTH_CALLBACK_PATH}")
    st.caption("st.login() always returns to /oauth2callback. Without that exact URI "
               "registered, Google answers redirect_uri_mismatch.")


def auth_page():
    """Login / sign-up screen. One card, no choices beyond email-or-Google."""
    # A pending redirect to Google, set by the legacy button above.
    if st.session_state.pop("go_google", False):
        redirect_to_google(build_auth_url())          # ends with st.stop()

    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        # The login card is ONE real container. It used to open
        # `<div class="glass auth-card">` in a markdown call and close it ~55
        # lines later; Streamlit renders each markdown call as its own block, so
        # that left an empty rounded box at the top and spilled every widget
        # outside the card.
        card = st.container(key="auth-card", border=False)
        with card:
            st.markdown(f"""
            <div class="auth-head">
              <div class="brand-mini">🪄 {APP_NAME}</div>
              <div class="gradient-title" style="font-size:2rem;">Know what customers really feel</div>
              <div class="subtitle">Pick a product, read what people said, and see which
                parts of it people loved or hated.</div>
              <div class="divider-line"></div>
            </div>
            """, unsafe_allow_html=True)

            err = st.session_state.pop("oauth_error", None)
            if err:
                st.error(f"🔐 {err}")

            # ---- way in #1: Google ----
            if native_login_configured():
                _native_google_button()
            elif is_google_configured():
                _legacy_google_button()
            else:
                _google_setup_panel()

            st.markdown("<div class='or-sep'><span>or use your email</span></div>",
                        unsafe_allow_html=True)
            st.caption(f"build {BUILD}")

            # ---- way in #2: email, behind one toggle ----
            mode = st.radio("Account", ["Log in", "Create account"], horizontal=True,
                            label_visibility="collapsed")

            if mode == "Log in":
                login = st.text_input("Username or Gmail", placeholder="you@gmail.com")
                pwd = st.text_input("Password", type="password", placeholder="••••••••")
                if st.button("Log in", type="secondary", width="stretch"):
                    if not login or not pwd:
                        st.error("Enter your username/Gmail and password.")
                    else:
                        from auth import verify_password
                        user = get_user_by_login(login)
                        if user and verify_password(pwd, user["password_hash"], user["salt"]):
                            do_login(user, via="email")
                        else:
                            st.error("That login didn't match. Check the spelling, or create an account below.")
            else:
                username = st.text_input("Username", placeholder="sneha_21  (3–20 letters, numbers or _)")
                gmail = st.text_input("Gmail", placeholder="you@gmail.com")
                pwd = st.text_input("Password", type="password", placeholder="At least 6 characters, with a number")
                pwd2 = st.text_input("Confirm password", type="password", placeholder="Repeat the password")
                if st.button("Create account", type="secondary", width="stretch"):
                    if not valid_username(username or ""):
                        st.error("Username must be 3–20 characters: letters, numbers or underscore.")
                    elif not valid_gmail(gmail or ""):
                        st.error("Please use a valid **@gmail.com** address.")
                    elif (issues := password_issues(pwd or "")):
                        st.error("Password needs " + ", ".join(issues) + ".")
                    elif pwd != pwd2:
                        st.error("The two passwords don't match.")
                    elif get_user_by_login(username):
                        st.error("That username is already taken.")
                    elif get_user_by_login(gmail):
                        st.error("That Gmail is already registered — log in instead.")
                    else:
                        user = create_user(username, gmail, pwd)
                        log_event(user, "signup", f"New account created ({username})")
                        st.success("Account created. Logging you in… 🎉")
                        do_login(user, via="email")

    if st.session_state.get("show_diag"):
        with c2:
            _diagnostics()
            if st.button("✖ Close check", key="diag_close"):
                st.session_state["show_diag"] = False
                st.rerun()
