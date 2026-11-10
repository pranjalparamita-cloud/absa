"""
AspectLens — Aspect-Based Sentiment Analytics (complete app, ONE file)
Run locally:        streamlit run app.py
Streamlit Cloud:    main file path = app.py
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
# CONFIG & PATHS
# ==========================================================================
APP_NAME = 'AspectLens'
OAUTH_CALLBACK_PATH = '/oauth2callback'
BUILD = 'v9 · Fast 10k Catalog Edition'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _writable(folder: str) -> bool:
    try:
        probe = os.path.join(folder, '.write_test')
        with open(probe, 'w') as fh:
            fh.write('ok')
        os.remove(probe)
        return True
    except Exception:
        return False

def _resolve_db_path() -> str:
    override = os.environ.get('ABSA_DB_PATH', '').strip()
    if override:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(override)), exist_ok=True)
        except Exception:
            pass
        return override
    if _writable(BASE_DIR):
        return os.path.join(BASE_DIR, 'absa.db')
    return os.path.join(tempfile.gettempdir(), 'absa.db')

DB_PATH = _resolve_db_path()
POS_COLOR = '#10b981'
NEG_COLOR = '#f43f5e'
NEU_COLOR = '#8b5cf6'
ACCENT = '#9333ea'

# ==========================================================================
# DATABASE LAYER
# ==========================================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA busy_timeout = 30000')
        conn.execute('PRAGMA synchronous = OFF')
        conn.execute('PRAGMA journal_mode = MEMORY')
    except Exception:
        pass
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            profile_pic TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            is_admin INTEGER DEFAULT 0,
            provider TEXT DEFAULT 'email',
            created_at TEXT NOT NULL,
            last_login TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalog_products (
            id INTEGER PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            product_type TEXT NOT NULL,
            review_count INTEGER NOT NULL DEFAULT 0,
            price REAL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalog_reviews (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            reviewer TEXT NOT NULL,
            rating REAL,
            review_text TEXT NOT NULL,
            review_date TEXT,
            seed_sentiment TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES catalog_products(id)
        )
    """)
    cur.execute('CREATE INDEX IF NOT EXISTS idx_catalog_products_title ON catalog_products(title)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_catalog_products_category ON catalog_products(category)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_catalog_products_brand ON catalog_products(brand)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_catalog_reviews_product ON catalog_reviews(product_id)')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            email TEXT,
            event_type TEXT,
            detail TEXT,
            timestamp TEXT,
            session_id TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id TEXT,
            product_name TEXT,
            platform TEXT,
            total_reviews INTEGER,
            positive INTEGER,
            neutral INTEGER,
            negative INTEGER,
            overall TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    seeds = [('admin', 'admin@gmail.com', 'Admin@123', 1, 'email'), ('demo', 'demo@gmail.com', 'Demo@123', 0, 'email')]
    for username, email, pwd, is_admin, provider in seeds:
        cur.execute('SELECT id FROM users WHERE email=?', (email,))
        if cur.fetchone() is None:
            phash, salt = hash_password(pwd)
            cur.execute('INSERT INTO users (username,email,password_hash,salt,is_admin,provider,created_at) VALUES (?,?,?,?,?,?,?)', (username, email, phash, salt, is_admin, provider, now))
    conn.commit()
    try:
        ensure_catalog_seed(conn)
    except Exception:
        conn.rollback()
    conn.close()

def row_to_dict(row):
    return dict(row) if row else None

def create_user(username, email, password, provider='email', is_admin=0):
    conn = get_conn()
    cur = conn.cursor()
    phash, salt = hash_password(password)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute('INSERT INTO users (username,email,password_hash,salt,is_admin,provider,created_at) VALUES (?,?,?,?,?,?,?)', (username.strip(), email.strip().lower(), phash, salt, is_admin, provider, now))
    uid = cur.lastrowid
    conn.commit()
    cur.execute('SELECT * FROM users WHERE id=?', (uid,))
    user = row_to_dict(cur.fetchone())
    conn.close()
    return user

def get_user_by_login(login: str):
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
    try:
        value = user[key]
    except (KeyError, IndexError, TypeError):
        try:
            value = user.get(key, default)
        except AttributeError:
            return default
    return value if value is not None else default

def log_event(user, event_type: str, detail: str=''):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('INSERT INTO activity_logs (user_id,username,email,event_type,detail,timestamp,session_id) VALUES (?,?,?,?,?,?,?)', (_get(user, 'id'), _get(user, 'username', 'guest'), _get(user, 'email', ''), event_type, detail[:500], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), st.session_state.get('session_id', '')))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_analysis(user_id, dataset_id, item_name, dataset_name, total, pos, neu, neg, overall):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT INTO analysis_history (user_id,product_id,product_name,platform,total_reviews,positive,neutral,negative,overall,timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)', (user_id, str(dataset_id), item_name, dataset_name, total, pos, neu, neg, overall, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def fetch_df(query, params=()):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# ==========================================================================
# AUTH HELPERS
# ==========================================================================
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
    return bool(EMAIL_RE.match((email or '').strip()))

def valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match((username or '').strip()))

def password_issues(pwd: str):
    issues = []
    if len(pwd or '') < 6:
        issues.append('at least 6 characters')
    if not re.search('[A-Za-z]', pwd or ''):
        issues.append('one letter')
    if not re.search('\\d', pwd or ''):
        issues.append('one number')
    return issues

def do_login(user, via='email'):
    st.session_state.user = get_user_by_id(user['id'])
    st.session_state.session_id = uuid.uuid4().hex[:12]
    st.session_state.login_time = datetime.now()
    st.session_state.page = '🛍️ Products'
    update_user(user['id'], last_login=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log_event(st.session_state.user, 'login' if via == 'email' else 'google_login', f'Logged in via {via}')
    st.rerun()

# ==========================================================================
# GOOGLE AUTH
# ==========================================================================
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
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
    low = (value or '').lower()
    if not low or len(low) < 20:
        return False
    return not any((marker in low for marker in _PLACEHOLDERS))

def is_google_configured() -> bool:
    return _looks_real(google_client_id()) and _looks_real(google_client_secret()) and bool(google_redirect_uri().startswith(('https://', 'http://')))

def build_auth_url() -> str:
    if 'oauth_state' not in st.session_state:
        st.session_state['oauth_state'] = secrets.token_urlsafe(24)
    state = st.session_state['oauth_state']
    params = {
        'client_id': google_client_id(),
        'redirect_uri': google_redirect_uri(),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account'
    }
    return GOOGLE_AUTH_URL + '?' + urllib.parse.urlencode(params)

def redirect_to_google(auth_url: str):
    st.markdown(f'<div class="glass" style="text-align:center; max-width:480px; margin:10vh auto;"><div style="font-size:2.2rem;">🔐</div><h3>Taking you to Google…</h3><p class="small-note">Pick one of your logged-in Gmail accounts on the next screen.</p><meta http-equiv="refresh" content="0;url={auth_url}"></div>', unsafe_allow_html=True)
    st.stop()

def handle_oauth_callback():
    try:
        code = st.query_params.get('code')
        state = st.query_params.get('state')
        error = st.query_params.get('error')
    except Exception:
        return (None, None)

    if not code and not error:
        return (None, None)

    st.query_params.clear()

    if error:
        return (None, f'Google sign-in error: {error}')

    saved_state = st.session_state.pop('oauth_state', None)
    if state and saved_state and state != saved_state:
        return (None, 'State mismatch. Please click Continue with Google again.')

    try:
        token_resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'code': code,
                'client_id': google_client_id(),
                'client_secret': google_client_secret(),
                'redirect_uri': google_redirect_uri(),
                'grant_type': 'authorization_code'
            },
            timeout=20
        )
        token = token_resp.json()
        if 'access_token' not in token:
            detail = token.get('error_description', token.get('error', 'unknown error'))
            return (None, f'Google token error: {detail}')

        me = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f"Bearer {token['access_token']}"},
            timeout=20
        ).json()

        if not me.get('email'):
            return (None, 'Google did not return an email address.')

        return ({'email': me['email'], 'name': me.get('name', ''), 'picture': me.get('picture', '')}, None)

    except requests.RequestException as e:
        return (None, f'Could not reach Google: {e}')

# ==========================================================================
# 10,000 CATALOG SEED & DATA
# ==========================================================================
CATALOG_VERSION = 'catalog-10k-v2'
TOTAL_PRODUCTS_TARGET = 10000
REVIEWS_PER_PRODUCT = 10

CATEGORY_SPECS = [
    ('Electronics', ['Samsung', 'Sony', 'LG', 'Panasonic', 'Philips', 'JBL', 'Bose', 'Canon', 'Nikon', 'Xiaomi'], ['4K Smart TV', 'Noise Cancelling Headphones', 'Portable Bluetooth Speaker', 'Soundbar', 'Mirrorless Camera', 'Smart Projector', 'Wireless Earbuds', 'Home Theatre System', 'Digital Camera', 'LED Monitor']),
    ('Mobile Accessories', ['Anker', 'Belkin', 'Spigen', 'UGREEN', 'ESR', 'OtterBox', 'Baseus', 'Portronics', 'boAt', 'Ambrane'], ['USB-C GaN Charger', 'Magnetic Power Bank', 'Protective Phone Case', 'Tempered Glass Pack', 'Fast Charging Cable', 'Wireless Charging Stand', 'Car Phone Mount', 'Bluetooth Tracker', 'Mobile Tripod', 'Laptop Sleeve']),
    ('Computers & Gaming', ['Dell', 'HP', 'Lenovo', 'ASUS', 'Acer', 'MSI', 'Logitech', 'Razer', 'Corsair', 'SteelSeries'], ['Gaming Laptop', 'Mechanical Keyboard', 'Wireless Mouse', '27-inch Monitor', 'Gaming Headset', 'USB-C Dock', 'External SSD', 'Wi-Fi Router', 'Webcam', 'Gaming Controller']),
    ('Home Appliances', ['Whirlpool', 'Bosch', 'Haier', 'LG', 'Samsung', 'Philips', 'Bajaj', 'Kent', 'Dyson', 'Havells'], ['Air Fryer', 'Water Purifier', 'Robot Vacuum', 'Microwave Oven', 'Front Load Washer', 'Air Purifier', 'Mixer Grinder', 'Coffee Maker', 'Electric Kettle', 'Ceiling Fan']),
    ('Automotive Parts', ['Bosch', 'Denso', 'NGK', 'Valeo', 'MANN-FILTER', 'SKF', 'Monroe', 'Gates', 'Brembo', 'Castrol'], ['Brake Pad Set', 'Engine Air Filter', 'Oil Filter', 'Spark Plug Kit', 'Wiper Blade Pair', 'Drive Belt', 'Wheel Bearing Kit', 'Clutch Cable', 'Fuel Pump Module', 'Shock Absorber']),
    ('Automotive Accessories', ['Michelin', '3M', 'Garmin', 'Pioneer', 'JBL', 'Philips', 'Bosch', "Meguiar's", 'Goodyear', 'Turtle Wax'], ['Dash Camera', 'Tyre Inflator', 'Car Vacuum Cleaner', 'Seat Cover Set', 'Reverse Camera', 'Car Stereo', 'Phone Holder', 'Car Care Kit', 'LED Headlight Pair', 'Roof Carrier']),
    ('Home & Kitchen', ['Prestige', 'Hawkins', 'Philips', 'Borosil', 'Tefal', 'IKEA', 'Milton', 'Pigeon', 'Bajaj', 'Kent'], ['Induction Cooktop', 'Non-stick Cookware Set', 'Storage Container Set', 'Vacuum Flask', 'Kitchen Scale', 'Water Bottle Set', 'Knife Set', 'Clothes Drying Rack', 'Table Lamp', 'Food Chopper']),
    ('Fashion & Beauty', ['Nike', 'Adidas', 'Puma', 'Skechers', "Levi's", 'Maybelline', "L'Oréal", 'Nivea', 'Dove', 'Lakmé'], ['Running Shoes', 'Everyday Backpack', 'Sports T-Shirt', 'Analog Watch', 'Sunglasses', 'Skin Care Set', 'Hair Dryer', 'Fragrance Gift Set', 'Makeup Kit', 'Travel Wallet']),
    ('Sports & Outdoors', ['Decathlon', 'Nike', 'Adidas', 'Puma', 'Yonex', 'Wilson', 'Coleman', 'Quechua', 'Nivia', 'Cosco'], ['Yoga Mat', 'Badminton Racket', 'Cricket Bat', 'Camping Tent', 'Trekking Backpack', 'Fitness Tracker', 'Resistance Band Set', 'Football', 'Cycling Helmet', 'Waterproof Jacket']),
    ('Books & Office', ['HP', 'Canon', 'Epson', 'Brother', 'Casio', 'Faber-Castell', 'Moleskine', 'Parker', 'Kangaro', 'Classmate'], ['Wireless Printer', 'Ink Cartridge Set', 'Scientific Calculator', 'Premium Notebook', 'Ball Pen Set', 'Desk Organiser', 'Document Scanner', 'Label Maker', 'Stapler Set', 'Office Chair']),
    ('Grocery & Gourmet', ['Tata', 'Nestle', 'Organic India', 'Kellogg\'s', 'Dabur', 'Cadbury', 'Saffola', 'Catch', 'Fortune', 'Urban Platter'], ['Extra Virgin Olive Oil', 'Organic Green Tea', 'Whole Grain Oats', 'Dark Chocolate Pack', 'Multigrain Atta', 'Raw Honey', 'Almonds & Nuts Pack', 'Instant Coffee Powder', 'Basmati Rice 5kg', 'Protein Bars Pack']),
    ('Health & Personal Care', ['Dettol', 'Himalaya', 'Sensodyne', 'Colgate', 'Gillette', 'Oral-B', 'Dr. Morepen', 'Omron', 'Pampers', 'Johnson\'s'], ['Digital Blood Pressure Monitor', 'Electric Toothbrush', 'First Aid Kit', 'Pulse Oximeter', 'Multivitamin Tablets', 'Whey Protein Powder', 'Personal Weighing Scale', 'Heating Pad', 'Nebulizer', 'Disinfectant Spray']),
    ('Toys & Baby Products', ['Lego', 'Hot Wheels', 'Barbie', 'Fisher-Price', 'Chicco', 'Mee Mee', 'Hamleys', 'Funskool', 'Disney', 'Pampers'], ['Building Blocks Set', 'Diecast Racing Car', 'Interactive Baby Walker', 'Stroller Tricycle', 'Plush Teddy Bear', 'STEM Educational Kit', 'Wooden Puzzle Set', 'Baby Carrier Sling', 'Remote Control Car', 'Board Game Classic']),
    ('Tools & Home Improvement', ['Bosch', 'Stanley', 'Black+Decker', 'DeWalt', 'Makita', 'Taparia', 'Asian Paints', 'Havells', 'Anchor', 'Syska'], ['Cordless Drill Kit', 'Tool Box Set 100-pc', 'LED Flood Light', 'Digital Multimeter', 'Laser Distance Meter', 'Hot Air Gun', 'Screwdriver Set', 'Paint Sprayer', 'Extension Cord Wheel', 'Step Ladder 4-Step']),
    ('Pet Supplies', ['Pedigree', 'Whiskas', 'Royal Canin', 'Drools', 'Choostix', 'Purina', 'Meatables', 'Heads Up For Tails', 'KONG', 'Fur滑动'], ['Dry Adult Dog Food 10kg', 'Cat Wet Food Pouches', 'Interactive Dog Toy Ball', 'Cat Litter 10kg', 'Pet Grooming Brush', 'Orthopedic Dog Bed', 'Pet Shampoo & Conditioner', 'Dog Harness & Leash', 'Cat Scratching Post', 'Pet Travel Carrier'])
]

TYPE_PRICE = {
    '4K Smart TV': (18999, 129999), 'Noise Cancelling Headphones': (2999, 34999), 'Portable Bluetooth Speaker': (1499, 24999),
    'Gaming Laptop': (44999, 249999), 'Air Fryer': (2999, 18999), 'Brake Pad Set': (899, 7999), 'Dash Camera': (1999, 18999),
    'Induction Cooktop': (1499, 9999), 'Running Shoes': (1499, 14999), 'Yoga Mat': (399, 3999), 'Wireless Printer': (5999, 34999),
    'Extra Virgin Olive Oil': (499, 2499), 'Digital Blood Pressure Monitor': (1299, 4999), 'Building Blocks Set': (599, 7999),
    'Cordless Drill Kit': (2499, 14999), 'Dry Adult Dog Food 10kg': (1899, 6999)
}

EDITIONS = ['Essential', 'Plus', 'Pro', 'Smart', 'Signature', 'Ultra', 'Everyday', 'Advance', 'Prime', 'Select', 'Max', 'Lite', 'Elite', 'Vibe', 'Studio']
EDITION_MULTIPLIER = {'Essential': 0.85, 'Plus': 1.0, 'Pro': 1.25, 'Smart': 1.1, 'Signature': 1.45, 'Ultra': 1.6, 'Everyday': 0.8, 'Advance': 1.15, 'Prime': 1.3, 'Select': 1.05, 'Max': 1.5, 'Lite': 0.75, 'Elite': 1.7, 'Vibe': 0.9, 'Studio': 1.35}
COLORS = ['Graphite', 'Midnight', 'Silver', 'Blue', 'Black', 'White', 'Sand', 'Rose', 'Green', 'Titanium', 'Crimson', 'Emerald', 'Gold', 'Amber', 'Obsidian']
REVIEWERS = ['Aarav', 'Ananya', 'Rohan', 'Meera', 'Ishaan', 'Kavya', 'Arjun', 'Diya', 'Vihaan', 'Saanvi', 'Rahul', 'Priya', 'Neha', 'Aditya', 'Sneha', 'Karan', 'Riya', 'Vikram', 'Aisha', 'Nikhil']
POSITIVE = ['The build quality feels premium and sturdy. Performance has been smooth and I am very satisfied.', 'Delivery was quick and the packaging kept everything safe. Great value for money.', 'The design looks sleek and the useful features work very well. Definitely recommend it.', 'Setup was easy, quality is excellent, and it has been reliable during daily use.', 'This is a well-made product with strong performance. It exceeded my expectations for the price.', 'Battery life is impressive and charging is fast. Very happy with this purchase.', 'The finish is flawless and it feels genuine, not like a duplicate. Worth every rupee.', 'Support was helpful and the replacement arrived quickly. Excellent service overall.']
NEUTRAL = ['It does the job as expected. The design is fine, although the price is a bit high.', 'Packaging was acceptable and delivery was on time. Nothing exceptional, but it is usable.', 'The features work reasonably well after setup. Quality is average for this price range.', 'It is an okay product. Performance is standard and nothing stands out.']
NEGATIVE = ['Build quality feels poor and the price is expensive. I expected better performance.', 'Delivery was delayed and the packaging arrived damaged. The overall experience was disappointing.', 'Performance is inconsistent and support was unhelpful. It stopped working sooner than expected.', 'It arrived scratched and the box was torn. Very disappointing for the price.']
MIX_PATTERNS = [(7, 2, 1), (7, 3, 0), (6, 3, 1), (6, 2, 2), (5, 3, 2), (5, 4, 1), (4, 4, 2), (4, 3, 3), (3, 4, 3), (3, 3, 4), (2, 4, 4), (1, 4, 5)]
POS_RATINGS = [5, 5, 4, 5, 4, 5, 4]
NEU_RATINGS = [3, 3, 4, 2]
NEG_RATINGS = [1, 2, 1, 2, 1]

def _product_rows(target_count=TOTAL_PRODUCTS_TARGET):
    rows = []
    product_id = 1
    per_cat = target_count // len(CATEGORY_SPECS)
    for category_index, (category, brands, types) in enumerate(CATEGORY_SPECS, start=1):
        for offset in range(per_cat):
            brand = brands[offset % len(brands)]
            product_type = types[(offset // len(brands) + offset) % len(types)]
            edition = EDITIONS[(offset // 7 + category_index) % len(EDITIONS)]
            colour = COLORS[(offset * 3 + category_index) % len(COLORS)]
            model = f'{chr(65 + (offset % 26))}{offset // 26 + 10}-{category_index}{offset % 100:02d}'
            title = f'{brand} {product_type} {edition} {model} — {colour}'
            sku = f'AL-{category_index:02d}-{offset + 1:05d}'
            type_low, type_high = TYPE_PRICE.get(product_type, (299, 14999))
            price_rng = random.Random(product_id * 104729 + category_index)
            spread = price_rng.random() ** 1.7
            price = type_low + (type_high - type_low) * spread
            price = round(price * EDITION_MULTIPLIER.get(edition, 1.0) / 10) * 10 + 9
            rows.append((product_id, sku, title, brand, category, product_type, REVIEWS_PER_PRODUCT, price))
            product_id += 1
    return rows

def _review_rows(products):
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
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    version_row = cur.execute("SELECT value FROM catalog_meta WHERE key='catalog_version'").fetchone()
    count = cur.execute('SELECT COUNT(*) FROM catalog_products').fetchone()[0]
    if version_row and version_row[0] == CATALOG_VERSION and (count >= TOTAL_PRODUCTS_TARGET):
        return
    
    cur.execute('BEGIN TRANSACTION;')
    cur.execute('DELETE FROM catalog_reviews;')
    cur.execute('DELETE FROM catalog_products;')
    
    products = _product_rows(TOTAL_PRODUCTS_TARGET)
    cur.executemany('INSERT INTO catalog_products (id, sku, title, brand, category, product_type, review_count, price) VALUES (?,?,?,?,?,?,?,?)', products)
    
    reviews = _review_rows(products)
    cur.executemany('INSERT INTO catalog_reviews (id, product_id, reviewer, rating, review_text, review_date, seed_sentiment) VALUES (?,?,?,?,?,?,?)', reviews)
    
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
        sql = f"SELECT id, sku, title, brand, category, product_type, review_count, price FROM catalog_products WHERE {' AND '.join(where)} ORDER BY CASE WHEN LOWER(title) LIKE ? THEN 0 WHEN LOWER(brand) LIKE ? THEN 1 ELSE 2 END, title LIMIT ? OFFSET ?"
        params.extend([prefix, prefix, limit, offset])
    else:
        params = []
        where = ''
        if category != 'All categories':
            where = 'WHERE category=?'
            params.append(category)
        sql = f'SELECT id, sku, title, brand, category, product_type, review_count, price FROM catalog_products {where} ORDER BY id LIMIT ? OFFSET ?'
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
    rows = conn.execute('SELECT reviewer AS author, rating, review_text AS text, review_date AS date, seed_sentiment FROM catalog_reviews WHERE product_id=? ORDER BY id', (product_id,)).fetchall()
    conn.close()
    return [dict(zip(('author', 'rating', 'text', 'date', 'seed_sentiment'), row)) for row in rows]

# ==========================================================================
# NLP ENGINE
# ==========================================================================
ASPECT_KEYWORDS = {'Quality': ['quality', 'premium', 'material', 'materials', 'build', 'sturdy', 'finish', 'finishing', 'fabric', 'genuine', 'original', 'duplicate', 'flaw', 'flaws', 'scratch', 'scratches', 'plasticky', 'well-made'], 'Price': ['price', 'cost', 'costs', 'expensive', 'cheap', 'cheaper', 'value', 'money', 'affordable', 'overpriced', 'worth', 'budget', 'discount', 'offer', 'mrp', 'rupee', 'rupees', 'pricey', 'deal', 'pricing'], 'Delivery': ['delivery', 'shipping', 'arrived', 'arrive', 'courier', 'dispatch', 'dispatched', 'shipment', 'delivered', 'delay', 'delayed', 'tracking', 'shipped', 'rescheduled'], 'Packaging': ['pack', 'packed', 'packing', 'packaging', 'package', 'box', 'sealed', 'seal', 'wrap', 'wrapping', 'unboxing', 'cushion', 'bubble'], 'Service': ['service', 'support', 'return', 'refund', 'replacement', 'warranty', 'seller', 'staff', 'helpful', 'response', 'responsive', 'unresponsive', 'claim', 'help', 'helpline', 'customer care'], 'Features': ['feature', 'features', 'battery', 'camera', 'display', 'screen', 'performance', 'sound', 'processor', 'ram', 'storage', 'charging', 'speaker', 'bluetooth', 'picture', 'photo', 'interface', 'connectivity', 'lag', 'heats', 'heating', 'mic', 'app', 'settings'], 'Durability': ['durable', 'durability', 'last', 'lasts', 'lasting', 'broke', 'broken', 'damaged', 'damage', 'crack', 'cracked', 'fragile', 'wear', 'drop', 'stopped', 'survived', 'strong', 'years', 'months', 'stopped working'], 'Design': ['design', 'look', 'looks', 'style', 'colour', 'color', 'beautiful', 'elegant', 'sleek', 'modern', 'attractive', 'appearance', 'comfort', 'comfortable', 'uncomfortable', 'fit', 'fits', 'size', 'sizing', 'bulky', 'dull', 'outdated', 'compliment', 'compliments', 'finish']}
POS_WORDS = {'good', 'great', 'excellent', 'amazing', 'awesome', 'fantastic', 'superb', 'outstanding', 'wonderful', 'brilliant', 'perfect', 'love', 'loved', 'loves', 'best', 'better', 'nice', 'premium', 'beautiful', 'elegant', 'sleek', 'smooth', 'smoothly', 'fast', 'quick', 'quickly', 'impressive', 'impressed', 'happy', 'satisfied', 'satisfying', 'satisfactory', 'recommend', 'recommended', 'worth', 'affordable', 'reasonable', 'unbeatable', 'sturdy', 'strong', 'durable', 'genuine', 'original', 'flawless', 'helpful', 'polite', 'seamless', 'intuitive', 'clear', 'crisp', 'sharp', 'comfortable', 'attractive', 'modern', 'compliment', 'compliments', 'exceeded', 'exceeds', 'incredible', 'phenomenal', 'stunning', 'gorgeous', 'classy', 'neat', 'reliable', 'trustworthy', 'authentic', 'responsive', 'easily', 'easy', 'efficient', 'powerful', 'lasting', 'bright', 'vivid', 'loud', 'balanced', 'approved', 'convenient', 'safe', 'protected', 'cushioned', 'prompt', 'early', 'superior', 'value', 'loving', 'favourite', 'favorite', 'glad', 'pleased', 'pleasantly', 'surprised', 'conveniently', 'handy', 'practical'}
NEG_WORDS = {'bad', 'poor', 'terrible', 'awful', 'horrible', 'worst', 'worse', 'disappointing', 'disappointed', 'disappointment', 'hate', 'hated', 'regret', 'frustrating', 'frustrated', 'annoying', 'useless', 'waste', 'pathetic', 'nightmare', 'cheap', 'duplicate', 'fake', 'flaw', 'flaws', 'scratch', 'scratches', 'torn', 'broken', 'broke', 'crack', 'cracked', 'damaged', 'damage', 'fragile', 'stopped', 'lag', 'lags', 'lagging', 'heats', 'heating', 'drains', 'drain', 'slow', 'late', 'delay', 'delayed', 'rude', 'rudely', 'unresponsive', 'unhelpful', 'rejected', 'cheated', 'expensive', 'overpriced', 'costly', 'gimmicky', 'gimmick', 'tinny', 'dropping', 'drops', 'dull', 'outdated', 'bulky', 'uncomfortable', 'tight', 'risky', 'rattling', 'rescheduled', 'denied', 'plasticky', 'noisy', 'blurry', 'dark', 'dim', 'weak', 'inconsistent', 'defective', 'faulty', 'junk', 'scam', 'leaking', 'loose', 'mismatched', 'incomplete'}
NEU_WORDS = {'fine', 'okay', 'ok', 'average', 'acceptable', 'expected', 'usable', 'decent', 'adequate', 'standard', 'ordinary', 'fair', 'moderate', 'passable', 'works', 'working'}
INTENSIFIERS = {'very', 'really', 'extremely', 'super', 'highly', 'totally', 'truly', 'absolutely', 'quite', 'so', 'too', 'incredibly', 'amazingly', 'deeply', 'completely', 'utterly'}
HEDGES = {'little', 'slightly', 'somewhat', 'bit', 'fairly', 'rather', 'relatively', 'mildly'}
NEGATIONS = {'not', 'no', 'never', 'neither', 'nor', 'none', 'hardly', 'barely', 'without', 'isnt', "isn't", 'wasnt', "wasn't", 'dont', "don't", 'doesnt', "doesn't", 'cant', "can't", 'wont', "won't", 'couldnt', "couldn't", 'didnt', "didn't"}

_PRICE_CTX = re.compile('\\b(price|prices|priced|pricing|cost|costs|value|money|rupee|rupees|mrp|budget|deal|offer|discount|expensive|cheap|affordable|worth|sale)\\b', re.I)
_QUALITY_CTX = re.compile('\\b(quality|grade|build|material|materials|finish|finishing|construction|made)\\b', re.I)
_FIT_CTX = re.compile('\\b(fit|fits|fitting|size|sizing|comfort|comfortable|wear)\\b', re.I)
NEG_PHRASES = [(re.compile('\\bexpect(?:ed|ing)? (?:a bit |a little )?better\\b', re.I), 'disappointing'), (re.compile('\\bexpect(?:ed|ing)? more\\b', re.I), 'disappointing'), (re.compile('\\bcould be (?:much )?better\\b', re.I), 'disappointing'), (re.compile('\\bcould be improved\\b', re.I), 'disappointing'), (re.compile('\\bnot (?:really )?worth\\b', re.I), 'overpriced'), (re.compile('\\bwaste of money\\b', re.I), 'overpriced'), (re.compile('\\bno complaints?\\b', re.I), 'perfect')]

def _apply_phrases(sentence: str) -> str:
    for pattern, replacement in NEG_PHRASES:
        sentence = pattern.sub(replacement, sentence)
    return sentence

def _contextual_polarity(word: str, sentence: str):
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

def analyze_reviews(reviews):
    aspects = list(ASPECT_KEYWORDS.keys())
    aspect_data = {a: {'positive': 0, 'neutral': 0, 'negative': 0, 'examples': []} for a in aspects}
    overall = {'positive': 0, 'neutral': 0, 'negative': 0}
    rows = []
    for rev in reviews:
        text = rev['text']
        sentences = [s.strip() for s in re.split('[.!?]+', text) if s.strip()]
        found_aspects = set()
        pos = neu = neg = 0
        for sent in sentences:
            score, hits = score_sentence(sent)
            if not hits:
                continue
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

# ==========================================================================
# CHARTS & STYLES
# ==========================================================================
def style_fig(fig, height=380):
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
    if rating is None:
        return ''
    try:
        full = int(round(float(rating)))
    except (TypeError, ValueError):
        return ''
    full = max(0, min(5, full))
    return '★' * full + '☆' * (5 - full)

def money(amount) -> str:
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return '—'
    if amount <= 0:
        return '—'
    return f'₹{amount:,.0f}'

def header(title, subtitle):
    st.markdown(f'<div class="gradient-title">{title}</div><div class="subtitle">{subtitle}</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)

GLASS_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
.stApp {
  font-family: 'Poppins', sans-serif;
  background:
    radial-gradient(1000px 620px at 8% 8%,   rgba(199,233,255,0.95), transparent 60%),
    radial-gradient(950px 720px at 92% 12%,  rgba(255,209,220,0.95), transparent 60%),
    radial-gradient(820px 620px at 88% 92%,  rgba(255,178,200,0.65), transparent 60%),
    radial-gradient(920px 720px at 8% 95%,   rgba(255,243,196,0.95), transparent 60%),
    radial-gradient(760px 560px at 50% 55%,  rgba(230,222,255,0.85), transparent 65%),
    linear-gradient(135deg, #eef4ff 0%, #fdf1f5 60%, #ffeef3 100%);
  background-attachment: fixed;
  color: #2b2350;
}
[data-testid="stSidebar"] {
  background: rgba(255,255,255,0.45) !important;
  backdrop-filter: blur(22px);
  -webkit-backdrop-filter: blur(22px);
  border-right: 1px solid rgba(255,255,255,0.65);
}
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
[data-testid="stHeader"] { background: rgba(255,255,255,0.0) !important; }
footer { visibility: hidden; }
.gradient-title {
  font-weight: 800; letter-spacing: -0.5px; line-height: 1.1; font-size: 2.7rem;
  background: linear-gradient(90deg, #5b6abf 0%, #0891b2 30%, #9333ea 65%, #ec4899 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.subtitle { color: #5b5675; font-size: 1.02rem; margin-top: 6px; }
.glass {
  background: rgba(255,255,255,0.55);
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  border-radius: 20px; border: 1px solid rgba(255,255,255,0.75);
  box-shadow: 0 8px 32px rgba(150,120,255,0.16); padding: 24px;
}
.st-key-auth-card {
  background: rgba(255,255,255,0.55); backdrop-filter: blur(18px);
  border-radius: 20px; border: 1px solid rgba(255,255,255,0.75);
  box-shadow: 0 8px 32px rgba(150,120,255,0.16); padding: 30px 32px;
  max-width: 560px; margin: 4vh auto;
}
.brand-mini { color: #9333ea; font-weight: 700; font-size: 1.05rem; }
.divider-line { height: 3px; border-radius: 99px; margin: 14px 0 20px;
  background: linear-gradient(90deg, rgba(34,211,238,0.7), rgba(232,121,249,0.15), rgba(139,92,246,0.7)); }
.kpi-label { font-size: 0.72rem; letter-spacing: 1.6px; color: #6d6890; font-weight: 600; }
.kpi-value { font-size: 2.6rem; font-weight: 800; color: #7c3aed; line-height: 1.1; }
.kpi-sub { font-size: 0.82rem; color: #6d6890; }
.sent-pos { background: rgba(16,185,129,0.16); color: #047857; padding: 2px 12px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; }
.sent-neg { background: rgba(244,63,94,0.12); color: #be123c; padding: 2px 12px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; }
.sent-neu { background: rgba(139,92,246,0.12); color: #6d28d9; padding: 2px 12px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; }
.avatar { width: 78px; height: 78px; border-radius: 50%; object-fit: cover; border: 3px solid rgba(255,255,255,0.9); }
.avatar-sm { width: 52px; height: 52px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(255,255,255,0.9); }
.avatar-fallback { display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 800; background: linear-gradient(135deg, #8b5cf6, #ec4899); }
.stButton > button {
  background: linear-gradient(135deg, #a855f7 0%, #ec4899 100%) !important;
  color: #fff !important; border: none !important; border-radius: 999px !important;
  padding: 0.55rem 1.9rem !important; font-weight: 600 !important;
}
.or-sep { display:flex; align-items:center; gap:12px; margin:14px 0 6px; color:#8b84ad; font-size:.76rem; font-weight:600; }
.or-sep::before, .or-sep::after { content:""; height:1px; flex:1; background:rgba(148,163,184,.45); }
.suggest-meta { color:#6d6890; font-size:.72rem; text-align:center; margin:-6px 0 12px; }
.catalog-hero { padding:22px; border-radius:20px; background:linear-gradient(125deg,rgba(124,58,237,.12),rgba(34,211,238,.12),rgba(236,72,153,.10)); border:1px solid rgba(255,255,255,.78); }
.review-feed { padding:14px 16px; margin:9px 0; border-radius:15px; background:rgba(255,255,255,.45); border:1px solid rgba(255,255,255,.7); }
.review-feed-text { color:#40385f; line-height:1.55; margin-top:7px; }
</style>
"""

def apply_custom_css():
    st.markdown(GLASS_CSS, unsafe_allow_html=True)

# ==========================================================================
# VIEWS: LOGIN
# ==========================================================================
def auth_page():
    if st.session_state.pop('go_google', False):
        redirect_to_google(build_auth_url())
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        card = st.container(key='auth-card', border=False)
        with card:
            st.markdown(f"""
            <div class="auth-head">
              <div class="brand-mini">🪄 {APP_NAME}</div>
              <div class="gradient-title" style="font-size:2rem;">Know what customers really feel</div>
              <div class="subtitle">Pick a product, review what people said, and see which parts they loved or hated.</div>
              <div class="divider-line"></div>
            </div>
            """, unsafe_allow_html=True)
            err = st.session_state.pop('oauth_error', None)
            if err:
                st.error(f'🔐 {err}')

            if is_google_configured():
                if st.button('🌐  Continue with Google', type='primary', width='stretch', key='google_signin'):
                    st.session_state['go_google'] = True
                    st.rerun()
            else:
                st.button('🌐  Continue with Google', type='primary', width='stretch', disabled=True)
                st.warning('**Google login is off** — please add credentials in secrets or log in using email.')

            st.markdown("<div class='or-sep'><span>or use your email</span></div>", unsafe_allow_html=True)
            st.caption(f'build {BUILD}')
            mode = st.radio('Account', ['Log in', 'Create account'], horizontal=True, label_visibility='collapsed')
            if mode == 'Log in':
                with st.form("login_form"):
                    login_input = st.text_input('Username or Gmail', placeholder='you@gmail.com')
                    pwd = st.text_input('Password', type='password', placeholder='••••••••')
                    submitted = st.form_submit_button('Log in', width='stretch')
                    
                    if submitted:
                        if not login_input or not pwd:
                            st.error('Enter your username/Gmail and password.')
                        else:
                            user = get_user_by_login(login_input)
                            if user and verify_password(pwd, user['password_hash'], user['salt']):
                                do_login(user, via='email')
                            else:
                                st.error("That login didn't match. Check spelling or create an account.")
            else:
                username = st.text_input('Username', placeholder='sneha_21', key='signup_username_field')
                gmail = st.text_input('Gmail', placeholder='you@gmail.com', key='signup_gmail_field')
                pwd = st.text_input('Password', type='password', placeholder='At least 6 characters', key='signup_pwd_field')
                pwd2 = st.text_input('Confirm password', type='password', placeholder='Repeat password', key='signup_pwd2_field')
                if st.button('Create account', type='secondary', width='stretch'):
                    if not valid_username(username or ''):
                        st.error('Username must be 3–20 characters.')
                    elif not valid_gmail(gmail or ''):
                        st.error('Please use a valid **@gmail.com** address.')
                    elif (issues := password_issues(pwd or '')):
                        st.error('Password needs ' + ', '.join(issues) + '.')
                    elif pwd != pwd2:
                        st.error("Passwords don't match.")
                    elif get_user_by_login(username):
                        st.error('Username already taken.')
                    elif get_user_by_login(gmail):
                        st.error('Gmail already registered.')
                    else:
                        user = create_user(username, gmail, pwd)
                        log_event(user, 'signup', f'New account created ({username})')
                        st.success('Account created! Logging you in… 🎉')
                        do_login(user, via='email')

# ==========================================================================
# VIEWS: ANALYSIS
# ==========================================================================
def _suggestions(query, limit=6):
    q = query.lower().strip()
    candidates = search_catalog(query, 'All categories', limit=120)
    def score(p):
        title = p['title'].lower()
        brand = p['brand'].lower()
        ptype = p['product_type'].lower()
        if title.startswith(q): return 0
        if ptype.startswith(q): return 1
        if brand.startswith(q): return 2
        return 3
    used_types, out = (set(), [])
    for product in sorted(candidates, key=lambda p: (score(p), p['title'])):
        key = product['product_type'].lower()
        if key in used_types: continue
        used_types.add(key)
        out.append(product)
        if len(out) >= limit: break
    return out

def _analyse_and_store(user, product, reviews):
    cached = st.session_state.get('catalog_analysis', {})
    if cached.get('product_id') == product['id']:
        return cached['result']
    result = analyze_reviews(reviews)
    st.session_state['catalog_analysis'] = {'product_id': product['id'], 'result': result}
    save_analysis(user['id'], f"catalog:{product['id']}", product['title'], 'Built-in Product Catalog', result['total'], result['overall']['positive'], result['overall']['neutral'], result['overall']['negative'], result['verdict'])
    log_event(user, 'catalog_analyse', f"Analysed {product['sku']} · {product['title']} → {result['verdict']}")
    return result

def _search_and_pick(user):
    c_summary = catalog_summary()
    cats = ['All categories'] + catalog_categories()
    
    col_cat, col_q = st.columns([1, 2.5])
    with col_cat:
        selected_cat = st.selectbox('Category Filter', cats, key='cat_filter')
    with col_q:
        query = st.text_input('Search a product', placeholder='Start typing… e.g. headphones, olive oil, drill kit, dog food', key='catalog_query')
        
    selected_id = st.session_state.get('catalog_product_id')
    typed = (query or '').strip()
    
    if not typed:
        if not selected_id:
            picks = search_catalog('', selected_cat, limit=12, offset=0)
            st.caption(f"Catalog database loaded with **{c_summary['products']:,}** products across **{c_summary['categories']}** categories.")
            _pick_grid(user, picks)
        return
        
    suggestions = _suggestions(typed)
    if not suggestions:
        st.info(f'No product matches “{typed}”.')
        return
    st.caption(f"**{catalog_match_count(typed, selected_cat):,}** products match “{typed}” — pick one:")
    _pick_grid(user, suggestions, compact=True)
    if selected_id:
        _show_product(user, selected_id)

def _pick_grid(user, products, compact=False):
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
    product = get_catalog_product(product_id)
    if not product:
        st.session_state.pop('catalog_product_id', None)
        return
    reviews = get_catalog_reviews(product_id)
    pos_n = sum((1 for r in reviews if r.get('seed_sentiment') == 'positive'))
    neu_n = sum((1 for r in reviews if r.get('seed_sentiment') == 'neutral'))
    neg_n = sum((1 for r in reviews if r.get('seed_sentiment') == 'negative'))
    st.markdown('<div class="divider-line"></div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="catalog-hero">
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
          <div class="gradient-title" style="font-size:1.55rem;">{html.escape(product['title'])}</div>
          <div class="subtitle" style="margin-top:4px;"><b>{html.escape(product['brand'])}</b> • {html.escape(product['product_type'])} • {money(product.get('price'))}</div>
        </div>
      </div>
      <div style="display:flex; gap:8px; margin-top:12px; flex-wrap:wrap;">
        <span class="sent-pos">{pos_n} positive</span>
        <span class="sent-neu">{neu_n} neutral</span>
        <span class="sent-neg">{neg_n} negative</span>
      </div>
    </div>""", unsafe_allow_html=True)
    result = _analyse_and_store(user, product, reviews)
    _dashboard(result, product)
    _review_feed(reviews, result['rows'])

def _review_feed(reviews, analysed_rows=None):
    st.markdown(f'### 💬 All catalog review samples ({len(reviews)})')
    for index, review in enumerate(reviews):
        sentiment = analysed_rows[index].get('sentiment', 'neutral') if analysed_rows else review.get('seed_sentiment', 'neutral')
        review_text = html.escape(str(review['text']))
        author = html.escape(str(review['author']))
        stars = stars_text(review.get('rating'))
        st.markdown(f'<div class="review-feed"><b>{author}</b> • <span class="stars">{stars}</span> &nbsp;{sent_badge(sentiment)}<div class="review-feed-text">{review_text}</div></div>', unsafe_allow_html=True)

def _dashboard(result, product):
    st.markdown(f'### 📊 Review intelligence — {html.escape(product["title"])}')
    overall = result['overall']
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f'<div class="glass" style="text-align:center;"><div class="kpi-label">REVIEWS</div><div class="kpi-value">{result["total"]}</div></div>', unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="glass" style="text-align:center;"><div class="kpi-label">VERDICT</div><div style="font-size:1.3rem;font-weight:800;color:#6d28d9;">{result["verdict"]}</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="glass" style="text-align:center;"><div class="kpi-label">POS / NEG</div><div style="font-size:1.5rem;font-weight:800;"><span style="color:{POS_COLOR};">{overall["positive"]}</span> / <span style="color:{NEG_COLOR};">{overall["negative"]}</span></div></div>', unsafe_allow_html=True)
    with k4: st.markdown(f'<div class="glass" style="text-align:center;"><div class="kpi-label">POSITIVITY</div><div class="kpi-value">{result["pos_pct"]:.0f}%</div></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(fig_donut(overall), width='stretch')
    with c2: st.plotly_chart(fig_bar(result['aspects']), width='stretch')
    
    c3, c4 = st.columns(2)
    with c3: st.plotly_chart(fig_sunburst(result['aspects'], result['total']), width='stretch')
    with c4: st.plotly_chart(fig_radar(result['aspects']), width='stretch')

def page_analysis():
    user = st.session_state.user
    header('What do you want to check?', 'Type a product, pick it from suggestions, and view instant NLP analysis.')
    if st.session_state.get('catalog_product_id'):
        if st.button('✕ Clear selection', type='secondary'):
            st.session_state.pop('catalog_product_id', None)
            st.session_state.pop('catalog_analysis', None)
            st.rerun()
    _search_and_pick(user)

# ==========================================================================
# VIEWS: PROFILE & HISTORY & ADMIN
# ==========================================================================
def page_profile():
    user = st.session_state.user
    header('My Account', f'Manage account settings for {user["username"]}')
    new_username = st.text_input('Username', value=user['username'], key='profile_username_input')
    if st.button('💾 Save changes', width='stretch'):
        update_user(user['id'], username=new_username.strip())
        st.session_state.user = get_user_by_id(user['id'])
        st.success('Profile updated!')
        st.rerun()

def page_history():
    user = st.session_state.user
    header('My Analysis History', 'Products you have previously analyzed.')
    df = fetch_df('SELECT product_name AS Item, platform AS Catalog, total_reviews AS Reviews, overall AS Verdict, timestamp AS Analysed_At FROM analysis_history WHERE user_id=? ORDER BY id DESC', (user['id'],))
    if df.empty:
        st.info('No analysis history yet.')
        return
    st.dataframe(df, width='stretch', hide_index=True)

def page_admin():
    user = st.session_state.user
    if not user.get('is_admin'):
        st.error('⛔ Admins only.')
        return
    header('Admin Panel', 'User tracking and system logs.')
    users_df = fetch_df('SELECT id,username,email,provider,is_admin,created_at,last_login FROM users ORDER BY id')
    st.dataframe(users_df, width='stretch', hide_index=True)

# View Namespaces
class login:
    auth_page = staticmethod(auth_page)

class analysis:
    page_analysis = staticmethod(page_analysis)

class profile:
    page_profile = staticmethod(page_profile)

class history:
    page_history = staticmethod(page_history)

class admin:
    page_admin = staticmethod(page_admin)

# ==========================================================================
# SIDEBAR & MAIN ENTRY
# ==========================================================================
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
        
        page = st.radio("Navigate", options, label_visibility="collapsed", key='sidebar_navigation_radio')
        if page != st.session_state.get("page"):
            st.session_state.page = page
            log_event(user, "navigate", f"Opened {page}")
            st.rerun()

        st.markdown("---")
        if st.button("🚪 Logout", type="secondary", width="stretch"):
            log_event(user, "logout", "User logged out.")
            for k in ["user", "page", "catalog_product_id", "catalog_analysis"]:
                st.session_state.pop(k, None)
            st.rerun()

def main():
    init_db()

    if "user" not in st.session_state or st.session_state.user is None:
        google_profile, oauth_error = handle_oauth_callback()
        if oauth_error:
            st.session_state["oauth_error"] = oauth_error
        if google_profile:
            login_with_google_profile(google_profile)

    if "user" not in st.session_state or st.session_state.user is None:
        login.auth_page()
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

def login_with_google_profile(profile):
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
    do_login(user, via='google')

st.set_page_config(
    page_title="AspectLens • Sentiment Analytics",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_custom_css()

try:
    main()
except Exception as _boot_exc:
    st.error("**Something went wrong while starting the app.**")
    st.code("".join(traceback.format_exception(type(_boot_exc), _boot_exc, _boot_exc.__traceback__)))
    st.stop()