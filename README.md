========================================================
 AspectLens — FINAL PACKAGE
========================================================

This zip contains SIX files. That is the whole project.

    app.py                  the entire application (one file)
    requirements.txt        the Python packages it needs
    README.md               this file
    GOOGLE_SETUP.md         optional: real Google login
    .streamlit/config.toml  theme
    .streamlit/secrets.toml.example   template for Google keys
    .gitignore

There is no views/ folder, no modules to import, nothing to assemble.
The build is stamped "v6 · 09 Nov 2026".


--------------------------------------------------------
 STEP 1 — PUT THESE FILES ON GITHUB
--------------------------------------------------------
Delete everything currently in your GitHub repo, then upload these.

Easiest way (no terminal):

 1. Unzip this file.
 2. Go to github.com/pranjalparamita-cloud/absa
 3. In the file list, select the old files and delete them
    (or just overwrite app.py and requirements.txt — those are the
     only two that matter).
 4. "Add file" -> "Upload files" -> drag in app.py and requirements.txt
 5. Commit.

IMPORTANT: app.py must be at the TOP LEVEL of the repo, not inside a folder.


--------------------------------------------------------
 STEP 2 — TELL STREAMLIT WHICH FILE TO RUN
--------------------------------------------------------
share.streamlit.io -> your app -> the "..." menu -> Settings
   Main file path:  app.py
   Save.

Then "Reboot app".


--------------------------------------------------------
 STEP 3 — CHECK IT WORKED
--------------------------------------------------------
Open the app. Under the login card you must see:

    build v6 · 09 Nov 2026

  Stamp visible  -> correct version is live.
  No stamp       -> Step 1 did not reach GitHub. Repeat it.


--------------------------------------------------------
 STEP 4 — LOG IN
--------------------------------------------------------
Without any Google setup, use email login:

    demo@gmail.com   / Demo@123      normal user
    admin@gmail.com  / Admin@123     admin (extra Admin Panel)

Or click "Create account": any username, a @gmail.com address,
and a password of 6+ characters containing a number.

Everything works this way: search a product, pick it, the NLP
analysis runs automatically, charts and reviews appear below.


--------------------------------------------------------
 STEP 5 — GOOGLE LOGIN (optional)
--------------------------------------------------------
Only if you want "Continue with Google". Full details in
GOOGLE_SETUP.md, but here is the short version:

 A. In Streamlit: Settings -> Secrets, paste this with YOUR values:

    [auth]
    client_id = "YOUR-ID.apps.googleusercontent.com"
    client_secret = "GOCSPX-YOUR-SECRET"
    server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
    redirect_uri = "https://nhuepfaebgtaqhk7w86htv.streamlit.app/oauth2callback"

 B. In Google Cloud -> APIs & Services -> Credentials ->
    your OAuth client -> Authorized redirect URIs, add:

    https://nhuepfaebgtaqhk7w86htv.streamlit.app/oauth2callback

    (note: /oauth2callback on the end — this is what changed)

    Then click SAVE at the bottom of the page.

 C. In Google Cloud -> Google Auth Platform -> Audience:
    add your Gmail under "Test users", or click "Publish app".

Then reboot and click "Continue with Google".

Without step C, Google blocks every account that is not a
test user. No code can bypass that — it is Google's rule.


--------------------------------------------------------
 IF SOMETHING LOOKS WRONG
--------------------------------------------------------
Old page content still showing?
    Ctrl+Shift+R to force-reload, then Settings -> Reboot app.

"ModuleNotFoundError: No module named 'views'"
    You are still running an old app.py. The correct one is
    119 KB and contains everything. Re-upload it.

"No module named 'streamlit'"
    requirements.txt is missing or not at the repo root.

Google button greyed out / "Google login is off"
    No [auth] block in Secrets, or a typo in a key name.

"Authentication requires Authlib>=1.3.2"
    requirements.txt is an old copy. It must contain:
        authlib>=1.3.2

"redirect_uri_mismatch"
    The URI in Google Cloud does not exactly match redirect_uri
    in Secrets. Check https, spelling, and /oauth2callback.

"Access blocked: app has not completed verification"
    Add your Gmail in Audience -> Test users, or Publish app.

Charts show but one panel is empty
    Fixed in this build. If you still see it, you are on old code.


--------------------------------------------------------
 WHAT IS IN THIS BUILD
--------------------------------------------------------
  - Search -> live suggestions -> pick product -> automatic
    NLP analysis -> charts -> reviews below.
  - 5,000 product catalog, 50,000 generated demo reviews.
  - Email/password accounts, profile, history, admin panel.
  - Google login via Streamlit's own st.login() (server-side
    redirect, so Google's screen can never be frame-blocked).
  - Sunburst chart fixed (it used to render blank).
  - Empty white panels on My Account / Admin removed.
  - Database falls back to a temp path on read-only hosts.
  - Requirements range-pinned so the install never fails on
    whichever Python version Streamlit Cloud picks.

Tested: boot, login, search, analysis (6 charts + aspect table
+ review feed), profile, history, admin, logout — 23/23 checks
passing, re-run from a clean extraction of this zip.
========================================================
