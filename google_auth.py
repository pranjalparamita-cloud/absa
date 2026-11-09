"""
google_auth.py — REAL "Continue with Google" (OAuth 2.0, free).
---------------------------------------------------------------
Flow:
1. User clicks "Continue with Google" -> we redirect them to Google.
2. Google shows its OWN account chooser with their already-logged-in
   Gmail accounts (prompt="select_account") -> user picks one.
3. Google redirects back to our app with ?code=... -> we exchange the
   code for tokens, fetch the verified email + name + photo, and log in.

One-time setup (free, ~10 min): see GOOGLE_SETUP.md — create a Google
OAuth client, then store these in Streamlit secrets:
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI

If secrets are missing, views/login.py falls back to demo mode.
"""
import secrets as py_secrets
import urllib.parse

import requests
import streamlit as st

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# ---------- configuration (from Streamlit secrets) ----------

def _secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return ""


def google_client_id() -> str:
    return _secret("GOOGLE_CLIENT_ID")


def google_client_secret() -> str:
    return _secret("GOOGLE_CLIENT_SECRET")


def google_redirect_uri() -> str:
    return _secret("GOOGLE_REDIRECT_URI")


def is_google_configured() -> bool:
    """True only when all 3 secrets are present."""
    return bool(google_client_id() and google_client_secret() and google_redirect_uri())


# ---------- step 1: redirect user to Google ----------

def build_auth_url() -> str:
    """Google sign-in URL. prompt=select_account forces the Gmail chooser
    to appear even if only one account is logged in the browser."""
    state = py_secrets.token_urlsafe(24)  # CSRF protection
    st.session_state["oauth_state"] = state
    params = {
        "client_id": google_client_id(),
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


def redirect_to_google(auth_url: str):
    """Same-tab redirect to Google (meta-refresh works inside Streamlit)."""
    st.markdown(
        f"""<div class="glass" style="text-align:center; max-width:480px; margin:10vh auto;">
        <div style="font-size:2.2rem;">🔐</div>
        <h3>Taking you to Google…</h3>
        <p class="small-note">Pick one of your logged-in Gmail accounts on the next screen.</p>
        <meta http-equiv="refresh" content="0;url={auth_url}">
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()


# ---------- step 2+3: handle Google's redirect back to us ----------

def handle_oauth_callback():
    """If Google redirected back (?code=...), verify + fetch the profile.

    Returns (profile_dict_or_None, error_or_None).
    profile = {"email": ..., "name": ..., "picture": ...}
    """
    params = st.query_params
    if "code" not in params and "error" not in params:
        return None, None  # not an OAuth callback, normal page load

    if "error" in params:
        err = params.get("error", "cancelled")
        st.query_params.clear()
        return None, f"Google sign-in was {err}. Please try again."

    code = params.get("code")
    state = params.get("state")
    st.query_params.clear()  # code is one-time-use
    if not state or state != st.session_state.pop("oauth_state", None):
        return None, "Security check failed (session expired). Please click Continue with Google again."

    try:
        token = requests.post(
            GOOGLE_TOKEN_URL,
            data={"code": code,
                  "client_id": google_client_id(),
                  "client_secret": google_client_secret(),
                  "redirect_uri": google_redirect_uri(),
                  "grant_type": "authorization_code"},
            timeout=20,
        ).json()
        if "access_token" not in token:
            detail = token.get("error_description", token.get("error", "unknown error"))
            return None, f"Google login failed: {detail}"
        me = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=20,
        ).json()
        if not me.get("email"):
            return None, "Google did not return an email address."
        return {"email": me["email"], "name": me.get("name", ""),
                "picture": me.get("picture", "")}, None
    except requests.RequestException as e:
        return None, f"Could not reach Google: {e}"
