"""Microsoft Entra ID (MSAL) SSO.

Authorization-code flow, server-side, with PKCE (S256):
  1. GET /api/auth/microsoft/login -> 302 to Entra ID consent screen
  2. Entra redirects back to /api/auth/microsoft/callback?code=...
  3. Callback exchanges the code for tokens via MSAL, resolves the user's
     work email, upserts a User/Employee record, and issues a MuraAI JWT that
     is handed back to the SPA via ?sso_token=<jwt>.

The SPA never sees the client secret; everything stays server-side.

PKCE: Entra requires a Proof Key for Code Exchange whenever the redirect URI is
registered under the "Single-page application" platform. We always send a
S256 code_challenge (harmless for "Web"-registered URIs, required for SPA) and
carry the matching code_verifier to the callback in a short-lived server-side
store keyed by the OAuth `state` value.
"""
import logging
import secrets
import threading
import time
from urllib.parse import quote

from fastapi import HTTPException

from .config import settings

logger = logging.getLogger("msal_service")

# PKCE auth-flow store: state -> {"flow", "ts"}. Single-process app, so an
# in-process TTL dict is fine; entries live at most a few minutes.
_pkce_store = {}
_pkce_lock = threading.Lock()
_PKCE_TTL = 600  # seconds


def _get_msal_app():
    if not settings.AZURE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Microsoft sign-in is not configured. Ask your administrator to set AZURE_CLIENT_ID / AZURE_CLIENT_SECRET / AZURE_TENANT_ID.",
        )
    import msal
    return msal.ConfidentialClientApplication(
        client_id=settings.AZURE_CLIENT_ID,
        client_credential=settings.AZURE_CLIENT_SECRET or "",
        authority=settings.AZURE_AUTHORITY,
    )


def sso_enabled() -> bool:
    return bool(settings.AZURE_CLIENT_ID and settings.AZURE_CLIENT_SECRET and settings.AZURE_TENANT_ID)


_SCOPES = [
    "User.Read",
    "email",
    "Calendars.ReadWrite",      # interview scheduling -> Outlook calendar
    "OnlineMeetings.ReadWrite", # create Teams online meetings
]  # MSAL handles openid/profile/offline_access internally


def build_auth_url(callback_url: str) -> str:
    """Build the Entra authorize URL with a fresh PKCE challenge. MSAL generates
    the S256 code_challenge + matching code_verifier; we stash the whole auth
    flow under a random `state` value so the verifier never appears in a URL."""
    app = _get_msal_app()
    state = "muraai-sso-" + secrets.token_hex(8)
    flow = app.initiate_auth_code_flow(scopes=_SCOPES, redirect_uri=callback_url, state=state)
    with _pkce_lock:
        _pkce_store[state] = {"flow": flow, "ts": time.time()}
    return flow["auth_uri"]


def exchange_code(callback_url: str, code: str, state: str = "") -> dict:
    """Exchange the auth code for a token result using the stored PKCE flow
    (acquire_token_by_auth_code_flow also validates the state/nonce for CSRF).
    If the flow is gone (expired/cross-instance), falls back to a bare exchange,
    which Entra still accepts for Web-registered redirect URIs."""
    app = _get_msal_app()
    with _pkce_lock:
        entry = _pkce_store.pop(state, None) if state else None
        flow = entry["flow"] if entry and entry["ts"] + _PKCE_TTL > time.time() else None

    if flow:
        result = app.acquire_token_by_auth_code_flow(
            dict(flow), {"code": code, "state": state}
        )
    else:
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=_SCOPES,
            redirect_uri=callback_url,
        )
    if "error" in result or "access_token" not in result:
        error = result.get("error_description") or result.get("error") or "Unknown MSAL error"
        logger.warning("MSAL code exchange failed: %s", error)
        raise HTTPException(status_code=401, detail=f"Microsoft sign-in failed: {error}")
    return result


def resolve_profile(result: dict) -> dict:
    """Pull the user's display name + email from the MSAL token result."""
    id_claims = result.get("id_token_claims", {}) or {}
    name = id_claims.get("name") or id_claims.get("preferred_username") or "Microsoft User"
    email = (
        id_claims.get("email")
        or id_claims.get("preferred_username")
        or (id_claims.get("upn", "").lower() or "")
    )
    if not email:
        # Fall back to the graph claim carried in the access token if present
        email = id_claims.get("unique_name", "")
    if not email:
        raise HTTPException(status_code=401, detail="Microsoft account has no verifiable work email.")
    email = email.strip().lower()
    return {"name": name, "email": email}
