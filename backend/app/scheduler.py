"""Background scheduler for automated Microsoft Teams operations.

Runs inside the FastAPI process using APScheduler.  Three recurring jobs:

1. auto_create_teams_meetings
   Every 5 minutes — picks up interviews marked "Scheduled" that have no
   graph_event_id yet, creates Outlook calendar events + Teams online meetings
   via Microsoft Graph (application-permission path), and persists the meeting
   link / event ID back to the database.

2. send_interview_reminders
   Every 60 minutes — finds interviews scheduled to happen within the next
   24 hours (and at least 30 minutes from now) that haven't been reminded yet,
   and sends both an in-app notification and an email reminder to the
   candidate and interviewer(s).

3. sync_calendar_events
   Every 30 minutes — for interviews that already have a graph_event_id,
   re-fetches the event from Graph to detect status changes (cancelled,
   updated time, etc.) and syncs them back to the database.

All jobs silently no-op when Microsoft Graph credentials are not configured.
Errors are logged but never crash the scheduler.
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .database import SessionLocal
from . import models

logger = logging.getLogger("scheduler")

# Global scheduler instance — created on import, started/stopped by main.py.
scheduler = BackgroundScheduler(
    job_defaults={
        "coalesce": True,        # if a run was missed, run once (not N times)
        "max_instances": 1,      # prevent overlapping runs of the same job
        "misfire_grace_time": 120,
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_datetime(date_str: str, time_str: str, tz_name: str = "") -> datetime | None:
    """Combine date 'YYYY-MM-DD' and time 'HH:MM' into a timezone-aware datetime."""
    if not date_str or not time_str:
        return None
    try:
        naive = datetime.strptime(f"{date_str}T{time_str}", "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        return None
    # Attach UTC offset as a reasonable default; the actual timezone is best-effort.
    return naive.replace(tzinfo=timezone.utc)


def _resolve_participants_safe(db, interview):
    """Like interviews._resolve_participants but returns (organizer, attendees)
    or (None, []) on any error instead of raising."""
    try:
        organizer = None
        attendees = []
        for token in (interview.interviewer or "").split(","):
            name = token.strip()
            if not name:
                continue
            if "@" in name:
                email = name.lower()
            else:
                emp = db.query(models.Employee).filter(
                    models.Employee.name.ilike(name)
                ).first()
                if not emp or not emp.email:
                    emp = db.query(models.Employee).filter(
                        models.Employee.email.ilike(f"{name}@%"),
                        models.Employee.is_active == True,
                    ).first()
                email = emp.email.lower() if emp and emp.email else None
            if not email:
                continue
            if organizer is None:
                organizer = email
            else:
                attendees.append(email)
        return organizer, attendees
    except Exception:
        return None, []


def _get_or_create_reminder_tracker(db):
    """Ensure we can track which interviews have already been reminded.

    Uses a simple in-memory set per process restart since adding a DB column
    is overkill for this ephemeral state.  Resets every process restart which
    means a reminder might be sent twice at most — acceptable trade-off.
    """
    if not hasattr(scheduler, "_reminded"):
        scheduler._reminded = set()
    return scheduler._reminded


# ---------------------------------------------------------------------------
# Job 1: Auto-create Teams meetings
# ---------------------------------------------------------------------------

def auto_create_teams_meetings():
    """Pick up Scheduled interviews without a Graph event and create meetings."""
    from . import ms_graph

    if not ms_graph.app_configured():
        return  # silently skip — credentials not set

    db = SessionLocal()
    try:
        interviews = (
            db.query(models.Interview)
            .filter(
                models.Interview.status == "Scheduled",
                models.Interview.graph_event_id == "",
                models.Interview.is_deleted == False,  # noqa: E712
                models.Interview.interview_date != "",
                models.Interview.start_time != "",
            )
            .all()
        )

        for iv in interviews:
            try:
                organizer, attendees = _resolve_participants_safe(db, iv)
                if not organizer:
                    logger.warning("scheduler: no organizer for interview %s, skipping", iv.id)
                    continue

                # Parse times
                start_dt = _parse_datetime(iv.interview_date, iv.start_time)
                if not start_dt:
                    continue
                end_dt = _parse_datetime(iv.interview_date, iv.end_time) if iv.end_time else start_dt + timedelta(minutes=45)
                if end_dt <= start_dt:
                    end_dt = start_dt + timedelta(minutes=45)

                # Build subject
                job = db.query(models.Job).filter(models.Job.id == iv.job_id).first()
                subject = f"Interview: {iv.candidate_name} — {iv.round_name}"
                if job:
                    subject += f" ({job.title})"

                # Determine attendee emails (include candidate)
                candidate_emails = []
                if iv.candidate_name and "@" in iv.candidate_name:
                    candidate_emails.append(iv.candidate_name.lower())
                # Also add referral email if available
                referral = db.query(models.Referral).filter(models.Referral.id == iv.referral_id).first()
                if referral and referral.email:
                    candidate_emails.append(referral.email.lower())

                all_attendees = list(set(attendees + candidate_emails))

                timezone_str = (iv.timezone or "").strip() or "UTC"

                result = ms_graph.create_teams_interview(
                    organizer_upn=organizer,
                    subject=subject,
                    start_dt=start_dt.replace(tzinfo=None),
                    end_dt=end_dt.replace(tzinfo=None),
                    timezone=timezone_str,
                    attendee_emails=all_attendees,
                    body=f"Interview scheduled via MuraAI Refer.\n\n"
                         f"Candidate: {iv.candidate_name}\n"
                         f"Round: {iv.round_name}\n"
                         f"Date: {iv.interview_date} at {iv.start_time}",
                )

                iv.meeting_link = result.get("join_url", "")
                iv.meeting_id = result.get("online_meeting_id", "")
                iv.graph_event_id = result.get("event_id", "")
                db.commit()

                logger.info(
                    "scheduler: created Teams meeting for interview %s (event=%s)",
                    iv.id, result.get("event_id", ""),
                )

            except Exception as exc:
                db.rollback()
                logger.warning("scheduler: failed to create meeting for interview %s: %s", iv.id, exc)
                continue

    except Exception as exc:
        logger.warning("scheduler: auto_create_teams_meetings error: %s", exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 2: Interview reminders
# ---------------------------------------------------------------------------

def send_interview_reminders():
    """Send reminders for interviews happening within the next 24 hours."""
    from .email_service import send_interview_reminder_email, send_teams_meeting_email
    from .routers.notifications import create_notification

    reminded = _get_or_create_reminder_tracker(db=None)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        interviews = (
            db.query(models.Interview)
            .filter(
                models.Interview.status == "Scheduled",
                models.Interview.is_deleted == False,  # noqa: E712
                models.Interview.interview_date != "",
                models.Interview.start_time != "",
            )
            .all()
        )

        for iv in interviews:
            try:
                interview_dt = _parse_datetime(iv.interview_date, iv.start_time)
                if not interview_dt:
                    continue

                hours_until = (interview_dt - now).total_seconds() / 3600

                # Only remind if interview is between 30 minutes and 24 hours away
                if hours_until < 0.5 or hours_until > 24:
                    continue

                # Deduplicate: only remind once per interview
                if iv.id in reminded:
                    continue

                job = db.query(models.Job).filter(models.Job.id == iv.job_id).first()
                job_title = job.title if job else "a position"

                # Get candidate email from referral
                referral = db.query(models.Referral).filter(models.Referral.id == iv.referral_id).first()

                # Send reminder to candidate
                if referral and referral.email:
                    try:
                        if iv.meeting_link:
                            send_teams_meeting_email(
                                to_email=referral.email,
                                candidate_name=iv.candidate_name,
                                job_title=job_title,
                                interview_date=iv.interview_date,
                                interview_time=iv.start_time,
                                meeting_link=iv.meeting_link,
                                interviewer=iv.interviewer or "TBD",
                            )
                        else:
                            send_interview_reminder_email(
                                to_email=referral.email,
                                candidate_name=iv.candidate_name,
                                job_title=job_title,
                                interview_date=f"{iv.interview_date} at {iv.start_time}",
                            )
                    except Exception as exc:
                        logger.warning("scheduler: failed to send reminder email to candidate: %s", exc)

                # Send reminder to interviewer(s)
                _, attendees = _resolve_participants_safe(db, iv)
                all_interviewers = []
                for token in (iv.interviewer or "").split(","):
                    name = token.strip()
                    if not name:
                        continue
                    if "@" in name:
                        all_interviewers.append(name.lower())
                    else:
                        emp = db.query(models.Employee).filter(models.Employee.name.ilike(name)).first()
                        if emp and emp.email:
                            all_interviewers.append(emp.email.lower())

                for interviewer_email in all_interviewers:
                    try:
                        send_interview_reminder_email(
                            to_email=interviewer_email,
                            candidate_name=iv.candidate_name,
                            job_title=job_title,
                            interview_date=f"{iv.interview_date} at {iv.start_time}",
                        )
                    except Exception as exc:
                        logger.warning("scheduler: failed to send reminder to interviewer %s: %s", interviewer_email, exc)

                # In-app notification for the candidate's referrer
                if referral and referral.referrer_id:
                    try:
                        create_notification(
                            db=db,
                            user_id=referral.referrer_id,
                            title="Interview Reminder",
                            message=f"Reminder: {iv.candidate_name}'s {iv.round_name} interview is coming up on {iv.interview_date} at {iv.start_time}.",
                            ntype="info",
                            category="interview",
                        )
                    except Exception:
                        pass

                reminded.add(iv.id)
                logger.info("scheduler: sent reminders for interview %s", iv.id)

            except Exception as exc:
                logger.warning("scheduler: error processing reminder for interview %s: %s", iv.id, exc)
                continue

    except Exception as exc:
        logger.warning("scheduler: send_interview_reminders error: %s", exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 3: Calendar sync (detect Graph-side changes)
# ---------------------------------------------------------------------------

def sync_calendar_events():
    """Re-fetch events from Graph to detect cancellations / time changes."""
    from . import ms_graph

    if not ms_graph.app_configured():
        return

    db = SessionLocal()
    try:
        interviews = (
            db.query(models.Interview)
            .filter(
                models.Interview.graph_event_id != "",
                models.Interview.status == "Scheduled",
                models.Interview.is_deleted == False,  # noqa: E712
            )
            .all()
        )

        if not interviews:
            return

        token = ms_graph.get_app_token()
        headers = {"Authorization": f"Bearer {token}"}

        for iv in interviews:
            try:
                # We need the organizer UPN to fetch the event
                organizer, _ = _resolve_participants_safe(db, iv)
                if not organizer:
                    continue

                from urllib.parse import quote
                url = (
                    f"{ms_graph._GRAPH_BASE}/users/{quote(organizer)}"
                    f"/calendar/events/{iv.graph_event_id}"
                )
                import httpx
                resp = httpx.get(url, headers=headers, timeout=15)

                if resp.status_code == 404:
                    # Event was deleted on Graph side
                    iv.status = "Cancelled"
                    db.commit()
                    logger.info("scheduler: calendar event %s deleted — marking interview %s as Cancelled", iv.graph_event_id, iv.id)
                    continue

                if resp.status_code >= 400:
                    logger.warning("scheduler: Graph sync fetch failed for %s: HTTP %s", iv.graph_event_id, resp.status_code)
                    continue

                event = resp.json()

                # Check if the event is marked as cancelled in its status
                event_status = event.get("calendarEventStatus", "")
                if event_status == "cancelled":
                    iv.status = "Cancelled"
                    db.commit()
                    logger.info("scheduler: event %s cancelled on Graph — updating interview %s", iv.graph_event_id, iv.id)
                    continue

                # Sync time changes (compare start times)
                graph_start = event.get("start", {}).get("dateTime", "")
                if graph_start:
                    try:
                        graph_dt = datetime.fromisoformat(graph_start.replace("Z", "+00:00"))
                        local_dt = _parse_datetime(iv.interview_date, iv.start_time)
                        if local_dt and abs((graph_dt - local_dt).total_seconds()) > 300:
                            # More than 5 minutes difference — update local record
                            new_date = graph_dt.strftime("%Y-%m-%d")
                            new_time = graph_dt.strftime("%H:%M")
                            iv.interview_date = new_date
                            iv.start_time = new_time
                            db.commit()
                            logger.info("scheduler: synced time change for interview %s (%s %s)", iv.id, new_date, new_time)
                    except (ValueError, TypeError):
                        pass

            except Exception as exc:
                logger.warning("scheduler: error syncing event %s for interview %s: %s", iv.graph_event_id, iv.id, exc)
                continue

    except Exception as exc:
        logger.warning("scheduler: sync_calendar_events error: %s", exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Job 4: Send 7-day referral review reminders
# ---------------------------------------------------------------------------

def send_referral_review_reminders():
    """Send reminders to HR about referrals approaching or past their 7-day review deadline.

    Schedule:
      - Day 4 (3 days before deadline): Review reminder
      - Day 6 (1 day before deadline): Urgent reminder
      - Day 7 (deadline day): Review due notification
      - After Day 7: Overdue notification

    Deduplication: uses last_review_reminder timestamp — won't re-notify within 12h.
    """
    from .routers.notifications import create_notification

    db = SessionLocal()
    TERMINAL_STATUSES = {"Selected", "Rejected", "Offer", "Offer Released", "Joined"}

    try:
        now = datetime.utcnow()
        referrals = db.query(models.Referral).filter(
            models.Referral.is_deleted.is_(False),
            models.Referral.review_deadline.isnot(None),
            models.Referral.status.notin_(TERMINAL_STATUSES),
        ).all()

        reminded_count = 0
        for ref in referrals:
            if not ref.review_deadline:
                continue

            days_left = (ref.review_deadline - now).total_seconds() / 86400

            # Determine the reminder type based on days remaining
            reminder_type = None
            if days_left < 0:
                reminder_type = "overdue"
            elif days_left < 1:
                reminder_type = "due_today"
            elif days_left < 2:
                reminder_type = "due_tomorrow"
            elif days_left < 3:
                reminder_type = "urgent"
            elif days_left <= 4:
                reminder_type = "review_reminder"

            if reminder_type is None:
                continue

            # Dedup: skip if reminded within the last 12 hours
            if ref.last_review_reminder:
                hours_since = (now - ref.last_review_reminder).total_seconds() / 3600
                if hours_since < 12:
                    continue

            # Resolve the referrer's User for notification
            referrer_user = None
            if ref.referred_by:
                emp = db.query(models.Employee).filter(models.Employee.id == ref.referred_by).first()
                if emp:
                    referrer_user = db.query(models.User).filter(
                        models.User.employee_id == emp.id
                    ).first()

            # Get job title
            job_title = ""
            if ref.job_id:
                job = db.query(models.Job).filter(models.Job.id == ref.job_id).first()
                job_title = job.title if job else ""

            referrer_name = referrer_user.name if referrer_user else "Unknown"

            # Build notification message
            messages = {
                "review_reminder": (
                    f"Referral for {ref.candidate_name} ({job_title}) is due for review in {max(1, round(days_left))} days. "
                    f"Referred by {referrer_name}. Submitted on {ref.submitted_date.strftime('%d %b %Y')}."
                ),
                "urgent": (
                    f"Urgent: Referral for {ref.candidate_name} ({job_title}) is due for review tomorrow! "
                    f"Referred by {referrer_name}."
                ),
                "due_today": (
                    f"Review required today: {ref.candidate_name} ({job_title}) — referral from {referrer_name} "
                    f"is due for review now."
                ),
                "due_tomorrow": (
                    f"Review due tomorrow: {ref.candidate_name} ({job_title}) — referral from {referrer_name}."
                ),
                "overdue": (
                    f"OVERDUE: Referral for {ref.candidate_name} ({job_title}) from {referrer_name} "
                    f"was due {abs(round(days_left))} day(s) ago. Please review immediately."
                ),
            }

            title_map = {
                "review_reminder": "Referral Review Reminder",
                "urgent": "Urgent: Referral Review Due Tomorrow",
                "due_today": "Referral Review Due Today",
                "due_tomorrow": "Referral Review Due Tomorrow",
                "overdue": "Overdue: Referral Review Required",
            }

            ntype_map = {
                "review_reminder": "info",
                "urgent": "warning",
                "due_today": "error",
                "due_tomorrow": "warning",
                "overdue": "error",
            }

            msg = messages[reminder_type]
            title = title_map[reminder_type]
            ntype = ntype_map[reminder_type]
            link = f"/referrals/{ref.id}"

            # Send to ALL HR/admin users
            hr_users = db.query(models.User).filter(
                models.User.role.in_(["hr", "hr_manager", "chro", "vp", "cto", "ceo", "system_admin", "admin"]),
                models.User.is_active.is_(True),
            ).all()

            for hr_user in hr_users:
                try:
                    create_notification(db, hr_user.id, title, msg, ntype=ntype, category="referral", link=link)
                    reminded_count += 1
                except Exception:
                    pass

            # Update last reminder timestamp
            ref.last_review_reminder = now

        if reminded_count:
            db.commit()
            logger.info("Referral review reminders: sent %d notifications", reminded_count)

    except Exception as exc:
        logger.warning("Referral review reminders failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def start_scheduler():
    """Register all jobs and start the background scheduler.

    Safe to call multiple times — no-ops if already running.
    """
    if scheduler.running:
        return

    scheduler.add_job(
        auto_create_teams_meetings,
        trigger=IntervalTrigger(minutes=5),
        id="auto_create_teams_meetings",
        name="Auto-create Teams meetings",
        replace_existing=True,
    )
    scheduler.add_job(
        send_interview_reminders,
        trigger=IntervalTrigger(minutes=60),
        id="send_interview_reminders",
        name="Send interview reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        sync_calendar_events,
        trigger=IntervalTrigger(minutes=30),
        id="sync_calendar_events",
        name="Sync calendar events with Graph",
        replace_existing=True,
    )
    scheduler.add_job(
        send_referral_review_reminders,
        trigger=IntervalTrigger(hours=6),
        id="send_referral_review_reminders",
        name="Send referral 7-day review reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started: auto-create meetings (5m), reminders (60m), calendar sync (30m), referral review (6h)"
    )


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
