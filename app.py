"""
AspectLens — Aspect-Based Sentiment Analytics  (complete app, ONE file)
=======================================================================
Login, product search, live suggestions, automatic NLP analysis, dashboard,
profile, history and the admin panel — all in this single module.

Why one file? Deployments used to fail with
    ModuleNotFoundError: No module named 'views'
because a folder did not survive the upload to GitHub. A single file cannot
lose a folder.

Run locally:        streamlit run app.py
Streamlit Cloud:    main file path = app.py   (this file renamed)
"""
import base64
import hashlib
import html
import importlib
import importlib.util
import io
import os
import random
import re
import secrets
import sqlite3
import sys
import tempfile
import traceback
import urllib.parse
import uuid
import zipfile
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from PIL import Image



# ==========================================================================
# CONFIG.PY
# ==========================================================================

"""
config.py — Central configuration for AspectLens.
------------------------------------------------
All app-wide constants live here (app name, file paths, chart colours,
platform badge colours) so every other file imports from ONE place.
"""
import os
APP_NAME = 'AspectLens'
OAUTH_CALLBACK_PATH = '/oauth2callback'
BUILD = 'v6 · 09 Nov 2026'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _writable(folder: str) -> bool:
    """True when we can actually create a file in `folder`."""
    try:
        probe = os.path.join(folder, '.write_test')
        with open(probe, 'w') as fh:
            fh.write('ok')
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
    override = os.environ.get('ABSA_DB_PATH', '').strip()
    if override:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(override)), exist_ok=True)
        except Exception:
            pass
        return override
    if _writable(BASE_DIR):
        return os.path.join(BASE_DIR, 'absa.db')
    import tempfile
    return os.path.join(tempfile.gettempdir(), 'absa.db')
DB_PATH = _resolve_db_path()
POS_COLOR = '#10b981'
NEG_COLOR = '#f43f5e'
NEU_COLOR = '#8b5cf6'
ACCENT = '#9333ea'



# ==========================================================================
# DATABASE.PY
# ==========================================================================

"""
database.py — SQLite database layer (100% free, file-based).
------------------------------------------------------------
Tables:
  users            -> accounts (username, gmail, hashed password, photo, ...)
  catalog_products -> built-in 5,000-item product catalog
  catalog_reviews  -> generated mixed demonstration review samples
  activity_logs    -> every user action (for the Admin tracking panel)
  analysis_history -> every product review analysis each user runs
                     (product_id   = catalog product id
                      product_name = analysed catalog item
                      platform     = catalog source label)

All other files talk to the DB ONLY through the functions below.
"""
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime

def get_conn():
    """Open a fresh DB connection (safe for Streamlit's threading).

    `timeout` + `busy_timeout` matter on Streamlit Cloud: every visitor session
    runs its own process, so two users can hit the database at the same instant
    (typically both triggering the first-run catalog seed). Without a busy
    timeout SQLite raises "database is locked" immediately instead of waiting.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA busy_timeout = 30000')
    except Exception:
        pass
    return conn

def init_db():
    """Create tables + seed demo accounts. Runs once at app startup."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("\n        CREATE TABLE IF NOT EXISTS users (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            username TEXT UNIQUE NOT NULL,\n            email TEXT UNIQUE NOT NULL,\n            password_hash TEXT NOT NULL,\n            salt TEXT NOT NULL,\n            profile_pic TEXT DEFAULT '',\n            bio TEXT DEFAULT '',\n            phone TEXT DEFAULT '',\n            is_admin INTEGER DEFAULT 0,\n            provider TEXT DEFAULT 'email',\n            created_at TEXT NOT NULL,\n            last_login TEXT DEFAULT ''\n        )\n    ")
    cur.execute('\n        CREATE TABLE IF NOT EXISTS catalog_products (\n            id INTEGER PRIMARY KEY,\n            sku TEXT UNIQUE NOT NULL,\n            title TEXT NOT NULL,\n            brand TEXT NOT NULL,\n            category TEXT NOT NULL,\n            product_type TEXT NOT NULL,\n            review_count INTEGER NOT NULL DEFAULT 0,\n            price REAL DEFAULT 0\n        )\n    ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS catalog_reviews (\n            id INTEGER PRIMARY KEY,\n            product_id INTEGER NOT NULL,\n            reviewer TEXT NOT NULL,\n            rating REAL,\n            review_text TEXT NOT NULL,\n            review_date TEXT,\n            seed_sentiment TEXT NOT NULL,\n            FOREIGN KEY(product_id) REFERENCES catalog_products(id)\n        )\n    ')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_catalog_products_title ON catalog_products(title)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_catalog_products_category ON catalog_products(category)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_catalog_reviews_product ON catalog_reviews(product_id)')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS activity_logs (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            user_id INTEGER,\n            username TEXT,\n            email TEXT,\n            event_type TEXT,\n            detail TEXT,\n            timestamp TEXT,\n            session_id TEXT\n        )\n    ')
    cur.execute('\n        CREATE TABLE IF NOT EXISTS analysis_history (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            user_id INTEGER,\n            product_id TEXT,\n            product_name TEXT,\n            platform TEXT,\n            total_reviews INTEGER,\n            positive INTEGER,\n            neutral INTEGER,\n            negative INTEGER,\n            overall TEXT,\n            timestamp TEXT\n        )\n    ')
    conn.commit()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    seeds = [('admin', 'admin@gmail.com', 'Admin@123', 1, 'email'), ('demo', 'demo@gmail.com', 'Demo@123', 0, 'email')]
    for username, email, pwd, is_admin, provider in seeds:
        cur.execute('SELECT id FROM users WHERE email=?', (email,))
        if cur.fetchone() is None:
            phash, salt = hash_password(pwd)
            cur.execute('INSERT INTO users (username,email,password_hash,salt,is_admin,provider,created_at)\n                   VALUES (?,?,?,?,?,?,?)', (username, email, phash, salt, is_admin, provider, now))
    conn.commit()
    try:
        ensure_catalog_seed(conn)
    except Exception:
        conn.rollback()
    conn.close()

def row_to_dict(row):
    return dict(row) if row else None

def create_user(username, email, password, provider='email', is_admin=0):
    """Create an account (password is hashed) and return the user dict."""
    conn = get_conn()
    cur = conn.cursor()
    phash, salt = hash_password(password)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute('INSERT INTO users (username,email,password_hash,salt,is_admin,provider,created_at)\n           VALUES (?,?,?,?,?,?,?)', (username.strip(), email.strip().lower(), phash, salt, is_admin, provider, now))
    uid = cur.lastrowid
    conn.commit()
    cur.execute('SELECT * FROM users WHERE id=?', (uid,))
    user = row_to_dict(cur.fetchone())
    conn.close()
    return user

def get_user_by_login(login: str):
    """Find a user by username OR email (case-insensitive)."""
    conn = get_conn()
    cur = conn.cursor()
    login = login.strip().lower()
    cur.execute('SELECT * FROM users WHERE LOWER(email)=? OR LOWER(username)=?', (login, login))
    user = row_to_dict(cur.fetchone())
    conn.close()
    return user

def get_user_by_id(uid: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id=?', (uid,))
    user = row_to_dict(cur.fetchone())
    conn.close()
    return user

def update_user(uid: int, **fields):
    """Update allowed user fields: username, password_hash, salt,
    profile_pic, bio, phone, last_login."""
    allowed = {'username', 'password_hash', 'salt', 'profile_pic', 'bio', 'phone', 'last_login'}
    sets = [f'{k}=?' for k in fields if k in allowed]
    if not sets:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", [fields[k] for k in fields if k in allowed] + [uid])
    conn.commit()
    conn.close()

def _get(user, key, default=None):
    """Read a field from a dict OR a sqlite3.Row without raising."""
    try:
        value = user[key]
    except (KeyError, IndexError, TypeError):
        try:
            value = user.get(key, default)
        except AttributeError:
            return default
    return value if value is not None else default

def log_event(user, event_type: str, detail: str=''):
    """Record a user action (login, search, analyse, logout, ...) for Admin."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('INSERT INTO activity_logs (user_id,username,email,event_type,detail,timestamp,session_id)\n               VALUES (?,?,?,?,?,?,?)', (_get(user, 'id'), _get(user, 'username', 'guest'), _get(user, 'email', ''), event_type, detail[:500], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), st.session_state.get('session_id', '')))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_analysis(user_id, dataset_id, item_name, dataset_name, total, pos, neu, neg, overall):
    """Save one analysis run to history."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT INTO analysis_history\n           (user_id,product_id,product_name,platform,total_reviews,positive,neutral,negative,overall,timestamp)\n           VALUES (?,?,?,?,?,?,?,?,?,?)', (user_id, str(dataset_id), item_name, dataset_name, total, pos, neu, neg, overall, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def fetch_df(query, params=()):
    """Run a SELECT query and return a pandas DataFrame."""
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df



# ==========================================================================
# AUTH.PY
# ==========================================================================

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

def hash_password(password: str, salt_hex: str=None):
    if salt_hex is None:
        salt_hex = secrets.token_hex(16)
    phash = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 100000).hex()
    return (phash, salt_hex)

def verify_password(password: str, phash: str, salt_hex: str) -> bool:
    test, _ = hash_password(password, salt_hex)
    return secrets.compare_digest(test, phash)
EMAIL_RE = re.compile('^[a-zA-Z0-9._%+-]+@gmail\\.com$', re.IGNORECASE)
USERNAME_RE = re.compile('^[A-Za-z0-9_]{3,20}$')

def valid_gmail(email: str) -> bool:
    """Gmail Authenticator: only @gmail.com addresses pass."""
    return bool(EMAIL_RE.match((email or '').strip()))

def valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match((username or '').strip()))

def password_issues(pwd: str):
    """Return a list of missing requirements (empty list = strong enough)."""
    issues = []
    if len(pwd or '') < 6:
        issues.append('at least 6 characters')
    if not re.search('[A-Za-z]', pwd or ''):
        issues.append('one letter')
    if not re.search('\\d', pwd or ''):
        issues.append('one number')
    return issues

def do_login(user, via='email'):
    """Start a logged-in session, stamp last_login, track the event."""
    st.session_state.user = get_user_by_id(user['id'])
    st.session_state.session_id = uuid.uuid4().hex[:12]
    st.session_state.login_time = datetime.now()
    st.session_state.page = '🛍️ Products'
    update_user(user['id'], last_login=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log_event(st.session_state.user, 'login' if via == 'email' else 'google_login', f'Logged in via {via}')
    st.rerun()



# ==========================================================================
# GOOGLE_AUTH.PY
# ==========================================================================

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
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'

def _secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, '') or '').strip()
    except Exception:
        return ''

def google_client_id() -> str:
    return _secret('GOOGLE_CLIENT_ID')

def google_client_secret() -> str:
    return _secret('GOOGLE_CLIENT_SECRET')

def google_redirect_uri() -> str:
    return _secret('GOOGLE_REDIRECT_URI')
_PLACEHOLDERS = ('paste_your', 'your-client-id', 'your_client', 'your-app', 'xxxxxxxx', 'changeme')

def _looks_real(value: str) -> bool:
    """Reject the example values from secrets.toml.example so the UI does not
    pretend Google is configured when it is not."""
    low = (value or '').lower()
    if not low or len(low) < 20:
        return False
    return not any((marker in low for marker in _PLACEHOLDERS))

def is_google_configured() -> bool:
    """True only when all 3 secrets are present AND are not placeholder text."""
    return _looks_real(google_client_id()) and _looks_real(google_client_secret()) and bool(google_redirect_uri().startswith(('https://', 'http://')))

def build_auth_url() -> str:
    """Google sign-in URL. prompt=select_account forces the Gmail chooser
    to appear even if only one account is logged in the browser."""
    state = py_secrets.token_urlsafe(24)
    st.session_state['oauth_state'] = state
    params = {'client_id': google_client_id(), 'redirect_uri': google_redirect_uri(), 'response_type': 'code', 'scope': 'openid email profile', 'state': state, 'prompt': 'select_account'}
    return GOOGLE_AUTH_URL + '?' + urllib.parse.urlencode(params)

def redirect_to_google(auth_url: str):
    """Same-tab redirect to Google (meta-refresh works inside Streamlit)."""
    st.markdown(f'<div class="glass" style="text-align:center; max-width:480px; margin:10vh auto;">\n        <div style="font-size:2.2rem;">🔐</div>\n        <h3>Taking you to Google…</h3>\n        <p class="small-note">Pick one of your logged-in Gmail accounts on the next screen.</p>\n        <meta http-equiv="refresh" content="0;url={auth_url}">\n        </div>', unsafe_allow_html=True)
    st.stop()

def handle_oauth_callback():
    """If Google redirected back (?code=...), verify + fetch the profile.

    Returns (profile_dict_or_None, error_or_None).
    profile = {"email": ..., "name": ..., "picture": ...}
    """
    params = st.query_params
    if 'code' not in params and 'error' not in params:
        return (None, None)
    if 'error' in params:
        err = params.get('error', 'cancelled')
        st.query_params.clear()
        return (None, f'Google sign-in was {err}. Please try again.')
    code = params.get('code')
    state = params.get('state')
    st.query_params.clear()
    if not state or state != st.session_state.pop('oauth_state', None):
        return (None, 'Security check failed (session expired). Please click Continue with Google again.')
    try:
        token = requests.post(GOOGLE_TOKEN_URL, data={'code': code, 'client_id': google_client_id(), 'client_secret': google_client_secret(), 'redirect_uri': google_redirect_uri(), 'grant_type': 'authorization_code'}, timeout=20).json()
        if 'access_token' not in token:
            detail = token.get('error_description', token.get('error', 'unknown error'))
            return (None, f'Google login failed: {detail}')
        me = requests.get(GOOGLE_USERINFO_URL, headers={'Authorization': f"Bearer {token['access_token']}"}, timeout=20).json()
        if not me.get('email'):
            return (None, 'Google did not return an email address.')
        return ({'email': me['email'], 'name': me.get('name', ''), 'picture': me.get('picture', '')}, None)
    except requests.RequestException as e:
        return (None, f'Could not reach Google: {e}')

def _secret_source(name: str) -> str:
    """Say WHERE a secret was found, so a stale value is easy to spot."""
    try:
        if name not in st.secrets:
            return 'NOT SET'
    except Exception:
        return 'secrets unavailable'
    raw = str(st.secrets.get(name, ''))
    if not raw:
        return 'empty'
    return f'set ({len(raw)} chars, ends ...{raw[-6:]})'

def explain_403() -> list:
    """Plain-language reasons Google shows the generic 403 page."""
    return ['**The Google account you picked is not a Test user.** In Testing mode only the emails listed under Google Auth Platform → Audience → Test users may sign in.', '**You opened the OAuth client from a different Cloud project** than the one whose consent screen you configured.', '**The Client ID / Secret in Streamlit do not belong to the client you registered** (for example after regenerating the secret).', "**The OAuth client is not type 'Web application'** (Desktop/Android clients cannot use a browser redirect)."]

def _decode_autherror(location: str) -> str:
    """Google encodes the reason in a base64 protobuf inside the redirect URL.
    Decode what we can so the message is readable."""
    import base64
    from urllib.parse import parse_qs, urlparse
    try:
        raw = parse_qs(urlparse(location).query).get('authError', [''])[0]
        if not raw:
            return 'unknown reason'
        padded = raw + '=' * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode('latin-1', 'ignore')
        words = ''.join((ch if 31 < ord(ch) < 127 else ' ' for ch in decoded))
        words = ' '.join(words.split())
        return words[:180] or 'unknown reason'
    except Exception:
        return 'unknown reason'

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
    if not cid:
        out.append(('bad', 'GOOGLE_CLIENT_ID is missing or empty.'))
    elif not cid.endswith('.apps.googleusercontent.com'):
        out.append(('bad', f"GOOGLE_CLIENT_ID looks wrong — it must end with '.apps.googleusercontent.com'. Found: {cid[-40:]}"))
    else:
        out.append(('ok', f"Client ID shape looks right — {_secret_source('GOOGLE_CLIENT_ID')}"))
    if not secret:
        out.append(('bad', 'GOOGLE_CLIENT_SECRET is missing or empty.'))
    elif secret.lower().startswith('gocspx-'):
        out.append(('ok', f"Client secret shape looks right — {_secret_source('GOOGLE_CLIENT_SECRET')}"))
    else:
        out.append(('warn', "GOOGLE_CLIENT_SECRET does not start with 'GOCSPX-'. Double-check you copied the secret, not the client ID."))
    if not uri:
        out.append(('bad', 'GOOGLE_REDIRECT_URI is missing or empty.'))
    elif not uri.startswith('https://'):
        out.append(('bad', f'GOOGLE_REDIRECT_URI must start with https:// — found: {uri}'))
    else:
        out.append(('ok', f'Redirect URI: {uri}'))
        if not uri.endswith('/'):
            out.append(('warn', "Redirect URI has no trailing '/'. Google usually needs one, and it must match the Cloud console EXACTLY."))
        if '.streamlit.app' in uri and 'YOUR-APP' in uri.upper():
            out.append(('bad', 'Redirect URI still contains the placeholder YOUR-APP. Replace it with your real app URL.'))
    if any((level == 'bad' for level, _ in out)):
        return out
    try:
        r = requests.get('https://accounts.google.com/o/oauth2/v2/auth', params={'client_id': cid, 'redirect_uri': uri, 'response_type': 'code', 'scope': 'openid email profile', 'prompt': 'select_account'}, allow_redirects=False, timeout=20)
        location = r.headers.get('Location', '') or ''
        if 'signin/oauth/error' in location or 'invalid_client' in location:
            reason = _decode_autherror(location)
            out.append(('bad', f'GOOGLE REJECTED THIS CLIENT ID — it says: "{reason}". That Client ID does not exist in your Cloud project. Re-copy it from Google Cloud → Google Auth Platform → Clients.'))
        elif 'redirect_uri_mismatch' in location:
            out.append(('bad', f'REDIRECT URI MISMATCH — Google does not allow {uri} for this client. Add it under Clients → your client → Authorized redirect URIs (copy it character for character).'))
        elif 'access_blocked' in location:
            out.append(('bad', 'ACCESS BLOCKED — the Google account you sign in with is not allowed. Add it under Audience → Test users.'))
        else:
            out.append(('ok', 'Google ACCEPTED this Client ID and redirect URI (it reached the real sign-in flow).'))
    except requests.RequestException as exc:
        out.append(('warn', f'Could not reach Google to verify: {exc}'))
    out.append(('warn', "If the checks above are all OK, the 403 is caused by the GOOGLE ACCOUNT, not the code: add that exact Gmail under Google Auth Platform → Audience → Test users, or click 'Publish app'."))
    return out

def native_login_configured() -> bool:
    """True when secrets contain a usable [auth] section for Google."""
    try:
        auth = st.secrets.get('auth', None)
        if not auth:
            return False
        if not auth.get('client_id') or not auth.get('client_secret'):
            return False
        meta = auth.get('server_metadata_url', '') or ''
        return 'accounts.google.com' in meta or 'google' in str(meta).lower()
    except Exception:
        return False

def current_native_user():
    """Return {'email', 'name', 'picture'} from st.user, or None."""
    try:
        if not getattr(st.user, 'is_logged_in', False):
            return None
        return {'email': st.user.get('email', '') or '', 'name': st.user.get('name', '') or '', 'picture': st.user.get('picture', '') or ''}
    except Exception:
        return None



# ==========================================================================
# CATALOG.PY
# ==========================================================================

"""
catalog.py — Built-in 5,000-item product discovery catalog.
-----------------------------------------------------------
The catalog uses recognised consumer brands and product categories, while the
specific product-style listings and review samples are generated demonstration
data. They are intentionally labelled in the UI as demo data; they are NOT
represented as scraped or customer-authored reviews.

At first app launch, ensure_catalog_seed() creates:
  catalog_products  : 5,000 searchable products (500 in each of 10 categories)
  catalog_reviews   : 50,000 mixed positive / neutral / negative review samples
"""
import random
from datetime import date, timedelta
CATALOG_VERSION = 'catalog-demo-v3'
REVIEWS_PER_PRODUCT = 10
CATEGORY_SPECS = [('Electronics', ['Samsung', 'Sony', 'LG', 'Panasonic', 'Philips', 'JBL', 'Bose', 'Canon', 'Nikon', 'Xiaomi'], ['4K Smart TV', 'Noise Cancelling Headphones', 'Portable Bluetooth Speaker', 'Soundbar', 'Mirrorless Camera', 'Smart Projector', 'Wireless Earbuds', 'Home Theatre System', 'Digital Camera', 'LED Monitor']), ('Mobile Accessories', ['Anker', 'Belkin', 'Spigen', 'UGREEN', 'ESR', 'OtterBox', 'Baseus', 'Portronics', 'boAt', 'Ambrane'], ['USB-C GaN Charger', 'Magnetic Power Bank', 'Protective Phone Case', 'Tempered Glass Pack', 'Fast Charging Cable', 'Wireless Charging Stand', 'Car Phone Mount', 'Bluetooth Tracker', 'Mobile Tripod', 'Laptop Sleeve']), ('Computers & Gaming', ['Dell', 'HP', 'Lenovo', 'ASUS', 'Acer', 'MSI', 'Logitech', 'Razer', 'Corsair', 'SteelSeries'], ['Gaming Laptop', 'Mechanical Keyboard', 'Wireless Mouse', '27-inch Monitor', 'Gaming Headset', 'USB-C Dock', 'External SSD', 'Wi-Fi Router', 'Webcam', 'Gaming Controller']), ('Home Appliances', ['Whirlpool', 'Bosch', 'Haier', 'LG', 'Samsung', 'Philips', 'Bajaj', 'Kent', 'Dyson', 'Havells'], ['Air Fryer', 'Water Purifier', 'Robot Vacuum', 'Microwave Oven', 'Front Load Washer', 'Air Purifier', 'Mixer Grinder', 'Coffee Maker', 'Electric Kettle', 'Ceiling Fan']), ('Automotive Parts', ['Bosch', 'Denso', 'NGK', 'Valeo', 'MANN-FILTER', 'SKF', 'Monroe', 'Gates', 'Brembo', 'Castrol'], ['Brake Pad Set', 'Engine Air Filter', 'Oil Filter', 'Spark Plug Kit', 'Wiper Blade Pair', 'Drive Belt', 'Wheel Bearing Kit', 'Clutch Cable', 'Fuel Pump Module', 'Shock Absorber']), ('Automotive Accessories', ['Michelin', '3M', 'Garmin', 'Pioneer', 'JBL', 'Philips', 'Bosch', "Meguiar's", 'Goodyear', 'Turtle Wax'], ['Dash Camera', 'Tyre Inflator', 'Car Vacuum Cleaner', 'Seat Cover Set', 'Reverse Camera', 'Car Stereo', 'Phone Holder', 'Car Care Kit', 'LED Headlight Pair', 'Roof Carrier']), ('Home & Kitchen', ['Prestige', 'Hawkins', 'Philips', 'Borosil', 'Tefal', 'IKEA', 'Milton', 'Pigeon', 'Bajaj', 'Kent'], ['Induction Cooktop', 'Non-stick Cookware Set', 'Storage Container Set', 'Vacuum Flask', 'Kitchen Scale', 'Water Bottle Set', 'Knife Set', 'Clothes Drying Rack', 'Table Lamp', 'Food Chopper']), ('Fashion & Beauty', ['Nike', 'Adidas', 'Puma', 'Skechers', "Levi's", 'Maybelline', "L'Oréal", 'Nivea', 'Dove', 'Lakmé'], ['Running Shoes', 'Everyday Backpack', 'Sports T-Shirt', 'Analog Watch', 'Sunglasses', 'Skin Care Set', 'Hair Dryer', 'Fragrance Gift Set', 'Makeup Kit', 'Travel Wallet']), ('Sports & Outdoors', ['Decathlon', 'Nike', 'Adidas', 'Puma', 'Yonex', 'Wilson', 'Coleman', 'Quechua', 'Nivia', 'Cosco'], ['Yoga Mat', 'Badminton Racket', 'Cricket Bat', 'Camping Tent', 'Trekking Backpack', 'Fitness Tracker', 'Resistance Band Set', 'Football', 'Cycling Helmet', 'Waterproof Jacket']), ('Books & Office', ['HP', 'Canon', 'Epson', 'Brother', 'Casio', 'Faber-Castell', 'Moleskine', 'Parker', 'Kangaro', 'Classmate'], ['Wireless Printer', 'Ink Cartridge Set', 'Scientific Calculator', 'Premium Notebook', 'Ball Pen Set', 'Desk Organiser', 'Document Scanner', 'Label Maker', 'Stapler Set', 'Office Chair'])]
TYPE_PRICE = {'4K Smart TV': (18999, 129999), 'Noise Cancelling Headphones': (2999, 34999), 'Portable Bluetooth Speaker': (1499, 24999), 'Soundbar': (4999, 59999), 'Mirrorless Camera': (39999, 189999), 'Smart Projector': (12999, 89999), 'Wireless Earbuds': (1499, 24999), 'Home Theatre System': (8999, 89999), 'Digital Camera': (9999, 79999), 'LED Monitor': (6999, 54999), 'USB-C GaN Charger': (899, 4499), 'Magnetic Power Bank': (999, 4999), 'Protective Phone Case': (299, 1999), 'Tempered Glass Pack': (199, 1299), 'Fast Charging Cable': (199, 1499), 'Wireless Charging Stand': (899, 3999), 'Car Phone Mount': (399, 2499), 'Bluetooth Tracker': (999, 3999), 'Mobile Tripod': (499, 2999), 'Laptop Sleeve': (499, 2999), 'Gaming Laptop': (44999, 249999), 'Mechanical Keyboard': (1999, 14999), 'Wireless Mouse': (499, 7999), '27-inch Monitor': (9999, 44999), 'Gaming Headset': (1499, 19999), 'USB-C Dock': (1999, 19999), 'External SSD': (2999, 24999), 'Wi-Fi Router': (999, 14999), 'Webcam': (1299, 12999), 'Gaming Controller': (1499, 9999), 'Air Fryer': (2999, 18999), 'Water Purifier': (6999, 32999), 'Robot Vacuum': (9999, 64999), 'Microwave Oven': (4999, 29999), 'Front Load Washer': (18999, 64999), 'Air Purifier': (5999, 39999), 'Mixer Grinder': (1899, 9999), 'Coffee Maker': (1999, 24999), 'Electric Kettle': (699, 4999), 'Ceiling Fan': (999, 7999), 'Brake Pad Set': (899, 7999), 'Engine Air Filter': (499, 3999), 'Oil Filter': (299, 2499), 'Spark Plug Kit': (399, 3999), 'Wiper Blade Pair': (399, 2999), 'Drive Belt': (599, 4999), 'Wheel Bearing Kit': (899, 6999), 'Clutch Cable': (399, 2999), 'Fuel Pump Module': (1999, 14999), 'Shock Absorber': (1499, 12999), 'Dash Camera': (1999, 18999), 'Tyre Inflator': (899, 4999), 'Car Vacuum Cleaner': (999, 6999), 'Seat Cover Set': (1499, 12999), 'Reverse Camera': (1299, 9999), 'Car Stereo': (2999, 29999), 'Phone Holder': (299, 1999), 'Car Care Kit': (699, 4999), 'LED Headlight Pair': (999, 8999), 'Roof Carrier': (2999, 18999), 'Induction Cooktop': (1499, 9999), 'Non-stick Cookware Set': (999, 9999), 'Storage Container Set': (399, 3999), 'Vacuum Flask': (399, 2999), 'Kitchen Scale': (399, 2499), 'Water Bottle Set': (299, 2499), 'Knife Set': (599, 6999), 'Clothes Drying Rack': (699, 4999), 'Table Lamp': (399, 3999), 'Food Chopper': (299, 2499), 'Running Shoes': (1499, 14999), 'Everyday Backpack': (699, 7999), 'Sports T-Shirt': (399, 3999), 'Analog Watch': (999, 24999), 'Sunglasses': (499, 9999), 'Skin Care Set': (399, 4999), 'Hair Dryer': (599, 7999), 'Fragrance Gift Set': (799, 8999), 'Makeup Kit': (499, 6999), 'Travel Wallet': (299, 2999), 'Yoga Mat': (399, 3999), 'Badminton Racket': (699, 9999), 'Cricket Bat': (899, 14999), 'Camping Tent': (1499, 19999), 'Trekking Backpack': (999, 14999), 'Fitness Tracker': (1299, 19999), 'Resistance Band Set': (299, 1999), 'Football': (399, 3999), 'Cycling Helmet': (899, 9999), 'Waterproof Jacket': (999, 12999), 'Wireless Printer': (5999, 34999), 'Ink Cartridge Set': (499, 4999), 'Scientific Calculator': (399, 3999), 'Premium Notebook': (99, 999), 'Ball Pen Set': (99, 999), 'Desk Organiser': (299, 2999), 'Document Scanner': (2999, 24999), 'Label Maker': (1499, 9999), 'Stapler Set': (199, 1999), 'Office Chair': (2999, 29999)}
EDITIONS = ['Essential', 'Plus', 'Pro', 'Smart', 'Signature', 'Ultra', 'Everyday', 'Advance', 'Prime', 'Select']
EDITION_MULTIPLIER = {'Essential': 0.85, 'Plus': 1.0, 'Pro': 1.25, 'Smart': 1.1, 'Signature': 1.45, 'Ultra': 1.6, 'Everyday': 0.8, 'Advance': 1.15, 'Prime': 1.3, 'Select': 1.05}
COLORS = ['Graphite', 'Midnight', 'Silver', 'Blue', 'Black', 'White', 'Sand', 'Rose', 'Green', 'Titanium']
REVIEWERS = ['Aarav', 'Ananya', 'Rohan', 'Meera', 'Ishaan', 'Kavya', 'Arjun', 'Diya', 'Vihaan', 'Saanvi', 'Rahul', 'Priya', 'Neha', 'Aditya', 'Sneha', 'Karan', 'Riya', 'Vikram', 'Aisha', 'Nikhil']
POSITIVE = ['The build quality feels premium and sturdy. Performance has been smooth and I am very satisfied.', 'Delivery was quick and the packaging kept everything safe. Great value for money.', 'The design looks sleek and the useful features work very well. Definitely recommend it.', 'Setup was easy, quality is excellent, and it has been reliable during daily use.', 'This is a well-made product with strong performance. It exceeded my expectations for the price.', 'Battery life is impressive and charging is fast. Very happy with this purchase.', 'The finish is flawless and it feels genuine, not like a duplicate. Worth every rupee.', 'Support was helpful and the replacement arrived quickly. Excellent service overall.', 'Excellent sound and a bright, crisp display. The picture quality is superb.', 'Comfortable to use for hours. The size is perfect and the material feels premium.', 'Arrived early and well cushioned. No scratches at all and everything works perfectly.', 'Durable after months of daily use. Still strong and reliable with no wear.']
NEUTRAL = ['It does the job as expected. The design is fine, although the price is a bit high.', 'Packaging was acceptable and delivery was on time. Nothing exceptional, but it is usable.', 'The features work reasonably well after setup. Quality is average for this price range.', 'It is an okay product. Performance is standard and nothing stands out.', 'Delivery took the usual time. The box was sealed and the product is decent.', 'Works fine for basic use. The finish is ordinary and the price is fair.', 'The design is standard and the size is average. It is a fair deal at this price.', 'Setup was normal. It performs as advertised, though the build feels ordinary.']
NEGATIVE = ['Build quality feels poor and the price is expensive. I expected better performance.', 'Delivery was delayed and the packaging arrived damaged. The overall experience was disappointing.', 'Performance is inconsistent and support was unhelpful. It stopped working sooner than expected.', 'It arrived scratched and the box was torn. Very disappointing for the price.', 'The material looks duplicate and low grade. Terrible finish and cheap plastic.', 'The battery drains fast and the device heats up. Poor performance overall.', 'The size runs small and the fit is uncomfortable. I regret buying this.', 'The seller was rude and refused the refund. Waste of money.']
MIX_PATTERNS = [(7, 2, 1), (7, 3, 0), (6, 3, 1), (6, 2, 2), (5, 3, 2), (5, 4, 1), (4, 4, 2), (4, 3, 3), (3, 4, 3), (3, 3, 4), (2, 4, 4), (1, 4, 5)]
POS_RATINGS = [5, 5, 4, 5, 4, 5, 4]
NEU_RATINGS = [3, 3, 4, 2]
NEG_RATINGS = [1, 2, 1, 2, 1]

def _product_rows():
    """Generate exactly 5,000 deterministic, searchable product-style rows."""
    rows = []
    product_id = 1
    for category_index, (category, brands, types) in enumerate(CATEGORY_SPECS, start=1):
        for offset in range(500):
            brand = brands[offset % len(brands)]
            product_type = types[(offset // len(brands) + offset) % len(types)]
            edition = EDITIONS[(offset // 7 + category_index) % len(EDITIONS)]
            colour = COLORS[(offset * 3 + category_index) % len(COLORS)]
            model = f'{chr(65 + offset % 26)}{offset // 26 + 10}{category_index}{offset % 10}'
            title = f'{brand} {product_type} {edition} {model} — {colour}'
            sku = f'AL-{category_index:02d}-{offset + 1:03d}'
            type_low, type_high = TYPE_PRICE.get(product_type, (499, 24999))
            price_rng = random.Random(product_id * 104729 + category_index)
            spread = price_rng.random() ** 1.7
            price = type_low + (type_high - type_low) * spread
            price = round(price * EDITION_MULTIPLIER[edition] / 10) * 10 + 9
            rows.append((product_id, sku, title, brand, category, product_type, REVIEWS_PER_PRODUCT, price))
            product_id += 1
    return rows

def _review_rows(products):
    """Build a varied, deterministic sentiment mix for each product."""
    rows = []
    review_id = 1
    base = date(2025, 1, 5)
    for product in products:
        product_id, _, _, brand, category, product_type, _, _ = product
        rng = random.Random(product_id * 7919)
        pos_count, neu_count, neg_count = MIX_PATTERNS[product_id % len(MIX_PATTERNS)]
        pos_texts = rng.sample(POSITIVE, min(pos_count, len(POSITIVE)))
        neu_texts = rng.sample(NEUTRAL, min(neu_count, len(NEUTRAL)))
        neg_texts = rng.sample(NEGATIVE, min(neg_count, len(NEGATIVE)))
        entries = []
        for i, text in enumerate(pos_texts):
            entries.append(('positive', float(POS_RATINGS[i % len(POS_RATINGS)]), text))
        for i, text in enumerate(neu_texts):
            entries.append(('neutral', float(NEU_RATINGS[i % len(NEU_RATINGS)]), text))
        for i, text in enumerate(neg_texts):
            entries.append(('negative', float(NEG_RATINGS[i % len(NEG_RATINGS)]), text))
        rng.shuffle(entries)
        for position, (seed_sentiment, rating, text) in enumerate(entries):
            reviewer = REVIEWERS[(product_id * 3 + position * 7) % len(REVIEWERS)]
            detail = f' — catalog item in the {category} category.'
            review_date = (base + timedelta(days=(product_id * 11 + position * 37) % 620)).isoformat()
            rows.append((review_id, product_id, reviewer, rating, text + detail, review_date, seed_sentiment))
            review_id += 1
    return rows

def ensure_catalog_seed(conn):
    """Create/rebuild the catalog only when its version or size is outdated."""
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    try:
        cur.execute('ALTER TABLE catalog_products ADD COLUMN price REAL DEFAULT 0')
    except Exception:
        pass
    version_row = cur.execute("SELECT value FROM catalog_meta WHERE key='catalog_version'").fetchone()
    count = cur.execute('SELECT COUNT(*) FROM catalog_products').fetchone()[0]
    if version_row and version_row[0] == CATALOG_VERSION and (count == 5000):
        return
    cur.execute('DELETE FROM catalog_reviews')
    cur.execute('DELETE FROM catalog_products')
    products = _product_rows()
    cur.executemany('INSERT INTO catalog_products\n           (id, sku, title, brand, category, product_type, review_count, price)\n           VALUES (?,?,?,?,?,?,?,?)', products)
    cur.executemany('INSERT INTO catalog_reviews\n           (id, product_id, reviewer, rating, review_text, review_date, seed_sentiment)\n           VALUES (?,?,?,?,?,?,?)', _review_rows(products))
    cur.execute("INSERT OR REPLACE INTO catalog_meta (key, value) VALUES ('catalog_version', ?)", (CATALOG_VERSION,))
    conn.commit()

def _conn():
    return get_conn()

def catalog_summary():
    conn = _conn()
    cur = conn.cursor()
    products = cur.execute('SELECT COUNT(*) FROM catalog_products').fetchone()[0]
    reviews = cur.execute('SELECT COUNT(*) FROM catalog_reviews').fetchone()[0]
    categories = cur.execute('SELECT COUNT(DISTINCT category) FROM catalog_products').fetchone()[0]
    conn.close()
    return {'products': products, 'reviews': reviews, 'categories': categories}

def catalog_categories():
    conn = _conn()
    rows = conn.execute('SELECT DISTINCT category FROM catalog_products ORDER BY category').fetchall()
    conn.close()
    return [row[0] for row in rows]

def catalog_match_count(query='', category='All categories'):
    """Count the products matching the current browse/search controls."""
    query = (query or '').strip().lower()
    conn = _conn()
    where, params = ([], [])
    if query:
        for term in [term for term in query.split() if term]:
            like = f'%{term}%'
            where.append('(LOWER(title) LIKE ? OR LOWER(brand) LIKE ? OR LOWER(category) LIKE ? OR LOWER(sku) LIKE ?)')
            params.extend([like, like, like, like])
    if category != 'All categories':
        where.append('category=?')
        params.append(category)
    suffix = f" WHERE {' AND '.join(where)}" if where else ''
    count = conn.execute(f'SELECT COUNT(*) FROM catalog_products{suffix}', params).fetchone()[0]
    conn.close()
    return count

def search_catalog(query='', category='All categories', limit=24, offset=0):
    """Prefix-first search for title, brand, category, product type or SKU."""
    query = (query or '').strip().lower()
    conn = _conn()
    conn.row_factory = None
    if query:
        terms = [term for term in query.split() if term]
        where = []
        params = []
        for term in terms:
            like = f'%{term}%'
            where.append('(LOWER(title) LIKE ? OR LOWER(brand) LIKE ? OR LOWER(category) LIKE ? OR LOWER(sku) LIKE ?)')
            params.extend([like, like, like, like])
        if category != 'All categories':
            where.append('category=?')
            params.append(category)
        prefix = f'{query}%'
        sql = f"SELECT id, sku, title, brand, category, product_type, review_count, price\n                   FROM catalog_products WHERE {' AND '.join(where)}\n                   ORDER BY CASE WHEN LOWER(title) LIKE ? THEN 0\n                                 WHEN LOWER(brand) LIKE ? THEN 1 ELSE 2 END,\n                            title LIMIT ? OFFSET ?"
        params.extend([prefix, prefix, limit, offset])
    else:
        params = []
        where = ''
        if category != 'All categories':
            where = 'WHERE category=?'
            params.append(category)
        sql = f'SELECT id, sku, title, brand, category, product_type, review_count, price\n                   FROM catalog_products {where} ORDER BY id LIMIT ? OFFSET ?'
        params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    columns = ['id', 'sku', 'title', 'brand', 'category', 'product_type', 'review_count', 'price']
    conn.close()
    return [dict(zip(columns, row)) for row in rows]
_PRODUCT_COLUMNS = ('id', 'sku', 'title', 'brand', 'category', 'product_type', 'review_count', 'price')

def get_catalog_product(product_id):
    conn = _conn()
    row = conn.execute('SELECT id, sku, title, brand, category, product_type, review_count, price FROM catalog_products WHERE id=?', (product_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(zip(_PRODUCT_COLUMNS, row))

def get_catalog_reviews(product_id):
    conn = _conn()
    rows = conn.execute('SELECT reviewer AS author, rating, review_text AS text, review_date AS date, seed_sentiment\n           FROM catalog_reviews WHERE product_id=? ORDER BY id', (product_id,)).fetchall()
    conn.close()
    return [dict(zip(('author', 'rating', 'text', 'date', 'seed_sentiment'), row)) for row in rows]



# ==========================================================================
# NLP_ENGINE.PY
# ==========================================================================

"""
nlp_engine.py — Aspect-based sentiment analysis (pure Python, offline, free).
--------------------------------------------------------------------------------
How it works:
1. Each review is split into sentences.
2. Each sentence is scored with a negation/intensifier/hedge-aware lexicon.
   Sentences that carry no opinion word at all are skipped entirely, so
   descriptive text ("...for the electronics category") can never vote.
3. Opinion sentences are tagged with aspects via keyword matching
   (Quality, Price, Delivery, Packaging, Service, Features, Durability, Design).
4. Sentence scores are aggregated per aspect + overall, with a verdict.

Ambiguous words are handled with real context rules instead of blunt lists:
   "high"  -> negative only when the sentence is about price/cost
   "low"   -> negative only when the sentence is about quality/grade
              (a low price is a GOOD thing, so that is a positive signal)
   "small" -> negative only when the sentence is about fit/size
Words like "time", "month", "brand", "new", "working" are deliberately NOT in
the lexicon: they were dragging neutral sentences in both directions.

Also includes price_trend(): deterministic 12-month price history per product.
"""
import hashlib
import random
import re
from datetime import datetime, timedelta
ASPECT_KEYWORDS = {'Quality': ['quality', 'premium', 'material', 'materials', 'build', 'sturdy', 'finish', 'finishing', 'fabric', 'genuine', 'original', 'duplicate', 'flaw', 'flaws', 'scratch', 'scratches', 'plasticky', 'well-made'], 'Price': ['price', 'cost', 'costs', 'expensive', 'cheap', 'cheaper', 'value', 'money', 'affordable', 'overpriced', 'worth', 'budget', 'discount', 'offer', 'mrp', 'rupee', 'rupees', 'pricey', 'deal', 'pricing'], 'Delivery': ['delivery', 'shipping', 'arrived', 'arrive', 'courier', 'dispatch', 'dispatched', 'shipment', 'delivered', 'delay', 'delayed', 'tracking', 'shipped', 'rescheduled'], 'Packaging': ['pack', 'packed', 'packing', 'packaging', 'package', 'box', 'sealed', 'seal', 'wrap', 'wrapping', 'unboxing', 'cushion', 'bubble'], 'Service': ['service', 'support', 'return', 'refund', 'replacement', 'warranty', 'seller', 'staff', 'helpful', 'response', 'responsive', 'unresponsive', 'claim', 'help', 'helpline', 'customer care'], 'Features': ['feature', 'features', 'battery', 'camera', 'display', 'screen', 'performance', 'sound', 'processor', 'ram', 'storage', 'charging', 'speaker', 'bluetooth', 'picture', 'photo', 'interface', 'connectivity', 'lag', 'heats', 'heating', 'mic', 'app', 'settings'], 'Durability': ['durable', 'durability', 'last', 'lasts', 'lasting', 'broke', 'broken', 'damaged', 'damage', 'crack', 'cracked', 'fragile', 'wear', 'drop', 'stopped', 'survived', 'strong', 'years', 'months', 'stopped working'], 'Design': ['design', 'look', 'looks', 'style', 'colour', 'color', 'beautiful', 'elegant', 'sleek', 'modern', 'attractive', 'appearance', 'comfort', 'comfortable', 'uncomfortable', 'fit', 'fits', 'size', 'sizing', 'bulky', 'dull', 'outdated', 'compliment', 'compliments', 'finish']}
POS_WORDS = {'good', 'great', 'excellent', 'amazing', 'awesome', 'fantastic', 'superb', 'outstanding', 'wonderful', 'brilliant', 'perfect', 'love', 'loved', 'loves', 'best', 'better', 'nice', 'premium', 'beautiful', 'elegant', 'sleek', 'smooth', 'smoothly', 'fast', 'quick', 'quickly', 'impressive', 'impressed', 'happy', 'satisfied', 'satisfying', 'satisfactory', 'recommend', 'recommended', 'worth', 'affordable', 'reasonable', 'unbeatable', 'sturdy', 'strong', 'durable', 'genuine', 'original', 'flawless', 'helpful', 'polite', 'seamless', 'intuitive', 'clear', 'crisp', 'sharp', 'comfortable', 'attractive', 'modern', 'compliment', 'compliments', 'exceeded', 'exceeds', 'incredible', 'phenomenal', 'stunning', 'gorgeous', 'classy', 'neat', 'reliable', 'trustworthy', 'authentic', 'responsive', 'easily', 'easy', 'efficient', 'powerful', 'lasting', 'bright', 'vivid', 'loud', 'balanced', 'approved', 'convenient', 'safe', 'protected', 'cushioned', 'prompt', 'early', 'superior', 'value', 'loving', 'favourite', 'favorite', 'glad', 'pleased', 'pleasantly', 'surprised', 'conveniently', 'handy', 'practical'}
NEG_WORDS = {'bad', 'poor', 'terrible', 'awful', 'horrible', 'worst', 'worse', 'disappointing', 'disappointed', 'disappointment', 'hate', 'hated', 'regret', 'frustrating', 'frustrated', 'annoying', 'useless', 'waste', 'pathetic', 'nightmare', 'cheap', 'duplicate', 'fake', 'flaw', 'flaws', 'scratch', 'scratches', 'torn', 'broken', 'broke', 'crack', 'cracked', 'damaged', 'damage', 'fragile', 'stopped', 'lag', 'lags', 'lagging', 'heats', 'heating', 'drains', 'drain', 'slow', 'late', 'delay', 'delayed', 'rude', 'rudely', 'unresponsive', 'unhelpful', 'rejected', 'cheated', 'expensive', 'overpriced', 'costly', 'gimmicky', 'gimmick', 'tinny', 'dropping', 'drops', 'dull', 'outdated', 'bulky', 'uncomfortable', 'tight', 'risky', 'rattling', 'rescheduled', 'denied', 'plasticky', 'noisy', 'blurry', 'dark', 'dim', 'weak', 'inconsistent', 'defective', 'faulty', 'junk', 'scam', 'leaking', 'loose', 'mismatched', 'incomplete'}
NEU_WORDS = {'fine', 'okay', 'ok', 'average', 'acceptable', 'expected', 'usable', 'decent', 'adequate', 'standard', 'ordinary', 'fair', 'moderate', 'passable', 'works', 'working'}
INTENSIFIERS = {'very', 'really', 'extremely', 'super', 'highly', 'totally', 'truly', 'absolutely', 'quite', 'so', 'too', 'incredibly', 'amazingly', 'deeply', 'completely', 'utterly'}
HEDGES = {'little', 'slightly', 'somewhat', 'bit', 'fairly', 'rather', 'relatively', 'mildly'}
CONTRAST = {'but', 'although', 'though', 'however', 'yet', 'except'}
NEGATIONS = {'not', 'no', 'never', 'neither', 'nor', 'none', 'hardly', 'barely', 'without', 'isnt', "isn't", 'wasnt', "wasn't", 'dont', "don't", 'doesnt', "doesn't", 'cant', "can't", 'wont', "won't", 'couldnt', "couldn't", 'didnt', "didn't"}
_PRICE_CTX = re.compile('\\b(price|prices|priced|pricing|cost|costs|value|money|rupee|rupees|mrp|budget|deal|offer|discount|expensive|cheap|affordable|worth|sale)\\b', re.I)
_QUALITY_CTX = re.compile('\\b(quality|grade|build|material|materials|finish|finishing|construction|made)\\b', re.I)
_FIT_CTX = re.compile('\\b(fit|fits|fitting|size|sizing|comfort|comfortable|wear)\\b', re.I)
NEG_PHRASES = [(re.compile('\\bexpect(?:ed|ing)? (?:a bit |a little )?better\\b', re.I), 'disappointing'), (re.compile('\\bexpect(?:ed|ing)? more\\b', re.I), 'disappointing'), (re.compile('\\bcould be (?:much )?better\\b', re.I), 'disappointing'), (re.compile('\\bcould be improved\\b', re.I), 'disappointing'), (re.compile('\\bnot (?:really )?worth\\b', re.I), 'overpriced'), (re.compile('\\bwaste of money\\b', re.I), 'overpriced'), (re.compile('\\bno complaints?\\b', re.I), 'perfect')]

def _apply_phrases(sentence: str) -> str:
    """Rewrite known idioms into a single unambiguous word before scoring."""
    for pattern, replacement in NEG_PHRASES:
        sentence = pattern.sub(replacement, sentence)
    return sentence

def _contextual_polarity(word: str, sentence: str):
    """Return a polarity for an ambiguous word, or None to ignore it.

    'high' / 'low' / 'small' were previously hard-coded as negative, which made
    'The build quality is high' score NEGATIVE. They only mean something bad in
    a specific context, so that context is checked here.
    """
    low = sentence.lower()
    if word in ('high', 'steep'):
        if _PRICE_CTX.search(low):
            return -1.0
        if _QUALITY_CTX.search(low):
            return 1.0
        return None
    if word == 'low':
        if _QUALITY_CTX.search(low):
            return -1.0
        if _PRICE_CTX.search(low):
            return 1.0
        return None
    if word in ('small', 'smaller', 'tight', 'loose'):
        return -1.0 if _FIT_CTX.search(low) else None
    if word in ('big', 'larger', 'bulky'):
        return -1.0 if _FIT_CTX.search(low) else None
    return None
CONTEXT_WORDS = ('high', 'steep', 'low', 'small', 'smaller', 'tight', 'loose', 'big', 'larger', 'bulky')
_ASPECT_PATTERNS = {a: re.compile('\\b(' + '|'.join(sorted(set((k.strip() for k in kws if k.strip())), key=len, reverse=True)) + ')\\b', re.IGNORECASE) for a, kws in ASPECT_KEYWORDS.items()}

def score_sentence(sentence: str):
    """Score one sentence -> (score, hits).

    `hits` lists every lexicon word that fired. An empty `hits` means the
    sentence expressed no opinion at all and must not vote on anything.
    """
    parts = re.split('\\b(?:but|although|though|however|yet|except)\\b', sentence.lower())
    if len(parts) > 1 and any((re.search('[a-z]', p) for p in parts[1:])):
        sentence = parts[-1]
    sentence = _apply_phrases(sentence)
    words = re.findall("[a-zA-Z']+", sentence.lower())
    score = 0.0
    hits = []
    for i, w in enumerate(words):
        if w in POS_WORDS:
            val = 1.0
        elif w in NEG_WORDS:
            val = -1.0
        elif w in CONTEXT_WORDS:
            val = _contextual_polarity(w, sentence)
        elif w in NEU_WORDS:
            val = 0.0
        else:
            continue
        if val is None:
            continue
        hits.append(w)
        if val == 0.0:
            continue
        window = words[max(0, i - 3):i]
        if any((n in NEGATIONS for n in window)):
            val = -val
        elif any((t in INTENSIFIERS for t in window)):
            val *= 1.5
        elif any((h in HEDGES for h in window)):
            val *= 0.25
        score += val
    return (score, hits)

def sentence_sentiment(sentence: str) -> str:
    """Score one sentence -> 'positive' | 'neutral' | 'negative'."""
    score, _ = score_sentence(sentence)
    if score > 0.25:
        return 'positive'
    if score < -0.25:
        return 'negative'
    return 'neutral'

def analyze_reviews(reviews):
    """Analyze a list of reviews -> overall counts, per-aspect counts, verdict."""
    aspects = list(ASPECT_KEYWORDS.keys())
    aspect_data = {a: {'positive': 0, 'neutral': 0, 'negative': 0, 'examples': []} for a in aspects}
    overall = {'positive': 0, 'neutral': 0, 'negative': 0}
    rows = []
    for rev in reviews:
        text = rev['text']
        sentences = [s.strip() for s in re.split('[.!?]+', text) if s.strip()]
        found_aspects = set()
        pos = neu = neg = 0
        opinion_sentences = 0
        for sent in sentences:
            score, hits = score_sentence(sent)
            if not hits:
                continue
            opinion_sentences += 1
            label = 'positive' if score > 0.25 else 'negative' if score < -0.25 else 'neutral'
            if label == 'positive':
                pos += 1
            elif label == 'negative':
                neg += 1
            else:
                neu += 1
            matched = [a for a in aspects if _ASPECT_PATTERNS[a].search(sent)]
            if not matched:
                matched = ['Quality'] if any((w in sent.lower() for w in ('product', 'item', 'purchase'))) else []
            for a in matched:
                aspect_data[a][label] += 1
                found_aspects.add(a)
                if len(aspect_data[a]['examples']) < 3:
                    aspect_data[a]['examples'].append((label, sent))
        if pos > neg:
            label = 'positive'
        elif neg > pos:
            label = 'negative'
        else:
            label = 'neutral'
        overall[label] += 1
        rows.append({**rev, 'sentiment': label, 'aspects': sorted(found_aspects) or ['General']})
    total = max(1, len(reviews))
    pos_pct = overall['positive'] / total * 100
    if pos_pct >= 60:
        verdict = 'Highly Positive'
    elif pos_pct >= 46:
        verdict = 'Mostly Positive'
    elif pos_pct >= 36:
        verdict = 'Mixed'
    elif pos_pct >= 25:
        verdict = 'Mostly Negative'
    else:
        verdict = 'Highly Negative'
    return {'overall': overall, 'total': len(reviews), 'pos_pct': pos_pct, 'verdict': verdict, 'aspects': aspect_data, 'rows': rows}

def price_trend(product, months=12):
    """Deterministic 12-month price history (random walk + sale events)."""
    pid = product.get('id', product.get('sku', 'catalog'))
    base = float(product.get('price') or 0) or 1000.0
    seed = int(hashlib.md5((str(pid) + 'price').encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    labels = []
    today = datetime.now()
    for i in range(months - 1, -1, -1):
        d = today - timedelta(days=30 * i)
        labels.append(d.strftime('%b %y'))
    prices, p = ([], base * 1.12)
    for i in range(months):
        drift = (base - p) * 0.25
        p = max(base * 0.82, p + drift + rng.uniform(-base * 0.05, base * 0.045))
        if i in (3, 8):
            p *= rng.uniform(0.9, 0.95)
        prices.append(round(p))
    prices[-1] = round(base)
    return (labels, prices)



# ==========================================================================
# CHARTS.PY
# ==========================================================================

"""
charts.py — All Plotly dashboard figures (transparent backgrounds
so they blend into the glass cards).
---------------------------------------------------------------
fig_donut()    overall sentiment split
fig_bar()      per-aspect positive/neutral/negative breakdown
fig_sunburst() aspects -> sentiment hierarchy
fig_radar()    aspect positivity scores (0-100)
fig_timeline() line chart: monthly positivity trend (needs dates)
fig_rolling()  line chart: rolling sentiment over review order (fallback)
fig_ratings()  bar chart: star-rating distribution (needs ratings)
fig_price_history()  line chart: deterministic 12-month price history
"""
import pandas as pd
import plotly.graph_objects as go

def style_fig(fig, height=380):
    """Apply the glass-friendly transparent style to any figure."""
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family='Poppins, sans-serif', color='#2b2350', size=12), legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
    return fig

def fig_donut(overall):
    fig = go.Figure(go.Pie(labels=['Positive', 'Neutral', 'Negative'], values=[overall['positive'], overall['neutral'], overall['negative']], hole=0.58, marker=dict(colors=[POS_COLOR, NEU_COLOR, NEG_COLOR], line=dict(color='white', width=3)), textinfo='percent', hoverinfo='label+value'))
    fig.update_layout(title='Overall Sentiment Split', title_font=dict(size=14, color='#4c1d95'))
    return style_fig(fig, 340)

def fig_bar(aspect_data):
    aspects = list(aspect_data.keys())
    fig = go.Figure()
    fig.add_bar(name='Positive', x=aspects, y=[aspect_data[a]['positive'] for a in aspects], marker_color=POS_COLOR)
    fig.add_bar(name='Neutral', x=aspects, y=[aspect_data[a]['neutral'] for a in aspects], marker_color=NEU_COLOR)
    fig.add_bar(name='Negative', x=aspects, y=[aspect_data[a]['negative'] for a in aspects], marker_color=NEG_COLOR)
    fig.update_layout(barmode='group', title='Aspect-Level Sentiment Breakdown', title_font=dict(size=14, color='#4c1d95'), xaxis_tickangle=-25)
    return style_fig(fig, 420)

def fig_sunburst(aspect_data, total):
    """Aspects -> sentiment sunburst.

    Two rules keep this chart visible, and both matter:

    1. NO artificial root node. A review mentions several aspects, so the
       per-aspect counts overlap and add up to MORE than the review count.
       A root valued `total` therefore cannot contain its children, and
       Plotly silently draws an empty canvas (this was a real bug: a blank
       "Sunburst: Aspects -> Sentiment" panel).
    2. Skip zero-count leaves. A slice with value 0 has no area, and mixing
       them into the hierarchy wastes the ring.

    `branchvalues="remainder"` then lets each ring size itself from the
    children that actually exist.
    """
    labels, parents, values, colors = ([], [], [], [])
    for a, d in aspect_data.items():
        a_total = max(1, d['positive'] + d['neutral'] + d['negative'])
        labels.append(a)
        parents.append('')
        values.append(a_total)
        colors.append('#ddd6fe')
        for s, c in (('positive', POS_COLOR), ('neutral', NEU_COLOR), ('negative', NEG_COLOR)):
            count = max(0, int(d[s]))
            if count == 0:
                continue
            labels.append(f'{a} • {s.capitalize()}')
            parents.append(a)
            values.append(count)
            colors.append(c)
    if not labels:
        fig = go.Figure()
        fig.add_annotation(text='No aspect mentions found', showarrow=False, font=dict(size=14, color='#6d6890'))
        return style_fig(fig, 460)
    fig = go.Figure(go.Sunburst(labels=labels, parents=parents, values=values, marker=dict(colors=colors, line=dict(color='white', width=2)), branchvalues='remainder', maxdepth=2, hoverinfo='label+value'))
    fig.update_layout(title='Sunburst: Aspects → Sentiment', title_font=dict(size=14, color='#4c1d95'))
    return style_fig(fig, 460)

def fig_radar(aspect_data):
    aspects = list(aspect_data.keys())
    if len(aspects) < 3:
        return fig_bar(aspect_data)
    scores = []
    for a in aspects:
        d = aspect_data[a]
        t = max(1, d['positive'] + d['neutral'] + d['negative'])
        scores.append(round((d['positive'] + 0.5 * d['neutral']) / t * 100, 1))
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=scores + scores[:1], theta=aspects + aspects[:1], fill='toself', name='Positivity score', line=dict(color='#9333ea', width=3), fillcolor='rgba(147,51,234,0.18)', marker=dict(color='#ec4899', size=7)))
    fig.update_layout(title='Radar: Aspect Positivity Score (0–100)', title_font=dict(size=14, color='#4c1d95'), polar=dict(radialaxis=dict(visible=True, range=[0, 100]), bgcolor='rgba(0,0,0,0)'))
    return style_fig(fig, 440)

def _line_trace(fig, x, y, name):
    fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', name=name, line=dict(color='#7c3aed', width=3), marker=dict(size=8, color='#ec4899', line=dict(color='white', width=2)), fill='tozeroy', fillcolor='rgba(168,85,247,0.12)'))
    return fig

def fig_timeline(dates, sentiments, title='Monthly Positivity Trend (% positive)'):
    """Line chart of % positive reviews per month. Returns None if <2 months."""
    df = pd.DataFrame({'date': pd.to_datetime(dates, errors='coerce'), 'pos': [1 if s == 'positive' else 0 for s in sentiments]})
    df = df.dropna(subset=['date'])
    if df.empty:
        return None
    df['month'] = df['date'].dt.to_period('M').astype(str)
    g = df.groupby('month')['pos'].mean().mul(100).round(1)
    if len(g) < 2:
        return None
    fig = go.Figure()
    _line_trace(fig, list(g.index), list(g.values), 'Positive %')
    fig.update_layout(title=title, title_font=dict(size=13, color='#4c1d95'), yaxis_title='Positive %', yaxis_range=[0, 100])
    return style_fig(fig, 380)

def fig_rolling(sentiments, title='Sentiment Trend Across Reviews (rolling average)'):
    """Fallback line chart when no dates exist: rolling positivity over review order."""
    scores = [{'positive': 1.0, 'neutral': 0.5, 'negative': 0.0}[s] for s in sentiments]
    s = pd.Series(scores)
    window = max(3, min(20, len(s) // 10 or 3))
    rolled = (s.rolling(window, min_periods=1).mean() * 100).round(1)
    fig = go.Figure()
    _line_trace(fig, list(range(1, len(rolled) + 1)), list(rolled.values), 'Positive %')
    fig.update_layout(title=title, title_font=dict(size=13, color='#4c1d95'), xaxis_title='Review #', yaxis_title='Positive %', yaxis_range=[0, 100])
    return style_fig(fig, 380)

def fig_ratings(ratings):
    """Bar chart of star-rating distribution."""
    vc = pd.Series(ratings).dropna().value_counts().sort_index()
    fig = go.Figure()
    fig.add_bar(x=[str(v) for v in vc.index], y=list(vc.values), name='Reviews', marker_color=['#f43f5e', '#fb923c', '#a78bfa', '#34d399', '#10b981'][-len(vc):] or '#9333ea')
    fig.update_layout(title='Rating Distribution', title_font=dict(size=14, color='#4c1d95'), xaxis_title='Stars', yaxis_title='Reviews')
    return style_fig(fig, 340)

def fig_price_history(product):
    """12-month price history for a catalog product (deterministic per product)."""
    labels, prices = price_trend(product)
    fig = go.Figure()
    _line_trace(fig, labels, prices, 'Price')
    fig.update_traces(fillcolor='rgba(16,185,129,0.12)', line=dict(color='#10b981', width=3), marker=dict(color='#059669'))
    fig.update_layout(title='Price History (last 12 months)', title_font=dict(size=13, color='#4c1d95'), yaxis_title='Price (₹)')
    return style_fig(fig, 340)



# ==========================================================================
# UI_HELPERS.PY
# ==========================================================================

"""
ui_helpers.py — Reusable UI building blocks (HTML snippets).
------------------------------------------------------------
avatar_html()     user profile picture (or initial-letter fallback)
sent_badge()      coloured Positive/Neutral/Negative pill
money()           ₹ formatting
product_row_html() name-first catalog card (no images)
header()          gradient page title + subtitle + divider
"""
import html
import streamlit as st

def avatar_html(user, size='md'):
    cls = 'avatar' if size == 'md' else 'avatar-sm'
    pic = (user or {}).get('profile_pic', '')
    name = (user or {}).get('username', '?')
    if pic:
        return f'<img class="{cls}" src="data:image/png;base64,{pic}"/>'
    return f'<div class="{cls} avatar-fallback">{name[:1].upper()}</div>'

def sent_badge(s):
    return f'<span class="sent-{s[:3]}">{s.capitalize()}</span>'

def stars_text(rating) -> str:
    """Render a 5-star string, e.g. 4.3 -> '★★★★☆' ('' if no rating)."""
    if rating is None:
        return ''
    try:
        full = int(round(float(rating)))
    except (TypeError, ValueError):
        return ''
    full = max(0, min(5, full))
    return '★' * full + '☆' * (5 - full)

def item_card_html(name, n_reviews, avg_rating=None):
    stars = stars_text(avg_rating) if avg_rating is not None else ''
    rating_line = f'<div class="stars">{stars} <span style="color:#6d6890;">{avg_rating:.1f} / 5</span></div>' if avg_rating is not None else '<div class="small-note">no ratings</div>'
    return f"""\n    <div class="glass-soft" style="padding:14px; height:100%;">\n      <span class="badge" style="background:#7c3aed;">{n_reviews} review{('s' if n_reviews != 1 else '')}</span>\n      <div class="item-name">{name}</div>\n      {rating_line}\n    </div>"""

def money(amount) -> str:
    """INR-ish money formatting used by cards and the dashboard."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return '—'
    if amount <= 0:
        return '—'
    return f'₹{amount:,.0f}'

def product_row_html(product, selected=False):
    """Simplest useful card: NAME, price, how many reviews and what type they are.

    No picture, no SKU, no category tag — the title already says what it is.
    """
    title = html.escape(str(product['title']))
    price = money(product.get('price'))
    count = int(product.get('review_count', 0))
    cls = 'product-row selected' if selected else 'product-row'
    return f'\n    <div class="{cls}">\n      <div class="product-row-name">{title}</div>\n      <div class="product-row-price">{price}</div>\n      <div class="product-row-meta">📝 {count} review samples</div>\n    </div>'

def header(title, subtitle):
    st.markdown(f'<div class="gradient-title">{title}</div><div class="subtitle">{subtitle}</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)



# ==========================================================================
# STYLES.PY
# ==========================================================================

"""
styles.py — Glassmorphism theme (pastel mesh background, glass cards,
gradient titles, pill buttons). Call apply_custom_css() once from app.py.
"""
import streamlit as st
GLASS_CSS = '\n<style>\n@import url(\'https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap\');\n\n.stApp {\n  font-family: \'Poppins\', sans-serif;\n  background:\n    radial-gradient(1000px 620px at 8% 8%,   rgba(199,233,255,0.95), transparent 60%),\n    radial-gradient(950px 720px at 92% 12%,  rgba(255,209,220,0.95), transparent 60%),\n    radial-gradient(820px 620px at 88% 92%,  rgba(255,178,200,0.65), transparent 60%),\n    radial-gradient(920px 720px at 8% 95%,   rgba(255,243,196,0.95), transparent 60%),\n    radial-gradient(760px 560px at 50% 55%,  rgba(230,222,255,0.85), transparent 65%),\n    linear-gradient(135deg, #eef4ff 0%, #fdf1f5 60%, #ffeef3 100%);\n  background-attachment: fixed;\n  color: #2b2350;\n}\n[data-testid="stSidebar"] {\n  background: rgba(255,255,255,0.45) !important;\n  backdrop-filter: blur(22px);\n  -webkit-backdrop-filter: blur(22px);\n  border-right: 1px solid rgba(255,255,255,0.65);\n}\n[data-testid="stSidebar"] .block-container { padding-top: 1rem; }\n[data-testid="stHeader"] { background: rgba(255,255,255,0.0) !important; }\n/* Do NOT hide stToolbar: it contains Streamlit\'s sidebar reopen control after\n   the sidebar is collapsed. Hiding it made the sidebar appear permanent-closed. */\n[data-testid="stToolbar"] { display: flex !important; visibility: visible !important; }\n[data-testid="stSidebarCollapsedControl"] {\n  display: flex !important; visibility: visible !important; opacity: 1 !important;\n  position: relative !important; z-index: 100000 !important;\n}\n[data-testid="stSidebarCollapsedControl"] button,\n[data-testid="stSidebar"] button[kind="header"] {\n  visibility: visible !important; opacity: 1 !important;\n}\nfooter { visibility: hidden; }\n\n.gradient-title {\n  font-weight: 800; letter-spacing: -0.5px; line-height: 1.1;\n  font-size: 2.7rem;\n  background: linear-gradient(90deg, #5b6abf 0%, #0891b2 30%, #9333ea 65%, #ec4899 100%);\n  -webkit-background-clip: text; background-clip: text; color: transparent;\n}\n.subtitle { color: #5b5675; font-size: 1.02rem; margin-top: 6px; }\n\n.glass {\n  background: rgba(255,255,255,0.55);\n  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);\n  border-radius: 20px;\n  border: 1px solid rgba(255,255,255,0.75);\n  box-shadow: 0 8px 32px rgba(150,120,255,0.16);\n  padding: 24px;\n}\n.glass-soft {\n  background: rgba(255,255,255,0.42);\n  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);\n  border-radius: 18px;\n  border: 1px solid rgba(255,255,255,0.6);\n  box-shadow: 0 6px 24px rgba(150,120,255,0.12);\n  padding: 18px;\n}\n/* ---- real st.container cards (key= gives every container an st-key-* class).\n   These replaced HTML wrappers that left empty boxes on the page. ---- */\n.st-key-auth-card {\n  background: rgba(255,255,255,0.55);\n  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);\n  border-radius: 20px;\n  border: 1px solid rgba(255,255,255,0.75);\n  box-shadow: 0 8px 32px rgba(150,120,255,0.16);\n  padding: 30px 32px;\n  max-width: 560px;\n  margin: 4vh auto;\n}\n.st-key-card-profile, .st-key-card-password,\n.st-key-admin-card-logins, .st-key-admin-card-events, .st-key-admin-card-active {\n  background: rgba(255,255,255,0.55);\n  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);\n  border-radius: 20px;\n  border: 1px solid rgba(255,255,255,0.75);\n  box-shadow: 0 8px 32px rgba(150,120,255,0.16);\n  padding: 22px 24px;\n}\n.st-key-card-profile, .st-key-card-password { margin-bottom: 18px; }\n.brand-mini { color: #9333ea; font-weight: 700; font-size: 1.05rem; letter-spacing: 0.2px; }\n.divider-line { height: 3px; border-radius: 99px; margin: 14px 0 20px;\n  background: linear-gradient(90deg, rgba(34,211,238,0.7), rgba(232,121,249,0.15), rgba(139,92,246,0.7)); }\n\n.kpi-label { font-size: 0.72rem; letter-spacing: 1.6px; color: #6d6890; font-weight: 600; }\n.kpi-value { font-size: 2.6rem; font-weight: 800; color: #7c3aed; line-height: 1.1; }\n.kpi-sub { font-size: 0.82rem; color: #6d6890; }\n\n.item-name { font-weight: 700; font-size: 1rem; color: #2b2350; margin: 10px 0 4px;\n  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.9em; }\n.catalog-card { height:100%; min-height:260px; box-sizing:border-box; padding:15px;\n  border-radius:16px; background:rgba(255,255,255,.54); border:1px solid rgba(255,255,255,.78);\n  box-shadow:0 6px 20px rgba(129,105,218,.12); }\n.catalog-card-top { display:flex; justify-content:space-between; gap:8px; align-items:center; }\n.catalog-category { display:inline-block; padding:3px 8px; border-radius:999px; background:rgba(124,58,237,.13);\n  color:#6d28d9; font-size:.67rem; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }\n.catalog-sku { color:#77719a; font-size:.66rem; font-weight:600; }\n.catalog-title { margin:10px 0 7px; color:#2b2350; font-size:.94rem; font-weight:750; line-height:1.35;\n  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }\n.catalog-price { color:#6d28d9; font-size:1.02rem; font-weight:800; margin:-2px 0 6px; }\n.catalog-meta { color:#6d6890; font-size:.73rem; line-height:1.35; }\n.catalog-hero { padding:22px; border-radius:20px; background:linear-gradient(125deg,rgba(124,58,237,.12),rgba(34,211,238,.12),rgba(236,72,153,.10));\n  border:1px solid rgba(255,255,255,.78); box-shadow:0 8px 28px rgba(127,94,207,.12); }\n.demo-note { border-left:4px solid #8b5cf6; padding:10px 14px; border-radius:10px; background:rgba(139,92,246,.09); color:#4c1d95; font-size:.84rem; }\n.review-feed { padding:14px 16px; margin:9px 0; border-radius:15px; background:rgba(255,255,255,.45); border:1px solid rgba(255,255,255,.7); }\n.review-feed-text { color:#40385f; line-height:1.55; margin-top:7px; }\n.badge { display: inline-block; font-size: 0.68rem; font-weight: 700; color: #fff;\n  padding: 3px 10px; border-radius: 999px; margin-right: 6px; }\n.price-row { margin-top: 6px; font-size: 0.9rem; }\n.price-now { font-weight: 800; color: #2b2350; font-size: 1.02rem; }\n.price-was { text-decoration: line-through; color: #9a94b8; font-size: 0.8rem; margin-left: 6px; }\n.stars { color: #f59e0b; font-size: 0.82rem; letter-spacing: 1px; }\n\n.sent-pos { background: rgba(16,185,129,0.16); color: #047857; border: 1px solid rgba(16,185,129,0.4);\n  padding: 2px 12px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; }\n.sent-neg { background: rgba(244,63,94,0.12); color: #be123c; border: 1px solid rgba(244,63,94,0.4);\n  padding: 2px 12px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; }\n.sent-neu { background: rgba(139,92,246,0.12); color: #6d28d9; border: 1px solid rgba(139,92,246,0.4);\n  padding: 2px 12px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; }\n.aspect-tag { background: rgba(255,255,255,0.8); border: 1px solid #e3d9ff; color: #6d28d9;\n  padding: 2px 10px; border-radius: 999px; font-size: 0.7rem; font-weight: 600; margin-right: 4px; }\n\n.avatar { width: 78px; height: 78px; border-radius: 50%; object-fit: cover;\n  border: 3px solid rgba(255,255,255,0.9); box-shadow: 0 6px 18px rgba(147,51,234,0.3); }\n.avatar-sm { width: 52px; height: 52px; border-radius: 50%; object-fit: cover;\n  border: 2px solid rgba(255,255,255,0.9); box-shadow: 0 4px 12px rgba(147,51,234,0.25); }\n.avatar-fallback { display: flex; align-items: center; justify-content: center; color: #fff;\n  font-weight: 800; background: linear-gradient(135deg, #8b5cf6, #ec4899); }\n\n.stButton > button {\n  background: linear-gradient(135deg, #a855f7 0%, #ec4899 100%) !important;\n  color: #fff !important; border: none !important; border-radius: 999px !important;\n  padding: 0.55rem 1.9rem !important; font-weight: 600 !important; font-family: \'Poppins\', sans-serif !important;\n  box-shadow: 0 8px 20px rgba(168,85,247,0.35) !important;\n  transition: transform 0.15s ease, box-shadow 0.15s ease !important;\n}\n.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 12px 26px rgba(168,85,247,0.45) !important; }\n.stButton > button[kind="secondary"] {\n  background: rgba(255,255,255,0.85) !important; color: #4c1d95 !important;\n  border: 1px solid #e3d9ff !important; box-shadow: 0 4px 14px rgba(150,120,255,0.15) !important;\n}\n.stTextInput input, .stTextArea textarea {\n  border-radius: 14px !important; background: rgba(255,255,255,0.85) !important;\n  border: 1px solid rgba(200,180,255,0.5) !important;\n}\n.stSelectbox div[data-baseweb="select"] > div { border-radius: 14px !important;\n  background: rgba(255,255,255,0.85) !important; border: 1px solid rgba(200,180,255,0.5) !important; }\ndiv[data-testid="stRadio"] label { background: rgba(255,255,255,0.6); border: 1px solid rgba(255,255,255,0.7);\n  border-radius: 12px; padding: 6px 14px; margin-right: 6px; font-weight: 500; }\n.streamlit-expanderHeader { font-weight: 600; color: #4c1d95; }\nh1, h2, h3 { color: #2b2350; font-family: \'Poppins\', sans-serif; }\n.small-note { font-size: 0.78rem; color: #77719a; }\n\n/* ---- name-first product card (no images) ---- */\n.product-row { background:#ffffff; border:1px solid rgba(148,163,184,.34); border-radius:16px;\n  padding:14px 15px; min-height:112px; display:flex; flex-direction:column; justify-content:space-between;\n  box-shadow:0 4px 14px rgba(76,29,149,.06); transition:border-color .15s, box-shadow .15s; }\n.product-row.selected { border-color:#9333ea; box-shadow:0 0 0 2px rgba(147,51,234,.18); }\n.product-row-name { color:#2b2350; font-size:.94rem; font-weight:700; line-height:1.32;\n  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }\n.product-row-price { color:#6d28d9; font-size:1.02rem; font-weight:800; margin:8px 0 2px; }\n.product-row-meta { color:#6d6890; font-size:.73rem; }\n\n/* ---- review type chips on the product page ---- */\n.review-type-line { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }\n.review-type-chip { background:rgba(147,51,234,.10); color:#5b21b6; border-radius:999px;\n  padding:5px 12px; font-size:.76rem; font-weight:700; }\n.review-type-chip.pos { background:rgba(16,185,129,.14); color:#047857; }\n.review-type-chip.neu { background:rgba(139,92,246,.14); color:#6d28d9; }\n.review-type-chip.neg { background:rgba(244,63,94,.13); color:#be123c; }\n\n/* ---- "or" separator on the login card ---- */\n.or-sep { display:flex; align-items:center; gap:12px; margin:14px 0 6px; color:#8b84ad;\n  font-size:.76rem; font-weight:600; }\n.or-sep::before, .or-sep::after { content:""; height:1px; flex:1; background:rgba(148,163,184,.45); }\n\n/* ---- product hero: title left, close button right ---- */\n.hero-top { display:flex; justify-content:space-between; align-items:flex-start; gap:14px; }\n.hero-clear { color:#8b84ad; font-weight:800; font-size:1.05rem; }\n/* ---- the one-line caption under each suggestion button ---- */\n.suggest-meta { color:#6d6890; font-size:.72rem; text-align:center;\n  margin:-6px 0 12px; line-height:1.35; }\n</style>\n'

def apply_custom_css():
    """Inject the glassmorphism theme into the Streamlit app."""
    st.markdown(GLASS_CSS, unsafe_allow_html=True)



# ==========================================================================
# VIEWS/LOGIN.PY
# ==========================================================================

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

def login_with_google_profile(profile):
    """Find-or-create the account for a verified Google email, then log in."""
    email = profile['email'].strip().lower()
    user = get_user_by_login(email)
    if user is None:
        base = re.sub('[^A-Za-z0-9_]', '_', email.split('@')[0])[:16] or 'user'
        uname, i = (base, 1)
        while get_user_by_login(uname):
            i += 1
            uname = f'{base}{i}'
        user = create_user(uname, email, secrets.token_urlsafe(16), provider='google')
        log_event(user, 'signup', f'Registered via Google ({uname})')
    if profile.get('picture') and (not (user.get('profile_pic') or '')):
        try:
            resp = requests.get(profile['picture'], timeout=5)
            if resp.ok and resp.content:
                img = Image.open(io.BytesIO(resp.content)).convert('RGB')
                img.thumbnail((256, 256))
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                import base64
                update_user(user['id'], profile_pic=base64.b64encode(buf.getvalue()).decode())
                user = get_user_by_id(user['id'])
        except Exception:
            pass
    do_login(user, via='google')

def _native_google_button():
    """Primary button: Streamlit's built-in OIDC login."""
    if st.button('🌐  Continue with Google', type='primary', width='stretch', key='google_native'):
        st.login()
    return

def _legacy_google_button():
    """Fallback for the old GOOGLE_CLIENT_ID style secrets."""
    if st.button('🌐  Continue with Google', type='primary', width='stretch', key='google_signin'):
        st.session_state['go_google'] = True
        st.rerun()

def _google_setup_panel():
    """Shown when no Google configuration at all is present."""
    st.button('🌐  Continue with Google', type='primary', width='stretch', disabled=True)
    st.warning('**Google login is off** — no Google credentials were found.\n\nAdd the `[auth]` block shown in **GOOGLE_SETUP.md** under **Manage app → Settings → Secrets**, then reboot.')
    if st.button('🔍 Check my Google settings', width='stretch', key='diag_btn'):
        st.session_state['show_diag'] = True

def _diagnostics():
    """Real checks against Google, so no one is left staring at a 403 page."""
    st.markdown('#### 🔍 Google login check')
    st.caption('This reads your app secrets and asks Google whether they work.')
    if native_login_configured():
        st.success('✅ `[auth]` secrets found — Streamlit native login (st.login) is active.')
        try:
            auth = st.secrets['auth']
            cid = str(auth.get('client_id', ''))
            meta = str(auth.get('server_metadata_url', ''))
            st.code(f'client_id            : ...{cid[-32:]}\nserver_metadata_url  : {meta}\nredirect_uri needed  : https://<your-app>.streamlit.app{OAUTH_CALLBACK_PATH}')
            if cid and (not cid.endswith('.apps.googleusercontent.com')):
                st.error("client_id does not end with '.apps.googleusercontent.com' — it is probably the client SECRET pasted into the id field.")
        except Exception as exc:
            st.warning(f'Could not read the [auth] section: {exc}')
    else:
        st.info('No `[auth]` block found, so the app is using the legacy GOOGLE_CLIENT_ID path. The checks below test those values.')
        for level, msg in diagnose():
            {'ok': st.success, 'warn': st.warning, 'bad': st.error}[level](msg)
    st.markdown('##### If Google still shows *403 — you do not have access to this page*')
    for i, reason in enumerate(explain_403(), 1):
        st.markdown(f'{i}. {reason}')
    st.info('**The 403 is almost always the Google ACCOUNT, not the code.** Google Cloud → **Google Auth Platform** → **Audience** → **Test users** → **+ ADD USERS** → the exact Gmail you sign in with → **Save** → wait 10 minutes. Or click **Publish app** — this app only asks for name, email and profile, which needs no Google review.')
    st.markdown('**Redirect URI that must be registered in Google Cloud**')
    st.code(f'https://YOUR-APP.streamlit.app{OAUTH_CALLBACK_PATH}')
    st.caption('st.login() always returns to /oauth2callback. Without that exact URI registered, Google answers redirect_uri_mismatch.')

def auth_page():
    """Login / sign-up screen. One card, no choices beyond email-or-Google."""
    if st.session_state.pop('go_google', False):
        redirect_to_google(build_auth_url())
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        card = st.container(key='auth-card', border=False)
        with card:
            st.markdown(f'\n            <div class="auth-head">\n              <div class="brand-mini">🪄 {APP_NAME}</div>\n              <div class="gradient-title" style="font-size:2rem;">Know what customers really feel</div>\n              <div class="subtitle">Pick a product, read what people said, and see which\n                parts of it people loved or hated.</div>\n              <div class="divider-line"></div>\n            </div>\n            ', unsafe_allow_html=True)
            err = st.session_state.pop('oauth_error', None)
            if err:
                st.error(f'🔐 {err}')
            if native_login_configured():
                _native_google_button()
            elif is_google_configured():
                _legacy_google_button()
            else:
                _google_setup_panel()
            st.markdown("<div class='or-sep'><span>or use your email</span></div>", unsafe_allow_html=True)
            st.caption(f'build {BUILD}')
            mode = st.radio('Account', ['Log in', 'Create account'], horizontal=True, label_visibility='collapsed')
            if mode == 'Log in':
                login = st.text_input('Username or Gmail', placeholder='you@gmail.com')
                pwd = st.text_input('Password', type='password', placeholder='••••••••')
                if st.button('Log in', type='secondary', width='stretch'):
                    if not login or not pwd:
                        st.error('Enter your username/Gmail and password.')
                    else:
                        user = get_user_by_login(login)
                        if user and verify_password(pwd, user['password_hash'], user['salt']):
                            do_login(user, via='email')
                        else:
                            st.error("That login didn't match. Check the spelling, or create an account below.")
            else:
                username = st.text_input('Username', placeholder='sneha_21  (3–20 letters, numbers or _)')
                gmail = st.text_input('Gmail', placeholder='you@gmail.com')
                pwd = st.text_input('Password', type='password', placeholder='At least 6 characters, with a number')
                pwd2 = st.text_input('Confirm password', type='password', placeholder='Repeat the password')
                if st.button('Create account', type='secondary', width='stretch'):
                    if not valid_username(username or ''):
                        st.error('Username must be 3–20 characters: letters, numbers or underscore.')
                    elif not valid_gmail(gmail or ''):
                        st.error('Please use a valid **@gmail.com** address.')
                    elif (issues := password_issues(pwd or '')):
                        st.error('Password needs ' + ', '.join(issues) + '.')
                    elif pwd != pwd2:
                        st.error("The two passwords don't match.")
                    elif get_user_by_login(username):
                        st.error('That username is already taken.')
                    elif get_user_by_login(gmail):
                        st.error('That Gmail is already registered — log in instead.')
                    else:
                        user = create_user(username, gmail, pwd)
                        log_event(user, 'signup', f'New account created ({username})')
                        st.success('Account created. Logging you in… 🎉')
                        do_login(user, via='email')
    if st.session_state.get('show_diag'):
        with c2:
            _diagnostics()
            if st.button('✖ Close check', key='diag_close'):
                st.session_state['show_diag'] = False
                st.rerun()



# ==========================================================================
# VIEWS/ANALYSIS.PY
# ==========================================================================

"""
views/analysis.py — Built-in Product Review Intelligence workspace.
------------------------------------------------------------------
The upload-first workflow has been replaced with a professional catalog:
- 5,000 searchable product-style listings across broad shopping categories
- autocomplete-style suggestions as the user searches
- 10 clearly labelled demo reviews per product, with a sentiment mix that
  varies by product (strong, average and weak items all exist in the catalog)
- aspect-based NLP dashboard and a complete review feed
"""
import html
import pandas as pd
import streamlit as st
CATALOG_NAME = 'Built-in Product Catalog · generated demo data'

def _suggestions(query, limit=6):
    """Live suggestions that are actually useful.

    Without this, typing "head" returned six identical "Headlight Pair" variants
    because results were alphabetical. Candidates are now scored by where the
    match happened and then de-duplicated by product type, so one honest
    suggestion per kind of product comes back.
    """
    q = query.lower().strip()
    candidates = search_catalog(query, 'All categories', limit=120)

    def score(p):
        title = p['title'].lower()
        brand = p['brand'].lower()
        ptype = p['product_type'].lower()
        if title.startswith(q):
            return 0
        if ptype.startswith(q):
            return 1
        if brand.startswith(q):
            return 2
        if q in ptype:
            return 3
        if q in brand:
            return 4
        return 5
    used_types, out = (set(), [])
    for product in sorted(candidates, key=lambda p: (score(p), p['title'])):
        key = product['product_type'].lower()
        if key in used_types:
            continue
        used_types.add(key)
        out.append(product)
        if len(out) >= limit:
            break
    return out

def _analyse_and_store(user, product, reviews):
    """Run the NLP once and remember the result for this product."""
    cached = st.session_state.get('catalog_analysis', {})
    if cached.get('product_id') == product['id']:
        return cached['result']
    result = analyze_reviews(reviews)
    st.session_state['catalog_analysis'] = {'product_id': product['id'], 'result': result}
    save_analysis(user['id'], f"catalog:{product['id']}", product['title'], CATALOG_NAME, result['total'], result['overall']['positive'], result['overall']['neutral'], result['overall']['negative'], result['verdict'])
    log_event(user, 'catalog_analyse', f"Analysed {product['sku']} · {product['title']} → {result['verdict']}")
    return result

def _search_and_pick(user):
    """Step 1: type → suggestions appear → pick one. That is the whole interaction."""
    query = st.text_input('Search a product', placeholder='Start typing… e.g. headphones, Samsung, air fryer, brake pad', key='catalog_query', label_visibility='collapsed')
    selected_id = st.session_state.get('catalog_product_id')
    typed = (query or '').strip()
    if not typed:
        if not selected_id:
            picks = search_catalog('', 'All categories', limit=8, offset=0)
            st.caption('Popular right now — or type above to search.')
            _pick_grid(user, picks)
        return
    suggestions = _suggestions(typed)
    if not suggestions:
        st.info(f'No product matches “{typed}”. Try one word — like “shoes”, “TV” or “Bosch”.')
        return
    st.caption(f"**{catalog_match_count(typed, 'All categories'):,}** products match “{typed}” — pick one:")
    _pick_grid(user, suggestions, compact=True)
    if selected_id:
        _show_product(user, selected_id)

def _pick_grid(user, products, compact=False):
    """Clickable suggestion cards. One click = one product selected, no second button."""
    per_row = 2 if compact else 4
    for start in range(0, len(products), per_row):
        columns = st.columns(per_row)
        for index, product in enumerate(products[start:start + per_row]):
            with columns[index]:
                is_sel = st.session_state.get('catalog_product_id') == product['id']
                if st.button(product['title'], key=f"pick_{product['id']}", width='stretch', type='primary' if is_sel else 'secondary'):
                    st.session_state['catalog_product_id'] = product['id']
                    st.session_state.pop('catalog_analysis', None)
                    log_event(user, 'catalog_product_view', f"Opened {product['sku']} · {product['title']}")
                    st.rerun()
                st.markdown(f"<div class='suggest-meta'>{money(product.get('price'))} · {html.escape(product['product_type'])} · {product['review_count']} reviews</div>", unsafe_allow_html=True)

def _show_product(user, product_id):
    """Step 2: the product, its automatic analysis, and its reviews underneath."""
    product = get_catalog_product(product_id)
    if not product:
        st.session_state.pop('catalog_product_id', None)
        return
    reviews = get_catalog_reviews(product_id)
    average = sum((r['rating'] for r in reviews)) / max(1, len(reviews))
    pos_n = sum((1 for r in reviews if r.get('seed_sentiment') == 'positive'))
    neu_n = sum((1 for r in reviews if r.get('seed_sentiment') == 'neutral'))
    neg_n = sum((1 for r in reviews if r.get('seed_sentiment') == 'negative'))
    st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)
    st.markdown(f"""\n    <div class="catalog-hero">\n      <div class="hero-top">\n        <div>\n          <div class="gradient-title" style="font-size:1.55rem;">{html.escape(product['title'])}</div>\n          <div class="subtitle" style="margin-top:4px;">\n            <b>{html.escape(product['brand'])}</b> &nbsp;•&nbsp;\n            {html.escape(product['product_type'])} &nbsp;•&nbsp; {money(product.get('price'))}\n          </div>\n        </div>\n        <div class="hero-clear">✕</div>\n      </div>\n      <div class="review-type-line">\n        <span class="review-type-chip">📝 {len(reviews)} review samples</span>\n        <span class="review-type-chip pos">{pos_n} positive</span>\n        <span class="review-type-chip neu">{neu_n} neutral</span>\n        <span class="review-type-chip neg">{neg_n} negative</span>\n        <span class="review-type-chip">⭐ {average:.1f} / 5</span>\n      </div>\n    </div>""", unsafe_allow_html=True)
    result = _analyse_and_store(user, product, reviews)
    _dashboard(result, product)
    _review_feed(reviews, result['rows'])

def _review_feed(reviews, analysed_rows=None):
    """Show every review below the product, as requested—not only a sample."""
    sentiment_by_index = {}
    if analysed_rows:
        sentiment_by_index = {index: row.get('sentiment', 'neutral') for index, row in enumerate(analysed_rows)}
    st.markdown(f'### 💬 All catalog review samples ({len(reviews)})')
    st.caption('These are varied generated demonstration samples for this catalog item. The sentiment badge shows the NLP result after analysis; otherwise it shows the seeded review mix.')
    for index, review in enumerate(reviews):
        sentiment = sentiment_by_index.get(index, review.get('seed_sentiment', 'neutral'))
        label = 'NLP result' if analysed_rows else 'Demo mix'
        review_text = html.escape(str(review['text']))
        author = html.escape(str(review['author']))
        date = html.escape(str(review['date']))
        stars = stars_text(review.get('rating'))
        st.markdown(f'<div class="review-feed">\n          <b>{author}</b> <span class="small-note">• {date} • <span class="stars">{stars}</span></span>\n          &nbsp;{sent_badge(sentiment)} <span class="small-note">{label}</span>\n          <div class="review-feed-text">{review_text}</div>\n        </div>', unsafe_allow_html=True)

def _dashboard(result, product):
    title = html.escape(product['title'])
    st.markdown(f'### 📊 Review intelligence — {title}', unsafe_allow_html=True)
    overall = result['overall']
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="glass" style="text-align:center;"><div class="kpi-label">REVIEWS ANALYSED</div>\n          <div class="kpi-value">{result['total']}</div><div class="kpi-sub">full product review feed</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="glass" style="text-align:center;"><div class="kpi-label">OVERALL VERDICT</div>\n          <div style="font-size:1.4rem;font-weight:800;color:#6d28d9;">{result['verdict']}</div>\n          <div class="kpi-sub">{result['pos_pct']:.1f}% positive reviews</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="glass" style="text-align:center;"><div class="kpi-label">POSITIVE / NEGATIVE</div>\n          <div style="font-size:1.7rem;font-weight:800;"><span style="color:{POS_COLOR};">{overall['positive']}</span>\n          <span style="color:#b9b3d9;"> / </span><span style="color:{NEG_COLOR};">{overall['negative']}</span></div>\n          <div class="kpi-sub">{overall['neutral']} neutral reviews</div></div>""", unsafe_allow_html=True)
    with k4:
        best = max(result['aspects'], key=lambda aspect: result['aspects'][aspect]['positive'] - result['aspects'][aspect]['negative'])
        concern = min(result['aspects'], key=lambda aspect: result['aspects'][aspect]['positive'] - result['aspects'][aspect]['negative'])
        st.markdown(f'<div class="glass" style="text-align:center;"><div class="kpi-label">TOP / WATCH ASPECT</div>\n          <div style="font-size:1.1rem;font-weight:800;color:#047857;">👍 {best}</div>\n          <div style="font-size:1rem;font-weight:700;color:#be123c;">⚠️ {concern}</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig_donut(overall), width='stretch')
    with c2:
        st.plotly_chart(fig_bar(result['aspects']), width='stretch')
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(fig_sunburst(result['aspects'], result['total']), width='stretch')
    with c4:
        st.plotly_chart(fig_radar(result['aspects']), width='stretch')
    dates = [row.get('date', '') for row in result['rows']]
    sentiments = [row['sentiment'] for row in result['rows']]
    trend = fig_timeline(dates, sentiments) if any(dates) else None
    st.plotly_chart(trend if trend else fig_rolling(sentiments), width='stretch')
    ratings = [row['rating'] for row in result['rows'] if row.get('rating') is not None]
    if ratings:
        st.plotly_chart(fig_ratings(ratings), width='stretch')
    detail = []
    for aspect, counts in result['aspects'].items():
        total = max(1, counts['positive'] + counts['neutral'] + counts['negative'])
        detail.append({'Aspect': aspect, '👍 Positive': counts['positive'], '😐 Neutral': counts['neutral'], '👎 Negative': counts['negative'], 'Positivity %': round(counts['positive'] / total * 100, 1)})
    st.markdown('#### 🧩 Aspect detail')
    st.dataframe(pd.DataFrame(detail).sort_values('Positivity %', ascending=False), width='stretch', hide_index=True)

def page_analysis():
    """One page, one path: search → suggestion → product → analysis → reviews."""
    user = st.session_state.user
    header('What do you want to check?', 'Type a product. Pick it from the suggestions. The analysis appears immediately.')
    selected_id = st.session_state.get('catalog_product_id')
    if selected_id:
        product = get_catalog_product(selected_id)
        c1, c2 = st.columns([5, 1])
        with c2:
            if st.button('✕ Clear', width='stretch', type='secondary'):
                st.session_state.pop('catalog_product_id', None)
                st.session_state.pop('catalog_analysis', None)
                st.rerun()
    _search_and_pick(user)



# ==========================================================================
# VIEWS/PROFILE.PY
# ==========================================================================

"""
views/profile.py — My Account.
--------------------------------
Just the two things that matter: your name and your password.
No photo upload, no phone, no bio, no avatar upload — removed on purpose.
"""
import streamlit as st

def page_profile():
    user = st.session_state.user
    header('My Account', f'Change your name or your password.   ·   build {BUILD}')
    hist = fetch_df('SELECT COUNT(*) c FROM analysis_history WHERE user_id=?', (user['id'],))
    logins = fetch_df("SELECT COUNT(*) c FROM activity_logs WHERE user_id=? AND event_type IN ('login','google_login')", (user['id'],))
    st.markdown(f"""<div class="review-type-line" style="margin-bottom:16px;">\n        <span class="review-type-chip">👤 {user['username']}</span>\n        <span class="review-type-chip">{user['email']}</span>\n        <span class="review-type-chip pos">{(int(hist['c'][0]) if len(hist) else 0)} analyses</span>\n        <span class="review-type-chip">{(int(logins['c'][0]) if len(logins) else 0)} logins</span>\n      </div>""", unsafe_allow_html=True)
    with st.container(key='card-profile', border=False):
        st.markdown('##### ✏️ Edit profile')
        new_username = st.text_input('Username', value=user['username'])
        save = st.button('💾 Save changes', width='stretch')
    if save:
        if not valid_username(new_username):
            st.error('Username must be 3–20 chars: letters, numbers, underscore.')
        else:
            other = get_user_by_login(new_username)
            if other and other['id'] != user['id']:
                st.error('That username is already taken.')
            else:
                update_user(user['id'], username=new_username.strip())
                st.session_state.user = get_user_by_id(user['id'])
                log_event(st.session_state.user, 'update_profile', f'Updated profile (username={new_username})')
                st.success('Profile saved!')
                st.rerun()
    with st.container(key='card-password', border=False):
        st.markdown('##### 🔑 Change password')
        if user['provider'] == 'google':
            st.info('You signed in with Google — set an email password below to also enable email login.')
            old = None
        else:
            old = st.text_input('Current password', type='password')
        new1 = st.text_input('New password', type='password')
        new2 = st.text_input('Confirm new password', type='password')
        update = st.button('🔐 Update password', width='stretch')
    if update:
        if old is not None and (not verify_password(old or '', user['password_hash'], user['salt'])):
            st.error('Current password is incorrect.')
        elif (issues := password_issues(new1 or '')):
            st.error('New password needs ' + ', '.join(issues) + '.')
        elif new1 != new2:
            st.error('New passwords do not match.')
        else:
            phash, salt = hash_password(new1)
            update_user(user['id'], password_hash=phash, salt=salt)
            st.session_state.user = get_user_by_id(user['id'])
            log_event(st.session_state.user, 'change_password', 'Changed password')
            st.success('Password updated!')



# ==========================================================================
# VIEWS/HISTORY.PY
# ==========================================================================

"""
views/history.py — My Analysis History screen.
Lists every product the logged-in user has analysed + CSV download.
"""
import streamlit as st

def page_history():
    user = st.session_state.user
    header('My Analysis History', 'Every product you have analysed, with verdicts over time.')
    df = fetch_df('SELECT product_name AS Item, platform AS Catalog, total_reviews AS Reviews,\n                            positive AS Positive, neutral AS Neutral, negative AS Negative,\n                            overall AS Verdict, timestamp AS Analysed_At\n                     FROM analysis_history WHERE user_id=? ORDER BY id DESC', (user['id'],))
    if df.empty:
        st.info('No analyses yet — open **🛍️ Product Explorer**, choose a product, and analyse its reviews.')
        return
    st.dataframe(df, width='stretch', hide_index=True)
    csv = df.to_csv(index=False).encode()
    st.download_button('⬇️ Download my history (CSV)', csv, 'my_analysis_history.csv', 'text/csv', type='secondary')



# ==========================================================================
# VIEWS/ADMIN.PY
# ==========================================================================

"""
views/admin.py — Admin Panel (admins only).
-------------------------------------------
Full user tracking: login times, every action, logout/leave times,
session durations, activity charts, role management, CSV exports.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

def page_admin():
    user = st.session_state.user
    if not user.get('is_admin'):
        st.error('⛔ Admins only.')
        return
    header('Admin Panel — User Tracking', 'Monitor logins, live activity, analyses and session/leave times for every user.')
    log_event(user, 'view_admin', 'Opened admin panel')
    users_df = fetch_df('SELECT id,username,email,provider,is_admin,created_at,last_login FROM users ORDER BY id')
    logs_df = fetch_df('SELECT * FROM activity_logs ORDER BY id DESC LIMIT 2000')
    hist_df = fetch_df('SELECT * FROM analysis_history ORDER BY id DESC LIMIT 2000')
    m1, m2, m3, m4 = st.columns(4)
    today = datetime.now().strftime('%Y-%m-%d')
    active_today = int(logs_df[logs_df['timestamp'].astype(str).str.startswith(today)]['user_id'].nunique()) if not logs_df.empty else 0
    for col, label, val, sub in [(m1, 'TOTAL USERS', len(users_df), f"{int(users_df['is_admin'].sum())} admins"), (m2, 'ACTIVE TODAY', active_today, f'{len(logs_df)} events logged'), (m3, 'TOTAL ANALYSES', len(hist_df), 'across all users'), (m4, 'TOTAL LOGINS', int(logs_df['event_type'].isin(['login', 'google_login']).sum()) if not logs_df.empty else 0, 'email + google')]:
        col.markdown(f'<div class="glass" style="text-align:center;">\n          <div class="kpi-label">{label}</div><div class="kpi-value">{val}</div>\n          <div class="kpi-sub">{sub}</div></div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(['🕵️ Live User Tracking', '👥 Users', '📈 Analytics', '📥 Export'])
    with tab1:
        st.markdown('##### Who did what, when — including login & leave (logout) times')
        f1, f2, f3 = st.columns([1.4, 1, 1.4])
        with f1:
            q_user = st.text_input('Filter by username/email', key='adm_q')
        with f2:
            ev_types = ['All'] + sorted(logs_df['event_type'].unique().tolist()) if not logs_df.empty else ['All']
            q_ev = st.selectbox('Event', ev_types)
        with f3:
            q_sess = st.text_input('Session ID (optional)', key='adm_s')
        view = logs_df.copy()
        if not view.empty:
            if q_user:
                view = view[view['username'].str.contains(q_user, case=False, na=False) | view['email'].str.contains(q_user, case=False, na=False)]
            if q_ev != 'All':
                view = view[view['event_type'] == q_ev]
            if q_sess:
                view = view[view['session_id'].str.contains(q_sess, na=False)]
        st.dataframe(view[['timestamp', 'username', 'email', 'event_type', 'detail', 'session_id']] if not view.empty else view, width='stretch', hide_index=True, height=420)
        st.markdown('##### ⏱️ Session durations (login → logout/leave)')
        if not logs_df.empty:
            sess = logs_df[logs_df['event_type'].isin(['login', 'google_login', 'logout'])].copy()
            sess['timestamp'] = pd.to_datetime(sess['timestamp'])
            rows = []
            for (uid, uname, sid), g in sess.groupby(['user_id', 'username', 'session_id']):
                g = g.sort_values('timestamp')
                start = g[g['event_type'].isin(['login', 'google_login'])]['timestamp'].min()
                end = g[g['event_type'] == 'logout']['timestamp'].max()
                if pd.notna(start):
                    rows.append({'User': uname, 'Login at': start.strftime('%Y-%m-%d %H:%M:%S'), 'Left at': end.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(end) else '— still in / closed tab —', 'Duration': str(end - start).split('.')[0] if pd.notna(end) else '—'})
            st.dataframe(pd.DataFrame(rows).tail(50), width='stretch', hide_index=True)
            st.caption('Note: clicking **Logout** records an exact leave time. If a user just closes the tab, their last activity timestamp above is the best available leave signal.')
    with tab2:
        st.markdown('##### Registered users')
        st.dataframe(users_df, width='stretch', hide_index=True)
        st.markdown('##### Promote / demote admin')
        c_a, c_b = st.columns([2, 1])
        with c_a:
            target = st.selectbox('User email', users_df['email'].tolist() if not users_df.empty else [])
        with c_b:
            role = st.selectbox('Role', ['User', 'Admin'])
        if st.button('Apply role', type='secondary'):
            if target == user['email'] and role == 'User':
                st.error('You cannot demote your own account — ask another admin to do it.')
            else:
                conn = get_conn()
                conn.execute('UPDATE users SET is_admin=? WHERE email=?', (1 if role == 'Admin' else 0, target))
                conn.commit()
                conn.close()
                log_event(user, 'admin_action', f'Set {target} → {role}')
                st.success(f'{target} is now {role}.')
                st.rerun()
    with tab3:
        if logs_df.empty:
            st.info('No activity yet.')
        else:
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
            d1 = logs_df[logs_df['event_type'].isin(['login', 'google_login'])].copy()
            g1, g2 = st.columns(2)
            with g1:
                with st.container(key='admin-card-logins', border=False):
                    if not d1.empty:
                        d1['day'] = d1['timestamp'].dt.strftime('%d %b')
                        fig = px.bar(d1.groupby('day').size().reset_index(name='logins'), x='day', y='logins', title='Logins per day', color_discrete_sequence=['#9333ea'])
                        st.plotly_chart(style_fig(fig, 320), width='stretch')
                    else:
                        st.info('No logins yet.')
            with g2:
                with st.container(key='admin-card-events', border=False):
                    ev = logs_df['event_type'].value_counts().reset_index()
                    ev.columns = ['event', 'count']
                    fig = px.pie(ev, names='event', values='count', hole=0.5, title='Event distribution', color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(style_fig(fig, 320), width='stretch')
            with st.container(key='admin-card-active', border=False):
                top = logs_df['username'].value_counts().head(10).reset_index()
                top.columns = ['user', 'events']
                fig = px.bar(top, x='user', y='events', title='Most active users (events)', color_discrete_sequence=['#ec4899'])
                st.plotly_chart(style_fig(fig, 320), width='stretch')
    with tab4:
        st.markdown('##### Download data')
        e1, e2, e3 = st.columns(3)
        with e1:
            st.download_button('⬇️ Users CSV', users_df.to_csv(index=False).encode(), 'users.csv', 'text/csv', type='secondary')
        with e2:
            st.download_button('⬇️ Activity logs CSV', logs_df.to_csv(index=False).encode(), 'activity_logs.csv', 'text/csv', type='secondary')
        with e3:
            st.download_button('⬇️ Analyses CSV', hist_df.to_csv(index=False).encode(), 'all_analyses.csv', 'text/csv', type='secondary')


# ============================================================================
# VIEW NAMESPACES — the router calls login.auth_page(), analysis.page_analysis()
# etc., exactly as it did when these lived in the views/ package.
# ============================================================================


class _ViewModule:
    """Tiny namespace object: _ViewModule(fn1=..., fn2=...)"""

    def __init__(self, **members):
        self.__dict__.update(members)


login = _ViewModule(auth_page=auth_page, login_with_google_profile=login_with_google_profile)
analysis = _ViewModule(page_analysis=page_analysis)
profile = _ViewModule(page_profile=page_profile)
history = _ViewModule(page_history=page_history)
admin = _ViewModule(page_admin=page_admin)


# ============================================================================
# SIDEBAR + ENTRY POINT
# ============================================================================


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
            # Also end the Streamlit native OIDC session (no-op if st.login is
            # not configured). Without it Google logs the user straight back in.
            try:
                if current_native_user():
                    st.logout()
            except Exception:
                pass
            st.rerun()
        st.markdown("---")
        with st.expander("ℹ️ How it works"):
            st.caption("1️⃣ Type a product in the search box.\n\n"
                       "2️⃣ Pick it from the suggestions that appear.\n\n"
                       "3️⃣ The analysis runs instantly — verdict, 8 aspects, charts.\n\n"
                       "4️⃣ Its reviews are listed underneath.\n\n"
                       "All review text is generated demo data.")


def _runtime_facts() -> str:
    return "\n".join([
        f"python    : {sys.version.split()[0]}",
        f"streamlit : {st.__version__}",
        f"app folder: {BASE_DIR}",
        f"database  : {DB_PATH}",
    ])


def _show_boot_error(exc: BaseException):
    """A readable card instead of Streamlit's redacted traceback."""
    traceback.print_exc()
    st.error("**Something went wrong while starting the app.**")
    st.markdown("Press reload below. If it repeats, open *Technical detail* and share it.")
    if st.button("🔄 Reload the app", type="primary"):
        st.rerun()
    with st.expander("Technical detail"):
        st.code(_runtime_facts())
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:])
    st.stop()


def _stage_bundle():
    """Unpack a bundled zip next to this file (existing files are never overwritten)."""
    try:
        for name in sorted(f for f in os.listdir(BASE_DIR) if f.lower().endswith(".zip")):
            with zipfile.ZipFile(os.path.join(BASE_DIR, name)) as bundle:
                for info in bundle.infolist():
                    if info.filename.endswith("/"):
                        continue
                    target = os.path.join(BASE_DIR, os.path.basename(info.filename))
                    if not os.path.exists(target):
                        with bundle.open(info) as src, open(target, "wb") as out:
                            out.write(src.read())
            break
    except Exception:
        pass                        # staging is best-effort, never fatal


def main():
    _stage_bundle()
    init_db()

    # ---- Streamlit native OIDC (st.login) -------------------------------
    # Streamlit performs the handshake and exposes the identity on st.user.
    # Adopted BEFORE the login gate so a returning user never sees it again.
    if "user" not in st.session_state or st.session_state.user is None:
        native_profile = current_native_user()
        if native_profile and native_profile.get("email"):
            login.login_with_google_profile(native_profile)

    # Legacy hand-built OAuth callback (?code=...) — also before the gate.
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


st.set_page_config(
    page_title="AspectLens • Aspect Sentiment Analytics",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_custom_css()

try:
    main()
except Exception as _boot_exc:
    _show_boot_error(_boot_exc)
