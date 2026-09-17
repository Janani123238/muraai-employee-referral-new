"""
Production email service using Microsoft Graph (EXCLUSIVELY — no SMTP).

Emails are sent through Microsoft Graph using the client-credentials flow with
the Azure app credentials from the backend .env (AZURE_CLIENT_ID,
AZURE_CLIENT_SECRET, AZURE_TENANT_ID). The mailbox that sends/reads is set via
GRAPH_SENDER_EMAIL (e.g. hr@yourcompany.com). The Azure App Registration must have the
Graph application permissions Mail.Send and Mail.Read (Admin Consent granted).

All sending functions return / propagate actionable, secret-free errors so the
UI can show the real reason an email failed (missing GRAPH_SENDER_EMAIL, missing Graph
permission 403, invalid credentials 401, etc.).
"""
import logging
import re
import html as _html

from .config import settings

logger = logging.getLogger("email_service")

# Imported lazily inside functions to avoid a heavyweight import at module
# load (and to keep this module importable by standalone scripts/tests).


class EmailConfigError(Exception):
    """Raised when the resolved email (Graph) configuration is invalid/missing."""


def plain_to_html(text: str) -> str:
    """Convert plain-text email content into clean HTML for delivery.
    Escapes HTML characters, converts **bold** to <b>, and newlines to <br>."""
    escaped = _html.escape(text or "")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped.replace("\n", "<br>")


def _send(to_email: str, subject: str, body: str, from_name: str = "") -> bool:
    """Send a workflow email via Microsoft Graph. Returns True on success,
    False on failure.

    Unlike the direct/composer path, automated workflow emails are best-effort:
    they must never crash a HR action, so failures are logged (with the precise
    reason) and reported via the return value rather than raising.
    """
    from . import ms_graph
    if not ms_graph.app_configured():
        missing = ", ".join(ms_graph.missing_app_config())
        logger.warning(
            "Microsoft Graph email is not configured (missing: %s) — email NOT "
            "sent to %s. Subject: %s", missing or "Azure creds", to_email, subject
        )
        return False
    if not ms_graph.mail_configured():
        logger.warning(
            "Microsoft Graph mail is not configured (GRAPH_SENDER_EMAIL empty) — email "
            "NOT sent to %s. Subject: %s", to_email, subject
        )
        return False
    result = ms_graph.send_email_via_graph(
        [to_email], subject, body, from_name=from_name, content_type="text"
    )
    if result.get("ok"):
        return True
    logger.warning("Graph email failed to %s (%s): %s", to_email, subject, result.get("error") or result.get("message"))
    return False


def send_email_direct(to_emails: list, cc_emails: list, bcc_emails: list,
                      subject: str, body: str, from_name: str = "",
                      attachments: list = None) -> dict:
    """Send a custom email to multiple recipients with CC/BCC support via
    Microsoft Graph (no SMTP).

    ``attachments`` is an optional list of dicts with ``filename``,
    ``content_bytes`` and optional ``content_type``.

    Returns a dict with ``sent``/``failed`` counts and a user-facing ``message``
    that reflects the real cause of any failure.
    """
    all_recipients = list(to_emails) + list(cc_emails) + list(bcc_emails)
    if not all_recipients:
        return {"sent": 0, "failed": 0,
                "message": "No recipients provided. Please enter at least one email address in the To field."}

    from . import ms_graph
    if not ms_graph.app_configured():
        missing = ", ".join(ms_graph.missing_app_config())
        msg = (
            "Microsoft Graph email is not configured. Set AZURE_CLIENT_ID, "
            "AZURE_CLIENT_SECRET and AZURE_TENANT_ID in the backend .env."
            + (f" Missing: {missing}." if missing else "")
        )
        return {"sent": 0, "failed": len(all_recipients), "message": msg, "error": "Graph not configured"}
    if not ms_graph.mail_configured():
        msg = (
            "Microsoft Graph mail is not configured — set GRAPH_SENDER_EMAIL in the backend .env "
            "to the mailbox used for sending (e.g. hr@yourcompany.com)."
        )
        return {"sent": 0, "failed": len(all_recipients), "message": msg, "error": "GRAPH_SENDER_EMAIL not set"}

    result = ms_graph.send_email_via_graph(
        to_emails, subject, body,
        cc_emails=cc_emails, bcc_emails=bcc_emails,
        from_name=from_name, content_type="html",
        attachments=attachments,
    )
    if result.get("ok"):
        return {"sent": len(all_recipients), "failed": 0, "message": result["message"]}
    return {"sent": 0, "failed": len(all_recipients),
            "message": result.get("message", "Failed to send email via Microsoft Graph."),
            "error": result.get("error", result.get("message", ""))}


def get_email_status() -> dict:
    """Describe the current Microsoft Graph email configuration state (no
    secrets). Used by the Admin settings UI in place of the old SMTP probe."""
    from . import ms_graph
    if not ms_graph.app_configured():
        missing = ", ".join(ms_graph.missing_app_config())
        return {
            "ok": False,
            "configured": False,
            "message": "Microsoft Graph email is not configured. Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET and AZURE_TENANT_ID in the backend .env."
                       + (f" Missing: {missing}." if missing else ""),
            "sender": "",
        }
    if not ms_graph.mail_configured():
        return {
            "ok": False,
            "configured": False,
            "message": "Microsoft Graph mail is configured but GRAPH_SENDER_EMAIL is empty. Set GRAPH_SENDER_EMAIL (the sending mailbox) in the backend .env.",
            "sender": "",
        }
    return {
        "ok": True,
        "configured": True,
        "message": "Microsoft Graph email is configured. Sending as: " + settings.GRAPH_SENDER_EMAIL,
        "sender": settings.GRAPH_SENDER_EMAIL,
    }


def test_email_connection() -> dict:
    """Probe the Microsoft Graph email setup without sending: verifies app
    credentials and (optionally) that the GRAPH_SENDER_EMAIL mailbox is reachable."""
    from . import ms_graph
    status = get_email_status()
    if not status["ok"]:
        return {"ok": False, "message": status["message"], "detail": status["message"]}

    read = ms_graph.read_emails_via_graph(top=1)
    if read.get("ok"):
        return {
            "ok": True,
            "message": f"Microsoft Graph connected. GRAPH_SENDER_EMAIL mailbox {status['sender']} is reachable and Mail.Read works.",
            "detail": f"Fetched {len(read.get('messages') or [])} message(s) as {status['sender']}.",
        }
    return {"ok": False, "message": read.get("message", "Microsoft Graph connection test failed."),
            "detail": read.get("error", read.get("message", ""))}


# ---------------------------------------------------------------------------
# Workflow email templates (Graph-only via _send)
# ---------------------------------------------------------------------------

def send_password_reset_email(to_email: str, reset_link: str) -> None:
    _send(to_email, "Reset your MuraAI Refer password",
          f"We received a request to reset your password.\n\n"
          f"Reset here (valid {settings.PASSWORD_RESET_EXPIRE_MINUTES} min): {reset_link}\n\n"
          f"If you didn't request this, ignore this email.")


def send_welcome_email(to_email: str, name: str) -> None:
    _send(to_email, "Welcome to MuraAI Refer",
          f"Hi {name},\n\nWelcome to MuraAI Refer — the AI-powered employee referral portal.\n\n"
          f"You can start referring candidates right away from the portal.\n\nBest regards,\nMuraAI Team")


def send_referral_submitted_email(to_email: str, referrer_name: str, candidate_name: str, job_title: str) -> None:
    _send(to_email, f"Referral Submitted — {candidate_name}",
          f"Hi {referrer_name},\n\nYour referral for {candidate_name} ({job_title}) has been submitted successfully.\n\n"
          f"You can track the status from your My Referrals dashboard.\n\nBest regards,\nMuraAI Team")


def send_referral_status_email(to_email: str, candidate_name: str, status: str, job_title: str) -> None:
    _send(to_email, f"Referral Update — {candidate_name}",
          f"Hi,\n\nThe referral for {candidate_name} ({job_title}) has been updated to: {status}.\n\nBest regards,\nMuraAI Team")


def send_interview_scheduled_email(to_email: str, candidate_name: str, job_title: str, round_name: str) -> None:
    _send(to_email, f"Interview Scheduled — {candidate_name}",
          f"Hi,\n\nAn interview has been scheduled for {candidate_name} ({job_title}).\n\n"
          f"Round: {round_name}\n\nBest regards,\nMuraAI Team")


def send_interview_reminder_email(to_email: str, candidate_name: str, job_title: str, interview_date: str) -> None:
    _send(to_email, f"Interview Reminder — {candidate_name}",
          f"Hi,\n\nThis is a reminder that {candidate_name} has an upcoming interview for {job_title}.\n\n"
          f"Scheduled: {interview_date}\n\nBest regards,\nMuraAI Team")


def send_offer_email(to_email: str, candidate_name: str, job_title: str) -> None:
    _send(to_email, f"Offer Extended — {candidate_name}",
          f"Hi,\n\nAn offer has been extended to {candidate_name} for the {job_title} position.\n\nBest regards,\nMuraAI Team")


def send_rejection_email(to_email: str, candidate_name: str, job_title: str) -> None:
    _send(to_email, f"Referral Update — {candidate_name}",
          f"Hi,\n\nUnfortunately, {candidate_name}'s application for {job_title} was not successful this time.\n\n"
          f"Thank you for the referral.\n\nBest regards,\nMuraAI Team")


def send_joining_confirmation_email(to_email: str, candidate_name: str, job_title: str, joining_date: str = "") -> None:
    _send(to_email, f"Joining Confirmation — {candidate_name}",
          f"Hi,\n\n{candidate_name} has officially joined the team for the {job_title} position."
          + (f"\n\nJoining Date: {joining_date}" if joining_date else "") +
          f"\n\nBest regards,\nMuraAI Team")


def send_bonus_credited_email(to_email: str, referrer_name: str, amount: int, candidate_name: str) -> None:
    _send(to_email, f"Referral Bonus Credited — ₹{amount:,}",
          f"Hi {referrer_name},\n\nCongratulations! A referral bonus of ₹{amount:,} has been credited "
          f"for the successful referral of {candidate_name}.\n\nThank you for your contribution!\n\nBest regards,\nMuraAI Team")


def send_interview_reschedule_email(to_email: str, candidate_name: str, job_title: str,
                                      new_date: str, new_time: str, round_name: str) -> None:
    _send(to_email, f"Interview Rescheduled — {candidate_name}",
          f"Hi,\n\nThe interview for {candidate_name} ({job_title}) has been rescheduled.\n\n"
          f"Round: {round_name}\nNew Date: {new_date}\nNew Time: {new_time}\n\n"
          f"Best regards,\nMuraAI Team")


def send_selection_email(to_email: str, candidate_name: str, job_title: str) -> None:
    _send(to_email, f"Congratulations! You've been selected — {candidate_name}",
          f"Hi {candidate_name},\n\n"
          f"We're pleased to inform you that you've been selected for the {job_title} position.\n\n"
          f"Our HR team will be in touch with the formal offer letter shortly.\n\n"
          f"Best regards,\nMuraAI Team")


def send_joining_instructions_email(to_email: str, candidate_name: str, job_title: str,
                                     joining_date: str = "", details: str = "") -> None:
    _send(to_email, f"Joining Instructions — {candidate_name}",
          f"Hi {candidate_name},\n\n"
          f"Welcome to MuraAI! We're excited to have you join us as {job_title}.\n\n"
          + (f"Joining Date: {joining_date}\n" if joining_date else "")
          + (f"\n{details}" if details else "")
          + f"\n\nPlease bring the following documents on your first day:\n"
          f"- Government-issued ID\n- Educational certificates\n- Previous employment documents\n"
          f"- Passport-size photographs\n\n"
          f"Best regards,\nMuraAI Team")


def send_teams_meeting_email(to_email: str, candidate_name: str, job_title: str,
                              interview_date: str, interview_time: str, meeting_link: str,
                              interviewer: str) -> None:
    _send(to_email, f"Interview Invitation — {candidate_name}",
          f"Hi {candidate_name},\n\n"
          f"You have been invited for an interview for the {job_title} position.\n\n"
          f"Date: {interview_date}\n"
          f"Time: {interview_time}\n"
          f"Interviewer: {interviewer}\n"
          f"Meeting Link: {meeting_link}\n\n"
          f"Please join the meeting 5 minutes before the scheduled time.\n\n"
          f"Best regards,\nMuraAI Team")


def send_interviewer_invite_email(to_email: str, candidate_name: str, job_title: str,
                                    interview_date: str, interview_time: str, meeting_link: str,
                                    round_name: str) -> None:
    _send(to_email, f"Interview Assignment — {candidate_name}",
          f"Hi,\n\n"
          f"You have been assigned to conduct an interview.\n\n"
          f"Candidate: {candidate_name}\n"
          f"Position: {job_title}\n"
          f"Round: {round_name}\n"
          f"Date: {interview_date}\n"
          f"Time: {interview_time}\n"
          f"Meeting Link: {meeting_link}\n\n"
          f"Please review the candidate's resume and be prepared.\n\n"
          f"Best regards,\nMuraAI Team")


def send_interview_invitation_email(to_email: str, candidate_name: str, job_title: str,
                                     interview_date: str, interview_time: str,
                                     meeting_info: str, notes: str = "") -> None:
    body = (
        f"Dear {candidate_name},\n\n"
        f"You have been invited for an interview for the {job_title} position.\n\n"
        f"Interview Details:\n"
        f"  Date: {interview_date}\n"
        f"  Time: {interview_time}\n"
    )
    if meeting_info:
        body += f"  {meeting_info}\n"
    if notes:
        body += f"\nAdditional Notes:\n{notes}\n"
    body += (
        f"\nPlease ensure you are available at the scheduled time. "
        f"If you need to reschedule, please contact us as soon as possible.\n\n"
        f"We look forward to speaking with you.\n\n"
        f"Best regards,\nMuraAI HR Team"
    )
    _send(to_email, f"Interview Invitation — {job_title} at MuraAI", body)
