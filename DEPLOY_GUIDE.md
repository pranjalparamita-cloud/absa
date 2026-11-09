# 🚀 Push to GitHub & Deploy on Streamlit — Step-by-Step Guide

Follow these 3 parts in order. Total time: ~10 minutes. Everything is FREE.

---

## PART 1 — Put the code on GitHub (pick ONE method)

### ✅ Method A: GitHub website upload (easiest, no commands)

1. Go to **https://github.com** and sign up / log in (free).
2. Click the **+** (top-right) → **New repository**.
3. Name it `aspect-sentiment-app`, keep it **Public**, tick **Add a README file** is OFF
   (we already have files), click **Create repository**.
4. On the repo page, click **uploading an existing file** (or `Add file` → `Upload files`).
5. Drag & drop **EVERYTHING** from the `aspect-sentiment-app` folder:
   all `.py` files (`app.py`, `config.py`, `database.py`, `auth.py`,
   `google_auth.py`, `catalog.py`, `nlp_engine.py`, `charts.py`,
   `styles.py`, `ui_helpers.py`), the `views` folder,
   `GOOGLE_SETUP.md`, `requirements.txt`, `README.md`, `.gitignore`,
   plus the `.streamlit` folder (`config.toml` + `secrets.toml.example`).
   > ⚠️ Upload so that `app.py` is at the **top level** of the repo,
   > NOT inside another folder. Keep the `views` folder as a folder.
   > ⚠️ NEVER upload a real `secrets.toml` — secrets go in the
   > Streamlit Cloud dashboard (Part 4 of GOOGLE_SETUP.md), not in GitHub.
6. Click **Commit changes**. Done — your code is on GitHub! 🎉

### 🖥️ Method B: Git commands (if you have Git installed)

```bash
# 1. Unzip the project, open a terminal INSIDE aspect-sentiment-app folder
git init
git add .
git commit -m "AspectLens sentiment app"

# 2. Create an empty repo named aspect-sentiment-app on github.com, then:
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/aspect-sentiment-app.git
git push -u origin main
```

---

## PART 2 — Deploy on Streamlit Cloud (free hosting)

1. Go to **https://share.streamlit.io** (Streamlit Community Cloud).
2. Click **Sign in with GitHub** and authorize Streamlit.
3. Click **Create app** (or `New app`).
4. Fill in:
   - **Repository:** `YOUR-USERNAME/aspect-sentiment-app`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** pick any name, e.g. `aspectlens-sentiment`
5. Click **Deploy!** ⏳ Wait 2–5 minutes while it installs packages.
6. Your app is LIVE at `https://aspectlens-sentiment.streamlit.app` 🎉

---

## PART 3 — Test your live app

1. Open your app URL.
2. Log in with the demo accounts:
   - User → `demo@gmail.com` / `Demo@123`
   - Admin → `admin@gmail.com` / `Admin@123`
3. Open **🛍️ Product Explorer**, type a product/brand/category/SKU (try `samsung`, `brake pad` or `air fryer`), choose an autocomplete suggestion, then click **Analyse all product reviews** to see the dashboard. The app seeds its 5,000-item built-in demo catalog automatically on first launch.
4. As admin, open **🛡️ Admin Panel** to see user tracking.

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` on deploy | Check `requirements.txt` is in the repo top level; then `Manage app` → `Reboot app` |
| Google login shows demo mode | Normal until you configure secrets — follow `GOOGLE_SETUP.md` (free, ~10 min) |
| `redirect_uri_mismatch` | Secrets' `GOOGLE_REDIRECT_URI` must EXACTLY match the URI in Google Console |
| App shows old code after you edit GitHub | Streamlit auto-redeploys in ~1 min; or `Manage app` → `Reboot app` |
| `app.py` not found | Main file path must be exactly `app.py`, and the file must be at repo top level |
| Database resets sometimes | Normal on free tier — Streamlit wipes the server disk on reboot. Users/data restart fresh with demo accounts |
| Images don't load | Needs internet in the browser (Unsplash CDN). Check your connection |

## 🔄 Updating your app later

Just edit/upload new files to the same GitHub repo — Streamlit will
automatically redeploy within a minute. No need to repeat Part 2.
