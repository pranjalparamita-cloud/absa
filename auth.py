"""
auth.py — Authentication helpers.
--------------------------------
- Password hashing / verification (PBKDF2-HMAC-SHA256, salted)
- Gmail Authenticator validation (only @gmail.com allowed)
- Username + password-strength validation
- do_login(): starts a tracked user session
"""
import hashlib
import re
import secrets
import uuid
from datetime import datetime

import streamlit as st

from database import get_user_by_id, update_user, log_event


# ---------- password hashing ----------

def hash_password(password: str, salt_hex: str = None):
    if salt_hex is None:
        salt_hex = secrets.token_hex(16)
    phash = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000).hex()
    return phash, salt_hex


def verify_password(password: str, phash: str, salt_hex: str) -> bool:
    test, _ = hash_password(password, salt_hex)
    return secrets.compare_digest(test, phash)


# ---------- validators ----------

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@gmail\.com$", re.IGNORECASE)
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def valid_gmail(email: str) -> bool:
    """Gmail Authenticator: only @gmail.com addresses pass."""
    return bool(EMAIL_RE.match((email or "").strip()))


def valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match((username or "").strip()))


def password_issues(pwd: str):
    """Return a list of missing requirements (empty list = strong enough)."""
    issues = []
    if len(pwd or "") < 6:
        issues.append("at least 6 characters")
    if not re.search(r"[A-Za-z]", pwd or ""):
        issues.append("one letter")
    if not re.search(r"\d", pwd or ""):
        issues.append("one number")
    return issues


# ---------- session ----------

def do_login(user, via="email"):
    """Start a logged-in session, stamp last_login, track the event."""
    st.session_state.user = get_user_by_id(user["id"])
    st.session_state.session_id = uuid.uuid4().hex[:12]
    st.session_state.login_time = datetime.now()
    st.session_state.page = "🛍️ Product Explorer"
    update_user(user["id"], last_login=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log_event(st.session_state.user, "login" if via == "email" else "google_login",
              f"Logged in via {via}")
    st.rerun()
