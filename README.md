# 💜 AspectLens — Product Review Intelligence

A polished, **100% free** Streamlit application for browsing a built-in product
catalog and running aspect-based sentiment analysis on product review samples.
Built with **Streamlit + SQLite + Plotly + pure-Python NLP** — no paid APIs or
large ML downloads.

> **Data transparency:** The bundled catalog uses recognised retail brands and
> categories, but its 5,000 product-style listings and 50,000 varied review
> samples are generated demonstration data. They are clearly labelled in the
> UI and are **not** represented as verified customer reviews.

---

## ✨ What it includes

| Module | What it does |
|---|---|
| **🛍️ Product Explorer** | Search a 5,000-item catalog by product, brand, category or SKU, with autocomplete-style suggestions |
| **🔎 Category filters** | Browse Electronics, Mobile Accessories, Computers & Gaming, Appliances, Automotive Parts/Accessories, Home, Fashion, Sports and Books & Office |
| **💬 Full review feed** | Every product includes 10 varied positive, neutral and negative review samples, displayed beneath the analysis workspace |
| **📊 Review intelligence** | Aspect-sentiment dashboard: Sunburst, Bar, Radar, Donut, timeline, rating chart, KPI cards and aspect table |
| **🔐 Accounts** | Gmail-only sign-up/login, hashed passwords, profile controls and session tracking |
| **🕘 My History** | Saved analyses with verdicts and CSV download |
| **🛡️ Admin Panel** | User activity tracking, session information and exports |

### NLP engine — offline and free

- Eight aspects: **Quality, Price, Delivery, Packaging, Service, Features, Durability, Design**
- Keyword aspect tagging plus negation/intensifier-aware sentiment scoring
- Every analysis runs on the product's complete 10-review demo feed

---

## 🚀 How to use it

1. Open **🛍️ Product Explorer**.
2. Type a product, brand, category or catalog SKU (for example `samsung`, `brake pad`, `air fryer`, or `AL-05-001`).
3. Select one of the autocomplete suggestions.
4. Read the product's complete mixed review feed.
5. Click **Analyse all product reviews** for the dashboard.

## 💻 Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

On first launch, SQLite automatically creates and seeds the built-in catalog:

- **5,000** product-style listings
- **50,000** mixed review samples
- **10** shopping categories

## 🚀 Deploy on Streamlit Community Cloud

1. Push this folder to a public GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io/) → **New app**.
3. Select the repository and `main` branch; set the main file path to `app.py`.
4. Click **Deploy**.

> `absa.db` is generated automatically. Streamlit Cloud may recreate its local
> database when an app is restarted, so the catalog is designed to seed itself
> safely whenever needed.

## 🔑 Demo accounts

| Role | Email | Password |
|---|---|---|
| User | `demo@gmail.com` | `Demo@123` |
| Admin | `admin@gmail.com` | `Admin@123` |

## 📁 Project structure

```text
aspect-sentiment-app/
├── app.py                  # app setup, sidebar and routing
├── catalog.py              # 5,000-product / 50,000-review generated demo catalog
├── product_visuals.py      # generated product thumbnail + 3-view gallery visuals
├── database.py             # SQLite schema, user data and catalog seeding
├── nlp_engine.py           # aspect-based sentiment engine
├── charts.py               # Plotly dashboard figures
├── ui_helpers.py           # cards, avatar, review and badge helpers
├── styles.py               # glassmorphism UI and sidebar fix
├── views/
│   ├── analysis.py         # Product Explorer and full review-analysis workspace
│   ├── login.py            # login / sign-up / Google entry point
│   ├── profile.py          # profile controls
│   ├── history.py          # saved analyses
│   └── admin.py            # activity tracking
├── requirements.txt
└── .streamlit/config.toml
```

## 🛡️ Notes

- Passwords are salted and hashed using PBKDF2-HMAC-SHA256.
- The catalog's generated content is for product-analytics demonstration only.
- For production, replace `catalog.py` seed data with appropriately licensed
  product and customer-review data, and retain source/consent attribution.
