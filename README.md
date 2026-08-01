# Google Tasks Dashboard

A Streamlit app to manage **and** analyze your [Google Tasks](https://tasks.google.com):
a Manage tab for CRUD (add / edit / delete across your task lists) and an Analytics tab
with completion velocity, streaks, backlog health, and day/time patterns.

Auth is **per-user**: everyone signs in with their own Google account, and credentials +
task data live only in that person's browser session. So the app is private for you today
and safe to publish for others later — nobody can ever see or touch anyone else's tasks.

---

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI (Manage + Analytics tabs) |
| `auth.py` | Per-user Google OAuth (web redirect flow) |
| `tasks_api.py` | Google Tasks API wrapper (fetch / add / update / delete) |
| `transform.py` | Adds derived analytics columns to the task data |
| `analytics.py` | Plotly chart functions + summary stats |
| `.streamlit/config.toml` | App config/theme |
| `.streamlit/secrets.toml.example` | Template for OAuth secrets |
| `detailed_analysis/export_to_csv.py` | Optional local CLI to export tasks to CSV (not part of the web app) |

---

## 1. Google Cloud setup (one time)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create (or pick) a project.
2. **APIs & Services → Library →** enable the **Google Tasks API**.
3. **APIs & Services → OAuth consent screen:**
   - User type **External**.
   - Add the scope `https://www.googleapis.com/auth/tasks`.
   - Under **Test users**, add your own Google address (and anyone else you want to let in
     while the app is unpublished).
4. **APIs & Services → Credentials → Create credentials → OAuth client ID:**
   - Application type must be **Web application** (a *Desktop* client will **not** work when hosted).
   - **Authorized redirect URIs** → add both:
     - `http://localhost:8501` (local development)
     - `https://YOUR-APP-NAME.streamlit.app` (added after you deploy — step 3)
   - Copy the **Client ID** and **Client secret**.

---

## 2. Run locally

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` from the example and fill in your client ID/secret:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

```toml
[google_oauth]
client_id = "....apps.googleusercontent.com"
client_secret = "...."
redirect_uri = "http://localhost:8501"
```

Then:

```bash
streamlit run app.py
```

Open http://localhost:8501, click **Sign in with Google**, grant access, and your tasks load.

---

## 3. Deploy to Streamlit Community Cloud (free)

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io), **New app**, pick this repo and `app.py`.
3. Deploy once to get your app URL, e.g. `https://your-app-name.streamlit.app`.
4. In **App → Settings → Secrets**, paste your `[google_oauth]` block, but set:
   ```toml
   redirect_uri = "https://your-app-name.streamlit.app"
   ```
5. Back in Google Cloud → your OAuth client → add that same URL to **Authorized redirect URIs**.
6. Reboot the app and sign in on the live URL.

> Secrets are never committed — `.streamlit/secrets.toml`, `client_secret.json`, and
> `token.pkl` are gitignored. Deployment secrets live only in the Streamlit Cloud dashboard.

---

## 4. Making it public later

While the OAuth consent screen is in **Testing**, only the Google accounts you added as
**test users** can sign in. To open it to everyone:

- In **OAuth consent screen**, click **Publish app**.
- `https://www.googleapis.com/auth/tasks` is a **sensitive scope**, so Google may require
  **app verification** (privacy policy URL, homepage, and a review) before unrestricted public
  use. Until verification completes, the app still works for you and any added test users.

No code changes are needed to go public — the per-user auth model already isolates every
visitor's account.

---

## Notes

- Google Tasks has no "created" timestamp, so analytics **age** is based on each task's
  last-modified time (this is noted in the app footer).
- Task data is cached per browser session; use **Refresh Tasks** in the sidebar to re-fetch.
