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
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
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


_PLACEHOLDERS = ("paste_your", "your-client-id", "your_client", "your-app", "xxxxxxxx", "changeme")


def _looks_real(value: str) -> bool:
    """Reject the example values from secrets.toml.example so the UI does not
    pretend Google is configured when it is not."""
    low = (value or "").lower()
    if not low or len(low) < 20:
        return False
    return not any(marker in low for marker in _PLACEHOLDERS)


def is_google_configured() -> bool:
    """True only when all 3 secrets are present AND are not placeholder text."""
    return (_looks_real(google_client_id())
            and _looks_real(google_client_secret())
            and bool(google_redirect_uri().startswith(("https://", "http://"))))


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


# ---------------------------------------------------------------------------
# DIAGNOSTICS — runs a real request against Google so the app can say exactly
# which value is wrong instead of leaving the user on Google's 403 page.
# ---------------------------------------------------------------------------

def _secret_source(name: str) -> str:
    """Say WHERE a secret was found, so a stale value is easy to spot."""
    try:
        if name not in st.secrets:
            return "NOT SET"
    except Exception:
        return "secrets unavailable"
    raw = str(st.secrets.get(name, ""))
    if not raw:
        return "empty"
    return f"set ({len(raw)} chars, ends ...{raw[-6:]})"


def explain_403() -> list:
    """Plain-language reasons Google shows the generic 403 page."""
    return [
        "**The Google account you picked is not a Test user.** In Testing mode only "
        "the emails listed under Google Auth Platform → Audience → Test users may sign in.",
        "**You opened the OAuth client from a different Cloud project** than the one whose "
        "consent screen you configured.",
        "**The Client ID / Secret in Streamlit do not belong to the client you registered** "
        "(for example after regenerating the secret).",
        "**The OAuth client is not type 'Web application'** (Desktop/Android clients cannot "
        "use a browser redirect).",
    ]


def _decode_autherror(location: str) -> str:
    """Google encodes the reason in a base64 protobuf inside the redirect URL.
    Decode what we can so the message is readable."""
    import base64
    from urllib.parse import parse_qs, urlparse
    try:
        raw = parse_qs(urlparse(location).query).get("authError", [""])[0]
        if not raw:
            return "unknown reason"
        padded = raw + "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode("latin-1", "ignore")
        words = "".join(ch if 31 < ord(ch) < 127 else " " for ch in decoded)
        words = " ".join(words.split())
        return words[:180] or "unknown reason"
    except Exception:
        return "unknown reason"


def diagnose() -> list:
    """Return a list of (level, message) lines.

    level: 'ok' | 'warn' | 'bad'
    This performs a real network call to Google with the configured client_id and
    redirect_uri, so it distinguishes 'Google rejects these keys' from
    'the keys are fine, the problem is the account / test users'.
    """
    out = []
    cid = google_client_id()
    secret = google_client_secret()
    uri = google_redirect_uri()

    # 1. secrets present and plausible
    if not cid:
        out.append(("bad", "GOOGLE_CLIENT_ID is missing or empty."))
    elif not cid.endswith(".apps.googleusercontent.com"):
        out.append(("bad", f"GOOGLE_CLIENT_ID looks wrong — it must end with "
                           f"'.apps.googleusercontent.com'. Found: {cid[-40:]}"))
    else:
        out.append(("ok", f"Client ID shape looks right — {_secret_source('GOOGLE_CLIENT_ID')}"))

    if not secret:
        out.append(("bad", "GOOGLE_CLIENT_SECRET is missing or empty."))
    elif secret.lower().startswith("gocspx-"):
        out.append(("ok", f"Client secret shape looks right — {_secret_source('GOOGLE_CLIENT_SECRET')}"))
    else:
        out.append(("warn", "GOOGLE_CLIENT_SECRET does not start with 'GOCSPX-'. "
                            "Double-check you copied the secret, not the client ID."))

    if not uri:
        out.append(("bad", "GOOGLE_REDIRECT_URI is missing or empty."))
    elif not uri.startswith("https://"):
        out.append(("bad", f"GOOGLE_REDIRECT_URI must start with https:// — found: {uri}"))
    else:
        out.append(("ok", f"Redirect URI: {uri}"))
        if not uri.endswith("/"):
            out.append(("warn", "Redirect URI has no trailing '/'. Google usually needs one, "
                                "and it must match the Cloud console EXACTLY."))
        if ".streamlit.app" in uri and "YOUR-APP" in uri.upper():
            out.append(("bad", "Redirect URI still contains the placeholder YOUR-APP. "
                               "Replace it with your real app URL."))

    if any(level == "bad" for level, _ in out):
        return out          # no point calling Google with broken values

    # 2. ask Google about the client_id / redirect_uri pair.
    #    Google answers with a 302: a normal sign-in URL when the client exists,
    #    or /signin/oauth/error?authError=... (base64 protobuf) when it does not.
    try:
        r = requests.get(
            "https://accounts.google.com/o/oauth2/v2/auth",
            params={"client_id": cid, "redirect_uri": uri, "response_type": "code",
                    "scope": "openid email profile", "prompt": "select_account"},
            allow_redirects=False, timeout=20,
        )
        location = r.headers.get("Location", "") or ""
        if "signin/oauth/error" in location or "invalid_client" in location:
            reason = _decode_autherror(location)
            out.append(("bad", f"GOOGLE REJECTED THIS CLIENT ID — it says: \"{reason}\". "
                               "That Client ID does not exist in your Cloud project. Re-copy it "
                               "from Google Cloud → Google Auth Platform → Clients."))
        elif "redirect_uri_mismatch" in location:
            out.append(("bad", f"REDIRECT URI MISMATCH — Google does not allow {uri} "
                               "for this client. Add it under Clients → your client → "
                               "Authorized redirect URIs (copy it character for character)."))
        elif "access_blocked" in location:
            out.append(("bad", "ACCESS BLOCKED — the Google account you sign in with is not "
                               "allowed. Add it under Audience → Test users."))
        else:
            out.append(("ok", "Google ACCEPTED this Client ID and redirect URI "
                              "(it reached the real sign-in flow)."))
    except requests.RequestException as exc:
        out.append(("warn", f"Could not reach Google to verify: {exc}"))

    out.append(("warn", "If the checks above are all OK, the 403 is caused by the GOOGLE "
                        "ACCOUNT, not the code: add that exact Gmail under "
                        "Google Auth Platform → Audience → Test users, or click 'Publish app'."))
    return out


# ---------------------------------------------------------------------------
# STREAMLIT NATIVE LOGIN (st.login)
# ---------------------------------------------------------------------------
# The hand-rolled flow below builds a URL and relies on the browser following a
# <meta refresh>. That breaks when the page is rendered in a framed context:
# Google refuses to render its OAuth screen inside a frame and shows
# "403 - That's an error / you do not have access to this page".
#
# st.login() is Streamlit's built-in OIDC client: the Streamlit SERVER issues a
# real 302 to Google, so the consent screen is always top-level and can never be
# framed. It needs an [auth] section in secrets; nothing else.

def native_login_configured() -> bool:
    """True when secrets contain a usable [auth] section for Google."""
    try:
        auth = st.secrets.get("auth", None)
        if not auth:
            return False
        if not auth.get("client_id") or not auth.get("client_secret"):
            return False
        meta = auth.get("server_metadata_url", "") or ""
        return "accounts.google.com" in meta or "google" in str(meta).lower()
    except Exception:
        return False


def current_native_user():
    """Return {'email', 'name', 'picture'} from st.user, or None."""
    try:
        if not getattr(st.user, "is_logged_in", False):
            return None
        return {
            "email": st.user.get("email", "") or "",
            "name": st.user.get("name", "") or "",
            "picture": st.user.get("picture", "") or "",
        }
    except Exception:
        return None
