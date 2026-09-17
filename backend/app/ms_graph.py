"""Microsoft Graph integration for Teams meetings (interview scheduling).

Two authentication paths are supported:

1. APPLICATION (client credentials) — automatic scheduling.
   When AZURE_CLIENT_ID / AZURE_CLIENT_SECRET / AZURE_TENANT_ID are all set in
   the backend .env, the API can create Outlook calendar events + Teams online
   meetings on behalf of the organisation without any end-user sign-in. This is
   the primary, recommended path for HR-driven interview scheduling.

   Required Microsoft Graph APPLICATION permissions (grant Admin Consent):
     - Calendars.ReadWrite.All
     - OnlineMeetings.ReadWrite.All
     - User.Read.All            (resolve interviewer name -> mailbox)

2. DELEGATED (SSO) — optional fallback.
   HR users who signed in via 'Continue with Microsoft' (msal_service) captured
   delegated Graph tokens (Calendars.ReadWrite, OnlineMeetings.ReadWrite) at
   consent time. If application credentials are NOT configured we fall back to
   acting on that user's own behalf.

Graph endpoints used (application path):
  POST /v1.0/users/{upn}/calendar/events
      -> creates an Outlook calendar event AND a Teams online meeting in one
         call (isOnlineMeeting: true, onlineMeetingProvider: teamsForBusiness).
         The response carries onlineMeeting.joinUrl.

Security notes:
  * AZURE_CLIENT_SECRET is NEVER logged, returned in API responses, or exposed
    to the frontend. Token acquisition failures report only non-secret context.
  * 401 / 403 / token errors are surfaced with actionable, secret-free messages
    (e.g. naming the exact missing Graph permission on a 403).
"""
import base64
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import azure.identity
import httpx

from .config import settings

# All interview times are displayed and stored in IST.
IST = ZoneInfo("Asia/Kolkata")

logger = logging.getLogger("ms_graph")

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_GRAPH_AUTH = "https://login.microsoftonline.com"
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"

# Required Graph application permissions (for the admin-consent error message).
_REQUIRED_APP_PERMISSIONS = [
    "Calendars.ReadWrite.All",
    "OnlineMeetings.ReadWrite.All",
    "User.Read.All",
]

# Graph application permissions used for sending/reading mail (client credentials).
# Mail.ReadWrite.All lets the app both send and read from any mailbox (still
# requires Admin Consent); Mail.Send is required to send.
_MAIL_APP_PERMISSIONS = ["Mail.Send", "Mail.ReadWrite.All"]

# Application token cache (single-process; safe across requests via a lock).
_app_token = {"access_token": "", "expires_at": 0}
_app_token_lock = threading.Lock()
_GRACE = 120  # refresh when < 2 minutes left

# ---------------------------------------------------------------------------
# Configuration detection (safe — never references the secret value)
# ---------------------------------------------------------------------------

def missing_app_config() -> list:
    """Return the list of *non-secret* Azure env vars that are not set.

    Never includes AZURE_CLIENT_SECRET's value — only its presence is checked.
    """
    missing = []
    if not settings.AZURE_CLIENT_ID:
        missing.append("AZURE_CLIENT_ID")
    if not settings.AZURE_CLIENT_SECRET:
        missing.append("AZURE_CLIENT_SECRET")
    if not settings.AZURE_TENANT_ID:
        missing.append("AZURE_TENANT_ID")
    return missing


def app_configured() -> bool:
    """True when application (client-credentials) scheduling can be used."""
    return not missing_app_config()


# ---------------------------------------------------------------------------
# Application token (client credentials)
# ---------------------------------------------------------------------------

def _token_url() -> str:
    return f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/token"


def _credential() -> azure.identity.ClientSecretCredential:
    """Create the Azure client-credential object used to acquire Graph tokens."""
    return azure.identity.ClientSecretCredential(
        tenant_id=settings.AZURE_TENANT_ID,
        client_id=settings.AZURE_CLIENT_ID,
        client_secret=settings.AZURE_CLIENT_SECRET,
    )


def get_app_token() -> str:
    """Acquire (and cache) an Azure AD app-only access token for Graph.

    Uses azure.identity.ClientSecretCredential (wrapping MSAL under the hood)
    so the client secret never appears in logs or error messages.
    Raises RuntimeError with a secret-free message on any failure.
    """
    with _app_token_lock:
        if _app_token["access_token"] and _app_token["expires_at"] - time.time() > _GRACE:
            return _app_token["access_token"]

    if not app_configured():
        raise RuntimeError(
            "Microsoft Graph application credentials are not configured. "
            "Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET and AZURE_TENANT_ID in the backend .env."
        )

    cred = _credential()
    try:
        token_scope = "https://graph.microsoft.com/.default"
        token_response = cred.get_token(token_scope)
    except Exception as exc:  # network / DNS failure, or invalid credentials
        logger.warning("Azure token request failed: %s", exc)
        raise RuntimeError("Could not reach Microsoft identity platform (network error). Check connectivity.")

    if not token_response or not token_response.token:
        raise RuntimeError("Azure returned no access token.")

    access_token = token_response.token
    # azure.identity's TokenResponse carries expiry; normalise to int seconds
    try:
        expires_in = int(getattr(token_response, "expires_on", 0) or 0) - int(time.time())
    except Exception:
        expires_in = 3600

    with _app_token_lock:
        _app_token["access_token"] = access_token
        _app_token["expires_at"] = time.time() + max(expires_in, 60) - _GRACE
    return access_token


# ---------------------------------------------------------------------------
# Graph error handling (secret-free, actionable)
# ---------------------------------------------------------------------------

def _permission_hint(message: str) -> str:
    """Best-effort extraction of the missing permission name from a Graph 403."""
    lowered = (message or "").lower()
    found = [p for p in _REQUIRED_APP_PERMISSIONS if p.lower() in lowered]
    if found:
        return ", ".join(found)
    mail_found = [p for p in _MAIL_APP_PERMISSIONS if p.lower() in lowered]
    if mail_found:
        return ", ".join(mail_found)
    for keyword, perm in [
        ("calendar", "Calendars.ReadWrite.All"),
        ("online meeting", "OnlineMeetings.ReadWrite.All"),
        ("user", "User.Read.All"),
        ("mail", ", ".join(_MAIL_APP_PERMISSIONS)),
        ("send mail", ", ".join(_MAIL_APP_PERMISSIONS)),
    ]:
        if keyword in lowered:
            return perm
    return ", ".join(_REQUIRED_APP_PERMISSIONS)


def _raise_graph_error(resp):
    body = {}
    try:
        body = resp.json()
    except Exception:
        pass
    err_obj = body.get("error") or {}
    code = err_obj.get("code", "") or ""
    message = err_obj.get("message", "") or ""
    logger.warning("Graph error %s: %s %s", resp.status_code, code, message)

    if resp.status_code == 401:
        raise RuntimeError(
            "Microsoft Graph rejected the app credentials (401 Unauthorized). "
            "Verify AZURE_CLIENT_ID / AZURE_CLIENT_SECRET / AZURE_TENANT_ID and that admin consent was granted."
        )
    if resp.status_code == 403:
        perms = _permission_hint(message)
        raise RuntimeError(
            "Microsoft Graph returned 403 Forbidden — the app is missing the required "
            f"permission(s): {perms}. Grant Admin Consent for these application "
            "permissions in Azure (App registration -> API permissions)."
        )
    if resp.status_code == 404:
        raise RuntimeError(
            "Microsoft Graph returned 404 Not Found — the interviewer mailbox could not be found. "
            "Verify the interviewer's email/UPN exists in the tenant."
        )
    if resp.status_code == 400:
        raise RuntimeError(
            f"Microsoft Graph rejected the request (400 Bad Request): {message or code or 'invalid parameters'}."
        )
    raise RuntimeError(
        f"Microsoft Graph error ({resp.status_code}): {message or code or 'unknown error'}"
    )


# ---------------------------------------------------------------------------
# Application-path scheduling (primary)
# ---------------------------------------------------------------------------

def _format_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def create_teams_interview(
    organizer_upn: str,
    subject: str,
    start_dt: datetime,
    end_dt: datetime,
    timezone: str,
    attendee_emails: list = None,
    body: str = "",
) -> dict:
    """Create an Outlook calendar event with a Teams online meeting in the
    organizer's mailbox using application permissions.

    A single Graph call creates BOTH the calendar event and the Teams meeting;
    the response contains the Teams join URL. Attendees receive the invite in
    their own Outlook/Teams calendars.

    Returns:
        {
          "event_id": <calendar event id>,
          "web_link": <Outlook web link>,
          "join_url": <Teams join URL>,
          "online_meeting_id": <Teams online meeting id>,
          "organizer": <organizer upn/email>,
        }
    """
    token = get_app_token()
    payload = {
        "subject": subject,
        "body": {
            "contentType": "text",
            "content": body or "Interview scheduled via MuraAI Refer.",
        },
        "start": {"dateTime": _format_iso(start_dt), "timeZone": timezone},
        "end": {"dateTime": _format_iso(end_dt), "timeZone": timezone},
        "location": {"displayName": "Microsoft Teams Meeting"},
        "isOnlineMeeting": True,
        "onlineMeetingProvider": "teamsForBusiness",
    }
    attendees = attendee_emails or []
    # The organizer is not also listed as an attendee.
    payload["attendees"] = [
        {
            "emailAddress": {"address": e, "name": (e.split("@")[0] if "@" in e else e)},
            "type": "required",
        }
        for e in attendees
        if e and e.lower() != organizer_upn.lower()
    ]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{_GRAPH_BASE}/users/{quote(organizer_upn)}/calendar/events"
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=30)
    except Exception as exc:
        logger.warning("Graph calendar event request failed: %s", exc)
        raise RuntimeError("Could not reach Microsoft Graph (network error). Try again.")

    if resp.status_code >= 400:
        _raise_graph_error(resp)

    data = resp.json()
    om = data.get("onlineMeeting") or {}
    return {
        "event_id": data.get("id", ""),
        "web_link": data.get("webLink", ""),
        "join_url": om.get("joinUrl") or om.get("joinWebUrl") or "",
        "online_meeting_id": om.get("id", ""),
        "organizer": organizer_upn,
    }


# ---------------------------------------------------------------------------
# Delegated (SSO) fallback — kept for optional use
# ---------------------------------------------------------------------------

# user_id -> {"access_token", "refresh_token", "expires_at", "home_oid"}
_tokens = {}
_tokens_lock = threading.Lock()
_DELEG_GRACE = 120


def _msal_app():
    import msal
    return msal.ConfidentialClientApplication(
        client_id=settings.AZURE_CLIENT_ID,
        client_credential=settings.AZURE_CLIENT_SECRET or "",
        authority=settings.AZURE_AUTHORITY,
    )


def save_tokens(user_id: str, result: dict):
    """Persist the delegated Graph tokens captured during SSO consent."""
    if not result or not result.get("access_token"):
        return
    expires_at = time.time() + (result.get("expires_in", 3600) or 3600)
    with _tokens_lock:
        _tokens[user_id] = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token", ""),
            "expires_at": expires_at,
            "home_oid": (result.get("id_token_claims") or {}).get("oid", ""),
        }


def available(user_id: str) -> bool:
    """True if we have (or can refresh) a delegated token for this user."""
    with _tokens_lock:
        entry = _tokens.get(user_id)
    if not entry:
        return False
    if entry["expires_at"] - time.time() > _DELEG_GRACE:
        return True
    return bool(entry.get("refresh_token"))


def _get_delegated_token(user_id: str) -> str:
    """Return a valid delegated access token, refreshing first if needed."""
    with _tokens_lock:
        entry = _tokens.get(user_id)
    if not entry:
        raise RuntimeError("No Graph token for this user — sign in via Microsoft SSO first.")

    if entry["expires_at"] - time.time() > _DELEG_GRACE:
        return entry["access_token"]

    if not entry.get("refresh_token"):
        raise RuntimeError("Graph token expired with no refresh token — re-sign in via Microsoft SSO.")

    app = _msal_app()
    result = app.acquire_token_by_refresh_token(
        entry["refresh_token"],
        scopes=["User.Read", "Calendars.ReadWrite", "OnlineMeetings.ReadWrite"],
    )
    if "error" in result or "access_token" not in result:
        logger.warning("Graph token refresh failed: %s", result.get("error_description") or result.get("error"))
        raise RuntimeError("Could not refresh the Microsoft session — re-sign in via Microsoft SSO.")

    with _tokens_lock:
        entry["access_token"] = result["access_token"]
        entry["refresh_token"] = result.get("refresh_token", entry["refresh_token"])
        entry["expires_at"] = time.time() + (result.get("expires_in", 3600) or 3600)
    return entry["access_token"]


def _parse_time(interview_date: str, clock: str = "") -> datetime:
    """Build an IST-aware datetime from 'YYYY-MM-DD' and 'HH:MM'.

    The HR user always selects times in IST (Asia/Kolkata). The returned
    datetime is timezone-aware so it can be safely sent to Microsoft Graph
    with the correct timeZone payload.
    """
    base = interview_date or datetime.now(IST).strftime("%Y-%m-%d")
    if clock and len(clock) >= 5:
        dt = datetime.strptime(f"{base}T{clock}", "%Y-%m-%dT%H:%M")
    else:
        dt = datetime.strptime(base, "%Y-%m-%d")
    return dt.replace(tzinfo=IST)


def create_online_meeting(user_id: str, subject: str, start_dt: str = "",
                          start_time: str = "", end_time: str = "", attendee_email: str = "") -> dict:
    """Create a Teams online meeting (delegated) and return {id, joinUrl}."""
    token = _get_delegated_token(user_id)
    start = _parse_time(start_dt, start_time)
    end = start + timedelta(minutes=45)
    if end_time and len(end_time) >= 5:
        try:
            end = _parse_time(start_dt, end_time)
        except Exception:
            pass

    payload = {
        "subject": subject,
        "startDateTime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "lobbyBypassSettings": {"scope": "everyone"},
        "allowMeetingChat": "enabled",
        "joinMeetingIdSettings": {},
    }
    if attendee_email:
        payload["participants"] = {
            "organizer": {"upn": ""},
            "attendees": [{"upn": attendee_email, "role": "presenter"}],
        }

    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = httpx.post(
            f"{_GRAPH_BASE}/me/onlineMeetings",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except Exception as exc:
        logger.warning("Graph onlineMeetings request failed: %s", exc)
        raise RuntimeError("Could not reach Microsoft Teams (network error). Try again.")

    if resp.status_code >= 400:
        _raise_graph_error(resp)

    data = resp.json()
    return {"id": data.get("id", ""), "joinUrl": data.get("joinWebUrl", "")}


def create_calendar_event(user_id: str, subject: str, start_dt: str, start_time: str,
                          end_time: str, join_url: str = "", attendee_email: str = "",
                          body: str = "") -> dict:
    """Add the interview to the organizer's Outlook calendar (delegated)."""
    token = _get_delegated_token(user_id)
    start = _parse_time(start_dt, start_time)
    end = _parse_time(start_dt, end_time) if end_time else start + timedelta(minutes=45)

    payload = {
        "subject": subject,
        "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Asia/Kolkata"},
        "body": {"contentType": "text", "content": body or "Interview scheduled via MuraAI Refer."},
    }
    if join_url:
        payload["location"] = {"displayName": "Microsoft Teams meeting"}
        payload["onlineMeeting"] = {"joinUrl": join_url}
        payload["isOnlineMeeting"] = True
    if attendee_email:
        payload["attendees"] = [{
            "emailAddress": {"address": attendee_email, "name": attendee_email.split("@")[0]},
            "type": "required",
        }]

    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = httpx.post(f"{_GRAPH_BASE}/me/calendar/events", headers=headers, json=payload, timeout=30)
    except Exception as exc:
        logger.warning("Graph calendar event request failed: %s", exc)
        return {}
    if resp.status_code >= 400:
        _raise_graph_error(resp)
    data = resp.json()
    return {"id": data.get("id", ""), "webLink": data.get("webLink", "")}


# ---------------------------------------------------------------------------
# Mail (send / read) via application permissions
# ---------------------------------------------------------------------------

def mail_configured() -> bool:
    """True when Graph mail can be used: app credentials present AND a sender
    mailbox (GRAPH_SENDER_EMAIL) is set in the backend .env."""
    return app_configured() and bool((settings.GRAPH_SENDER_EMAIL or "").strip())


def _mailbox() -> str:
    """The mailbox (email address) used as sender / reader for Graph mail."""
    return (settings.GRAPH_SENDER_EMAIL or "").strip()


def _mail_headers(token: str, content_type: str = "application/json") -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }


def send_email_via_graph(
    to_emails: list,
    subject: str,
    body: str,
    cc_emails: list = None,
    bcc_emails: list = None,
    from_name: str = "",
    content_type: str = "html",
    attachments: list = None,
) -> dict:
    """Send an email through Microsoft Graph as the GRAPH_SENDER_EMAIL mailbox using
    application (client-credentials) permissions. Requires the Azure App
    Registration to have Mail.Send (and, given client_credentials, the mailbox
    granting this as an application permission) with Admin Consent.

    ``attachments`` is an optional list of dicts, each with:
        filename (str), content_bytes (bytes), content_type (str, optional).

    Returns a dict with ``ok`` (bool), ``message`` and, on failure, ``error``.
    """
    if not mail_configured():
        missing = ", ".join(missing_app_config())
        if missing:
            missing += ", "
        missing += "GRAPH_SENDER_EMAIL (set it in the backend .env)"
        return {
            "ok": False,
            "message": (
                "Microsoft Graph mail is not configured. Set AZURE_CLIENT_ID, "
                "AZURE_CLIENT_SECRET, AZURE_TENANT_ID and GRAPH_SENDER_EMAIL in the backend .env."
            ),
            "error": f"Missing configuration: {missing}",
        }

    to = to_emails or []
    cc = cc_emails or []
    bcc = bcc_emails or []
    if not (to or cc or bcc):
        return {
            "ok": False,
            "message": "No recipients provided. Please enter at least one email address in the To field.",
            "error": "No recipients",
        }

    sender = _mailbox()
    message = {
        "subject": subject or "",
        "body": {"contentType": content_type or "html", "content": body or ""},
        "toRecipients": [
            {"emailAddress": {"address": e}} for e in to if e
        ],
    }
    if cc:
        message["ccRecipients"] = [{"emailAddress": {"address": e}} for e in cc if e]
    if bcc:
        message["bccRecipients"] = [{"emailAddress": {"address": e}} for e in bcc if e]
    if from_name:
        message["from"] = {"emailAddress": {"address": sender, "name": from_name}}

    if attachments:
        message["attachments"] = []
        for a in attachments:
            content = a.get("content_bytes") or b""
            if isinstance(content, str):
                content = content.encode("utf-8", "ignore")
            message["attachments"].append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": a.get("filename") or "attachment",
                    "contentBytes": base64.b64encode(content).decode("ascii"),
                    "contentType": a.get("content_type") or "application/octet-stream",
                }
            )

    try:
        token = get_app_token()
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc), "error": str(exc)}

    url = f"{_GRAPH_BASE}/users/{quote(sender)}/sendMail"
    try:
        resp = httpx.post(url, headers=_mail_headers(token), json={"message": message, "saveToSentItems": True}, timeout=30)
    except Exception as exc:
        logger.warning("Graph sendMail request failed: %s", exc)
        return {"ok": False, "message": "Could not reach Microsoft Graph (network error). Try again.", "error": str(exc)}

    if resp.status_code >= 400:
        try:
            _raise_graph_error(resp)
        except RuntimeError as exc:
            return {"ok": False, "message": str(exc), "error": str(exc)}

    count = len(to) + len(cc) + len(bcc)
    return {"ok": True, "message": f"Email sent successfully to {count} recipient(s) via Microsoft Graph."}


def _graph_dt_to_ist_time(graph_start: dict, graph_end: dict) -> tuple[str, str]:
    """Convert Microsoft Graph start/end datetime objects to IST HH:MM strings.

    Graph returns ``{dateTime: "...", timeZone: "..."}`` where dateTime is
    already converted to the timezone requested via the Prefer header.  We
    request IST (Asia/Kolkata) so dateTime is in IST — but we also handle
    UTC or other timezones defensively by parsing the offset/z suffix.

    Returns (start_hhmm, end_hhmm) in IST, e.g. ("10:30", "11:00").
    """
    def _to_ist_hhmm(dt_str: str, tz_name: str) -> str:
        """Parse a Graph dateTime string and convert to IST HH:MM.

        Handles:
          - "2026-09-02T10:30:00" (local, timezone in tz_name)
          - "2026-09-02T05:00:00.0000000" (UTC or other)
          - "2026-09-02T05:00:00Z" (UTC)
          - "2026-09-02T10:30:00+05:30" (IST with offset)
        """
        if not dt_str:
            return "00:00"
        # Strip trailing fractional seconds ("05:00:00.0000000" -> "05:00:00")
        clean = dt_str.split(".")[0]
        # Strip trailing Z
        if clean.endswith("Z"):
            clean = clean[:-1]

        # Try parsing with offset first (e.g. "+05:30", "-05:00")
        dt = None
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(clean, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            logger.warning("Could not parse Graph datetime: %s", dt_str)
            return "00:00"

        # If the datetime is naive (no offset), attach the Graph-reported timezone
        if dt.tzinfo is None:
            try:
                src_tz = ZoneInfo(tz_name)
            except Exception:
                # Fallback: assume UTC if timezone name is unrecognised
                src_tz = timezone.utc
            dt = dt.replace(tzinfo=src_tz)

        # Convert to IST
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%H:%M")

    start_tz = (graph_start.get("timeZone") or "UTC")
    end_tz = (graph_end.get("timeZone") or "UTC")
    start_hhmm = _to_ist_hhmm(graph_start.get("dateTime", ""), start_tz)
    end_hhmm = _to_ist_hhmm(graph_end.get("dateTime", ""), end_tz)
    return start_hhmm, end_hhmm


def get_calendar_events(
    user_upn: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Read calendar events for a user via Microsoft Graph using the
    ``/calendarView`` endpoint (application permissions).

    ``/calendarView`` is the correct endpoint for reading availability:
    it returns the **merged view** of all calendar sources (primary,
    shared, delegate, room calendars) — unlike ``/calendar/events``
    which only shows the primary calendar.

    Requires Calendars.ReadWrite.All or Calendars.Read.All (Admin Consent).
    All returned start/end times are converted to IST (Asia/Kolkata).

    user_upn  : the user's email / UPN whose calendar to read.
    start_date: ISO date string (YYYY-MM-DD) — events from this day onwards.
    end_date  : ISO date string (YYYY-MM-DD) — events up to end of this day.

    Returns dict with ``ok`` (bool), ``events`` list, ``message``, and
    ``diagnostics`` with detailed logging info for debugging.
    """
    if not app_configured():
        return {"ok": False, "message": "Microsoft Graph app credentials not configured.", "events": [],
                "diagnostics": {"reason": "app_not_configured"}}

    try:
        token = get_app_token()
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc), "events": [],
                "diagnostics": {"reason": "token_error", "error": str(exc)}}

    # --- Build the calendarView query ---
    # /calendarView uses startDateTime/endDateTime as query params (not $filter).
    # The Prefer header tells Graph to convert all returned datetimes to IST.
    start_dt = f"{start_date}T00:00:00"
    end_dt = f"{end_date}T23:59:59"

    url = f"{_GRAPH_BASE}/users/{quote(user_upn)}/calendarView"
    params = {
        "startDateTime": start_dt,
        "endDateTime": end_dt,
        "$orderby": "start/dateTime asc",
        "$select": "subject,start,end,isAllDay,isCancelled,showAs,onlineMeeting,isOnlineMeeting",
        "$top": 100,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        # Request Graph to return all datetimes in IST.
        "Prefer": 'outlook.timezone="Asia/Kolkata"',
    }

    logger.info(
        "Calendar request: interviewer=%s date=%s endpoint=%s",
        user_upn, start_date, url,
    )

    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=30)
    except Exception as exc:
        logger.error("Graph calendarView request failed for %s: %s", user_upn, exc)
        return {
            "ok": False,
            "message": f"Could not reach Microsoft Graph (network error): {exc}",
            "events": [],
            "diagnostics": {"reason": "network_error", "error": str(exc)},
        }

    logger.info(
        "Graph calendarView response: status=%d interviewer=%s",
        resp.status_code, user_upn,
    )

    if resp.status_code >= 400:
        error_msg = ""
        try:
            _raise_graph_error(resp)
        except RuntimeError as exc:
            error_msg = str(exc)
        logger.error(
            "Graph calendarView error for %s: HTTP %d — %s",
            user_upn, resp.status_code, error_msg,
        )
        return {
            "ok": False,
            "message": error_msg,
            "events": [],
            "diagnostics": {
                "reason": "graph_http_error",
                "status": resp.status_code,
                "error": error_msg,
            },
        }

    data = resp.json()
    raw_events = data.get("value") or []
    logger.info(
        "Graph returned %d raw event(s) for %s on %s",
        len(raw_events), user_upn, start_date,
    )

    events = []
    for ev in raw_events:
        if ev.get("isCancelled"):
            continue
        start_obj = ev.get("start") or {}
        end_obj = ev.get("end") or {}
        om = ev.get("onlineMeeting") or {}

        # Convert to IST HH:MM strings.
        ist_start, ist_end = _graph_dt_to_ist_time(start_obj, end_obj)
        show_as = ev.get("showAs", "busy")
        subject = ev.get("subject", "(no subject)")

        logger.info(
            "  Calendar event: '%s' %s-%s IST (showAs=%s, allDay=%s) raw=%s/%s tz=%s/%s",
            subject, ist_start, ist_end, show_as, ev.get("isAllDay"),
            start_obj.get("dateTime", ""), end_obj.get("dateTime", ""),
            start_obj.get("timeZone", ""), end_obj.get("timeZone", ""),
        )

        events.append({
            "subject": subject,
            "start": ist_start,          # HH:MM in IST
            "end": ist_end,              # HH:MM in IST
            "isAllDay": ev.get("isAllDay", False),
            "showAs": show_as,
            "joinUrl": om.get("joinUrl") or om.get("joinWebUrl") or "",
        })

    logger.info(
        "Calendar availability: %d events returned for %s on %s (IST)",
        len(events), user_upn, start_date,
    )

    return {
        "ok": True,
        "message": f"Fetched {len(events)} calendar event(s) for {user_upn}.",
        "events": events,
        "user": user_upn,
        "diagnostics": {
            "raw_count": len(raw_events),
            "filtered_count": len(events),
            "date": start_date,
            "timezone": "Asia/Kolkata",
        },
    }


def read_emails_via_graph(
    mailbox: str = "",
    top: int = 20,
    folder: str = "inbox",
    query: str = "",
) -> dict:
    """Read emails from a mailbox via Microsoft Graph using application
    permissions. Requires Mail.Read or Mail.ReadWrite.All (Admin Consent).

    mailbox: email address of the mailbox to read (defaults to GRAPH_SENDER_EMAIL).
    top    : max number of messages (1-100).
    folder : folder to read, e.g. 'inbox' (default).
    query  : optional $filter / search term (searches subject/body).

    Returns dict with ``ok`` (bool), ``message`` and ``messages`` list.
    """
    if not app_configured():
        return {"ok": False, "message": "Microsoft Graph application credentials are not configured.", "error": "Not configured"}
    target = (mailbox or _mailbox() or "").strip()
    if not target:
        return {"ok": False, "message": "No mailbox specified. Set GRAPH_SENDER_EMAIL in .env or pass a mailbox.", "error": "No mailbox"}

    try:
        token = get_app_token()
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc), "error": str(exc)}

    top = max(1, min(int(top or 20), 100))
    url = f"{_GRAPH_BASE}/users/{quote(target)}/mailFolders/{quote(folder)}/messages"
    params = {"$top": top, "$orderby": "receivedDateTime desc"}
    if query:
        params["$search"] = f'"{query.strip()}"'
        params["$select"] = "subject,from,toRecipients,receivedDateTime,bodyPreview"

    try:
        resp = httpx.get(url, headers=_mail_headers(token), params=params, timeout=30)
    except Exception as exc:
        logger.warning("Graph read mail request failed: %s", exc)
        return {"ok": False, "message": "Could not reach Microsoft Graph (network error). Try again.", "error": str(exc)}

    if resp.status_code >= 400:
        try:
            _raise_graph_error(resp)
        except RuntimeError as exc:
            return {"ok": False, "message": str(exc), "error": str(exc)}

    data = resp.json()
    messages = []
    for m in (data.get("value") or []):
        sender = (m.get("from") or {}).get("emailAddress") or {}
        messages.append({
            "id": m.get("id", ""),
            "subject": m.get("subject", ""),
            "from": sender.get("address", ""),
            "fromName": sender.get("name", ""),
            "received": m.get("receivedDateTime", ""),
            "preview": m.get("bodyPreview", "") or "",
            "read": bool(m.get("isRead")),
        })
    return {
        "ok": True,
        "message": f"Fetched {len(messages)} email(s) from {target}/{folder}.",
        "mailbox": target,
        "messages": messages,
    }
