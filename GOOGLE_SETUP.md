# 🔐 Enable "Continue with Google" — st.login() edition

This build uses **Streamlit's built-in login** (`st.login()`). Streamlit's own
server sends the browser to Google, so the Google screen is always a top-level
page. The old build tried to redirect from HTML, and when that ran inside a
framed context Google answered with:

```
403. That's an error.
We're sorry, but you do not have access to this page.
```

That page can no longer appear in this build.

**Setup time: about 8 minutes. Cost: free.**

---

## The one thing that changed

Streamlit's login always returns to this path:

```
https://YOUR-APP.streamlit.app/oauth2callback
```

That exact URL — with `/oauth2callback` on the end — must be registered in
Google Cloud. It is **not** the bare app URL any more. If you skip this you get
`redirect_uri_mismatch` rather than a 403, which at least names the problem.

---

## STEP 1 — Google Cloud project

1. Open **https://console.cloud.google.com** and sign in.
2. Top-left project dropdown → **New Project** → name it → **Create**.
3. Make sure that project is selected afterwards.

## STEP 2 — OAuth consent screen

**APIs & Services → OAuth consent screen** (newer console: **Google Auth Platform**)

1. User type **External** → **Create**.
2. App name `AspectLens`, user support email and developer contact = your Gmail.
3. **Save and Continue** through Scopes.
4. On **Test users** → **+ ADD USERS** → add **the exact Gmail you will sign in with** → **Save**.

> While the app is in **Testing**, only those emails may sign in. Anyone else
> gets an error even though the code is perfect.
>
> Better: on the **Audience** page click **Publish app**. This app requests only
> `openid`, `email` and `profile` — Google classes those as *non-sensitive*, so
> publishing is instant and needs no review.

## STEP 3 — Create the OAuth client

**APIs & Services → Credentials → + CREATE CREDENTIALS → OAuth client ID**

- Application type: **Web application**
- Name: `aspectlens-web`
- **Authorized redirect URIs** → **+ ADD URI** → paste **exactly**:

```
https://YOUR-APP.streamlit.app/oauth2callback
```

For testing on your own computer add a second URI:

```
http://localhost:8501/oauth2callback
```

- **Create** → copy the **Client ID** and **Client Secret**.

⚠️ Character for character: `https`, the exact subdomain, and `/oauth2callback`
at the end. No trailing slash after `oauth2callback`.

## STEP 4 — Paste the secrets into Streamlit

Your app → **Manage app** → **Settings** → **Secrets** → replace everything with:

```toml
[auth]
client_id = "123456789012-xxxxxxxx.apps.googleusercontent.com"
client_secret = "GOCSPX-xxxxxxxxxxxxxxxx"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
redirect_uri = "https://YOUR-APP.streamlit.app/oauth2callback"
```

**Save.** The app reboots.

Before clicking anything else, open the login page and press
**🔍 Check my Google settings**. It reads back which values the app actually
received, so you can see a typo immediately instead of guessing.

## STEP 5 — Test

Click **Continue with Google** → Google's account chooser appears → pick your
Gmail → you land back in the app, logged in, account created automatically.

`st.login()` needs the **`authlib`** package; it is already listed in
`requirements.txt` of this build.

---

## Why this is more reliable than before

| Old build | This build |
|---|---|
| App built the URL and used `<meta refresh>` | Streamlit server issues a real 302 |
| Google screen could be rendered inside a frame → **403** | Always top-level → cannot be framed |
| Redirect to the bare app URL | Redirect to `/oauth2callback` |
| Secrets named `GOOGLE_CLIENT_ID` etc. | Standard `[auth]` block |
| Failure looked like a bare Google 403 | Failures name themselves: `redirect_uri_mismatch`, `invalid_client` |

---

## Troubleshooting

| What you see | Cause | Fix |
|---|---|---|
| `redirect_uri_mismatch` | URI in Google Cloud ≠ `redirect_uri` in secrets | They must match character for character, including `/oauth2callback` |
| `Access blocked: app has not completed verification` | Your Gmail is not a Test user | Add it under Audience → Test users, or Publish app |
| `invalid_client` / "OAuth client was not found" | Client ID copied wrong, or the client was deleted | Re-copy from Credentials |
| Still the plain email/password card with a grey Google button | No `[auth]` section in secrets | Paste STEP 4 and save |
| `st.login() requires authlib` | Missing dependency | Add `authlib>=1.3.2` to `requirements.txt` |
| Login works, then bounces straight back in after logout | Google session still active | Expected — the app calls `st.logout()`; to switch accounts use an incognito window |

---

## No Google account? Email login works with zero setup

```
demo@gmail.com  / Demo@123      normal user
admin@gmail.com / Admin@123     admin — extra Admin Panel in the sidebar
```

Or click **Create account** on the login card: any username, a `@gmail.com`
address, and a password with 6+ characters including a number.
