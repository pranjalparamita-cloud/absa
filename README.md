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
| **🛍️ Products** | One search box, one grid. Search a 5,000-item catalog by product, brand or category — no filters to configure |
| **💬 Name + review type** | The product page shows the product name and what its 10 reviews are made of — how many positive / neutral / negative, and the average stars. No image gallery, no clutter |
| **📊 Review intelligence** | Aspect-sentiment dashboard: Sunburst, Bar, Radar, Donut, timeline, rating chart, KPI cards and aspect table |
| **🔐 Accounts** | Continue with Google (real OAuth), or email + password. Gmail-only. Change your display name and password in **My Account** |
| **👤 My Account** | Name, password, and your past analyses with CSV download |
| **🛡️ Admin Panel** | User activity tracking, session information and exports |

### NLP engine — offline and free

- Eight aspects: **Quality, Price, Delivery, Packaging, Service, Features, Durability, Design**
- Negation-aware scoring (`"not good"` flips), intensifiers (`"very good"` boosts), hedges (`"a little high"` dampens) and contrast clauses (`"fine, although the price is high"` scores the price clause)
- Ambiguous words are context-checked: `high` only counts as negative when the sentence is about price, `low` counts as *positive* about price and negative about quality, `small` only matters for fit/size
- Sentences with no opinion word at all are skipped, so descriptive text can never vote
- 100% agreement between the seeded review label and the NLP label across the whole catalog

---

## 🚀 How to use it

1. Log in — **Continue with Google**, or email and password.
2. Type a product in the search box (`headphones`, `samsung`, `air fryer`).
3. Suggestions appear as you type — **click the one you mean**.
4. The analysis runs immediately: verdict, the 8 aspects, the charts.
5. Its reviews are listed **underneath** the analysis.

There is no "Analyse" button and no filters to set. One search, one click.

## 💻 Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Google login is optional. With no secrets configured the app says so on the login
screen and email login works normally. To enable it, copy
`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the three
values — see `GOOGLE_SETUP.md`.

On first launch, SQLite automatically creates and seeds the built-in catalog:

- **5,000** product-style listings
- **50,000** mixed review samples
- **10** shopping categories
- realistic per-product-type pricing (₹99 pens to ₹3.7 L gaming laptops)

## 🚀 Deploy on Streamlit Community Cloud

1. Push this folder to a public GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io/) → **New app**.
3. Select the repository and `main` branch; set the main file path to `app.py`.
4. Click **Deploy**.

> `absa.db` is generated automatically. Streamlit Cloud may recreate its local
> database when an app is restarted, so the catalog is designed to seed itself
> safely whenever needed.

### Demo accounts

| Role | Email | Password |
|---|---|---|
| User | `demo@gmail.com` | `Demo@123` |
| Admin | `admin@gmail.com` | `Admin@123` |

## 📁 Project structure

```text
aspect-sentiment-app/
├── app.py                  # app setup, sidebar and routing
├── catalog.py              # 5,000-product / 50,000-review generated demo catalog + pricing
├── database.py             # SQLite schema, user data and catalog seeding
├── nlp_engine.py           # aspect-based sentiment engine + 12-month price history
├── charts.py               # Plotly dashboard figures (incl. price history)
├── ui_helpers.py           # cards, avatar, review, badge and price helpers
├── styles.py               # glassmorphism UI and sidebar fix
├── legacy/                 # superseded upload-first code (not imported; safe to delete)
├── views/
│   ├── analysis.py         # one-box product search + review-analysis workspace
│   ├── login.py            # login / sign-up / Google entry point
│   ├── profile.py          # My Account: name + password
│   ├── history.py          # saved analyses
│   └── admin.py            # activity tracking
├── requirements.txt
└── .streamlit/config.toml
```

## 🛡️ Notes

- Passwords are salted and hashed using PBKDF2-HMAC-SHA256.
- Prices are generated demo values matched to each product type, not live listings.
- The catalog's generated content is for product-analytics demonstration only.
- For production, replace `catalog.py` seed data with appropriately licensed
  product and customer-review data, and retain source/consent attribution.
