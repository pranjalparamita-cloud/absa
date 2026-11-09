"""
views/login.py — one screen, two ways in.

  1. Continue with Google  (the primary button, always first)
  2. Email + password      (behind a single toggle, no separate sign-up hunt)
  3. Create an account     (one extra field in the same form)

Everything that used to need a decision is gone: no demo-account chooser, no
"pick a Google account" demo list, no third button. ONE Gmail rule is enforced
everywhere: the address must end in @gmail.com.
"""
import io
import re
import secrets

import requests
import streamlit as st
from PIL import Image

from auth import do_login, valid_username, valid_gmail, password_issues
from config import APP_NAME
from database import get_user_by_login, get_user_by_id, create_user, log_event
from google_auth import is_google_configured, build_auth_url, redirect_to_google


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
    # Optional extra: cache the Google avatar locally so it keeps working
    # offline. Fully guarded — a missing/failed download must never block login.
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


def _google_button(label="🌐  Continue with Google"):
    """One Google button, wired straight to the real OAuth flow."""
    if is_google_configured():
        if st.button(label, type="primary", width="stretch", key="google_signin"):
            st.session_state["go_google"] = True
            st.rerun()
        return

    # Not configured yet: say so plainly instead of inventing a fake chooser.
    st.button(label, type="primary", width="stretch", disabled=True,
              help="Add GOOGLE_CLIENT_ID / SECRET / REDIRECT_URI to .streamlit/secrets.toml — see GOOGLE_SETUP.md")
    st.caption("⚠️ Google login needs 3 keys in `.streamlit/secrets.toml` — free, "
               "about 10 minutes, see **GOOGLE_SETUP.md**.")


def auth_page():
    """Login / sign-up screen. One card, no choices beyond email-or-Google."""
    # A pending redirect to Google, set by the button above.
    if st.session_state.pop("go_google", False):
        redirect_to_google(build_auth_url())          # ends with st.stop()

    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f"""
        <div class="glass auth-card">
          <div class="brand-mini">🪄 {APP_NAME}</div>
          <div class="gradient-title" style="font-size:2rem;">Know what customers really feel</div>
          <div class="subtitle">Pick a product, read what people said, and see which
            parts of it people loved or hated.</div>
          <div class="divider-line"></div>
        """, unsafe_allow_html=True)

        err = st.session_state.pop("oauth_error", None)
        if err:
            st.error(f"🔐 {err}")

        # ---- way in #1: Google, first and biggest ----
        _google_button()

        st.markdown("<div class='or-sep'><span>or use your email</span></div>", unsafe_allow_html=True)

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

        st.markdown("</div>", unsafe_allow_html=True)
