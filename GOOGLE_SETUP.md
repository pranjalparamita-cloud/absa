# 🔐 Enable the REAL "Continue with Google" (free, ~10 min)

Out of the box the app runs Google login in **demo mode**. Follow these steps
once to switch it to **real mode**: clicking *Continue with Google* will open
Google's own account chooser showing the user's already-logged-in Gmail
accounts, and one click logs them straight into your app.

Everything below is FREE (Google Cloud's free tier covers OAuth logins).

---

## STEP 1 — Create a Google Cloud project

1. Go to **https://console.cloud.google.com** and sign in with your Gmail.
2. Top-left project dropdown → **New Project** → name it e.g. `aspectlens` → **Create**.
3. Make sure the new project is selected (top-left dropdown).

## STEP 2 — Configure the OAuth consent screen

1. Left menu → **APIs & Services** → **OAuth consent screen**.
2. User type → **External** → **Create**.
3. Fill the required fields:
   - **App name:** `AspectLens` (or anything)
   - **User support email:** your Gmail
   - **Developer contact:** your Gmail
4. Click **Save and Continue** through Scopes/Test users — but on the
   **Test users** step click **+ Add Users** and add your Gmail
   (and any friend's Gmail who should be able to log in).
   > ⚠️ While the app is in **Testing** mode, ONLY these test users can log in.
   > That's perfect for a college project. (Publishing is optional.)
5. **Back to Dashboard**. Done.

## STEP 3 — Create the OAuth Client ID + Secret

1. Left menu → **APIs & Services** → **Credentials** → **+ Create Credentials** → **OAuth client ID**.
2. Application type → **Web application**, name it e.g. `aspectlens-web`.
3. Under **Authorized redirect URIs**, click **+ Add URI** and add BOTH:
   - `https://YOUR-APP-NAME.streamlit.app/` ← your deployed app URL (with trailing `/`)
   - `http://localhost:8501/` ← for testing on your own computer
   > ⚠️ Must match **exactly** (https, spelling, trailing `/`), or Google shows `redirect_uri_mismatch`.
4. Click **Create** → a popup shows your **Client ID** and **Client Secret**. Copy both.

## STEP 4 — Add secrets to Streamlit Cloud

1. Open your deployed app → bottom-right **Manage app** (or `⋮` menu) → **Settings** → **Secrets**.
2. Paste this (with YOUR values), then **Save** (the app auto-reboots):

```toml
GOOGLE_CLIENT_ID = "xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-xxxxxxxxxxxxxxxxxxxxxxxx"
GOOGLE_REDIRECT_URI = "https://YOUR-APP-NAME.streamlit.app/"
```

## STEP 5 (local testing) — `.streamlit/secrets.toml`

To test real Google login on your own computer, create the file
`.streamlit/secrets.toml` (copy from `secrets.toml.example`) with:

```toml
GOOGLE_CLIENT_ID = "xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-xxxxxxxxxxxxxxxxxxxxxxxx"
GOOGLE_REDIRECT_URI = "http://localhost:8501/"
```

Then run `streamlit run app.py` and try it.

> 🔒 **NEVER commit `secrets.toml` to GitHub** — it contains your secret.
> It is already listed in `.gitignore`. On Streamlit Cloud, secrets are
> stored securely in the dashboard, not in the repo.

---

## ✅ Test it

1. Open your app → **Continue with Google**.
2. Google's chooser appears with your logged-in Gmail accounts → pick one.
3. You're logged in! First login auto-creates the account (with your Google
   profile photo); next time it's a one-click login.

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| `redirect_uri_mismatch` / Error 400 | The URI in Google Console must EXACTLY equal `GOOGLE_REDIRECT_URI` (check trailing `/`, https) |
| `Access blocked: app has not completed verification` | Normal in Testing mode — the Gmail must be added under **Test users** (Step 2.4) |
| Still seeing demo mode | Secrets missing/typo'd → check Cloud **Settings → Secrets**, then **Reboot app** |
| `Security check failed` | Session expired — just click Continue with Google again |
