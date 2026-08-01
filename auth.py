"""
auth.py
Per-user Google OAuth for a hosted Streamlit app.

Each browser session authenticates independently. The user's credentials live only
in st.session_state (never a shared file on the server), so:
  - it is private for you today, and
  - it is safe to make public later (every visitor uses their own Google account,
    nobody can ever touch anyone else's tasks).

Client configuration is read from st.secrets["google_oauth"] — see
.streamlit/secrets.toml.example. This must be a Google OAuth client of type
"Web application" whose authorized redirect URI matches the app's URL.
"""
import json
import os

# Google may echo back a slightly different scope string on token exchange (e.g. adding
# a granted scope), which otherwise makes oauthlib raise "Scope has changed". Relax it.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

import streamlit as st
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

SCOPES = ["https://www.googleapis.com/auth/tasks"]

_SESSION_KEY = "google_credentials"
_VERIFIER_KEY = "google_oauth_code_verifier"


def _client_config() -> dict:
    """Build the google-auth client config dict from Streamlit secrets."""
    cfg = st.secrets["google_oauth"]
    return {
        "web": {
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [cfg["redirect_uri"]],
        }
    }


def _build_flow() -> Flow:
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=st.secrets["google_oauth"]["redirect_uri"],
        autogenerate_code_verifier=True,
    )


def _load_session_credentials():
    """Return Credentials stored in the session, refreshing if expired."""
    raw = st.session_state.get(_SESSION_KEY)
    if not raw:
        return None

    creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            st.session_state[_SESSION_KEY] = creds.to_json()
            return creds
        except Exception:
            # Refresh failed (revoked / expired refresh token) — force re-login.
            st.session_state.pop(_SESSION_KEY, None)
            return None

    return None


def logout():
    """Clear the signed-in user's credentials from this session."""
    st.session_state.pop(_SESSION_KEY, None)


def get_credentials():
    """
    Gate the app behind Google sign-in and return valid Credentials.

    Renders a "Sign in with Google" link and stops the script until the user
    completes the OAuth redirect. Once signed in, subsequent runs return the
    session credentials directly.
    """
    creds = _load_session_credentials()
    if creds:
        return creds

    flow = _build_flow()

    # Step 2: we came back from Google with an authorization code.
    code = st.query_params.get("code")
    if code:
        # Restore the PKCE code_verifier generated when we built the sign-in URL;
        # it must match the code_challenge Google received, or the token exchange
        # fails with "Missing code verifier".
        flow.code_verifier = st.session_state.get(_VERIFIER_KEY)
        try:
            flow.fetch_token(code=code)
        except Exception as e:
            st.error(f"Sign-in failed: {e}")
            st.query_params.clear()
            st.session_state.pop(_VERIFIER_KEY, None)
            st.stop()
        st.session_state[_SESSION_KEY] = flow.credentials.to_json()
        st.session_state.pop(_VERIFIER_KEY, None)
        st.query_params.clear()
        st.rerun()

    # Step 1: no credentials yet — show the sign-in link.
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    # Persist the verifier so it survives the redirect back into a fresh rerun.
    st.session_state[_VERIFIER_KEY] = flow.code_verifier
    st.title("📋 Google Tasks Dashboard")
    st.write("Sign in with your Google account to view and manage your tasks.")
    st.link_button("🔐 Sign in with Google", auth_url, type="primary")
    st.caption(
        "The app only requests access to your Google Tasks. Your credentials stay "
        "in your own browser session."
    )
    st.stop()
