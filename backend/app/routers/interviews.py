from datetime import datetime, timedelta
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user, require_hr
from ..routers.activity import log_activity
from ..routers.admin import log_audit
from .. import email_service, ms_graph
from ..ms_graph import _parse_time, IST

logger = logging.getLogger("interviews")

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def serialize(i: models.Interview):
    return {
        "id": i.id,
        "referralId": i.referral_id,
        "jobId": i.job_id,
        "candidateName": i.candidate_name,
        "roundName": i.round_name,
        "interviewType": i.interview_type,
        "interviewDate": i.interview_date,
        "startTime": i.start_time,
        "endTime": i.end_time,
        "interviewer": i.interviewer,
        "meetingLink": i.meeting_link,
        "meetingId": i.meeting_id or "",
        "graphEventId": i.graph_event_id or "",
        "timezone": i.timezone or "",
        "location": i.location,
        "notes": i.notes,
        "status": i.status,
        "result": i.result,
        "feedback": i.feedback,
        "score": i.score,
        "created_at": i.created_at,
        "updated_at": i.updated_at,
    }


def _active():
    return models.Interview.is_deleted.is_(False)


@router.get("")
def list_interviews(db: Session = Depends(get_db), user=Depends(require_hr)):
    interviews = db.query(models.Interview).filter(_active()).order_by(models.Interview.created_at.desc()).all()
    return [serialize(i) for i in interviews]


@router.get("/calendar")
def interview_calendar(year: int = None, month: int = None,
                       start: str = "", end: str = "",
                       db: Session = Depends(get_db), user=Depends(require_hr)):
    """Return interviews, optionally filtered by year/month or start/end date range."""
    now = datetime.utcnow()
    interviews = db.query(models.Interview).filter(_active()).all()
    result = []
    for iv in interviews:
        if not iv.interview_date:
            continue
        try:
            if start and end:
                if iv.interview_date < start or iv.interview_date > end:
                    continue
            elif year and month:
                parts = iv.interview_date.split("-")
                if int(parts[0]) != year or int(parts[1]) != month:
                    continue
            result.append(serialize(iv))
        except Exception:
            continue
    return result


@router.get("/today")
def today_interviews(db: Session = Depends(get_db), user=Depends(require_hr)):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    interviews = db.query(models.Interview).filter(
        _active(),
        models.Interview.interview_date == today
    ).order_by(models.Interview.start_time).all()
    return [serialize(i) for i in interviews]


@router.get("/availability")
def check_availability(interviewer: str = "", date: str = "", duration: int = 30,
                       fetch_calendar: bool = False, exclude_id: str = "",
                       db: Session = Depends(get_db), user=Depends(require_hr)):
    """Check interviewer availability for a given date.

    Combines existing interview records from the database AND calendar events
    from Microsoft Graph (when configured) to give a complete picture.

    Params:
      interviewer : comma-separated names or emails.
      date        : YYYY-MM-DD.
      duration    : slot duration in minutes (30, 45, 60). Defaults to 30.
      exclude_id  : interview ID to exclude (for rescheduling).
      calendar    : 'true' to also fetch Outlook calendar events via Graph.

    Returns busy slots, individual time slots with available/busy status,
    and recommended free windows.
    """
    if not interviewer or not date:
        raise HTTPException(status_code=400, detail="interviewer and date are required")

    try:
        duration = int(duration) if duration else 30
    except (ValueError, TypeError):
        duration = 30
    duration = max(15, min(duration, 120))  # clamp 15–120 min

    tokens = [t.strip().lower() for t in interviewer.split(",") if t.strip()]
    interviews = db.query(models.Interview).filter(
        _active(),
        models.Interview.interview_date == date,
    ).all()

    busy = []
    for iv in interviews:
        if exclude_id and iv.id == exclude_id:
            continue
        iv_tokens = [t.strip().lower() for t in (iv.interviewer or "").split(",") if t.strip()]
        if any(t in iv_tokens for t in tokens):
            busy.append({
                "id": iv.id,
                "candidateName": iv.candidate_name,
                "roundName": iv.round_name,
                "startTime": iv.start_time or "09:00",
                "endTime": iv.end_time or "10:00",
                "status": iv.status,
                "source": "internal",
            })

    # --- Fetch Outlook calendar events via Graph (best-effort) ---
    calendar_source = "none"
    calendar_error = ""
    graph_events = []
    if fetch_calendar and ms_graph.app_configured():
        # Resolve each token to a mailbox UPN
        for token in tokens:
            email = None
            if "@" in token:
                email = token
            else:
                emp = db.query(models.Employee).filter(models.Employee.name.ilike(token)).first()
                if emp and emp.email:
                    email = emp.email.lower()
            if not email:
                calendar_error = f"Could not resolve interviewer '{token}' to an email address."
                logger.warning("Interviewer resolution failed: '%s' -> no email found", token)
                continue

            logger.info(
                "Fetching Outlook calendar: interviewer='%s' email=%s date=%s",
                token, email, date,
            )
            cal_result = ms_graph.get_calendar_events(email, date, date)

            if cal_result.get("ok"):
                calendar_source = "graph"
                cal_events = cal_result.get("events", [])
                diagnostics = cal_result.get("diagnostics", {})
                logger.info(
                    "Calendar fetch OK for %s: %d events (raw=%s)",
                    email, len(cal_events), diagnostics.get("raw_count"),
                )
                for ev in cal_events:
                    # Skip all-day events and free/transparent events
                    if ev.get("isAllDay") or ev.get("showAs") in ("free", "oof"):
                        logger.info(
                            "  Skipping event '%s' (allDay=%s, showAs=%s)",
                            ev.get("subject"), ev.get("isAllDay"), ev.get("showAs"),
                        )
                        continue
                    # get_calendar_events() now returns IST HH:MM strings directly
                    ev_start = ev.get("start", "")
                    ev_end = ev.get("end", "")
                    if not ev_start or not ev_end:
                        continue
                    logger.info(
                        "  Busy slot: %s-%s IST '%s' (showAs=%s)",
                        ev_start, ev_end, ev.get("subject"), ev.get("showAs"),
                    )
                    busy.append({
                        "id": f"graph_{email}_{ev_start}",
                        "candidateName": ev.get("subject", "Calendar Event"),
                        "roundName": "Outlook Calendar",
                        "startTime": ev_start,
                        "endTime": ev_end,
                        "status": "Busy",
                        "source": "graph",
                    })
            else:
                # Calendar fetch failed — propagate the error
                error_msg = cal_result.get("message", "Unknown error")
                calendar_source = "error"
                calendar_error = (
                    f"Unable to retrieve calendar for {email}: {error_msg}. "
                    f"Please verify the interviewer's Microsoft calendar access."
                )
                logger.error(
                    "Calendar fetch FAILED for %s: %s",
                    email, error_msg,
                )

    def to_minutes(t):
        try:
            h, m = t.split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 540

    busy_sorted = sorted(busy, key=lambda x: to_minutes(x["startTime"]))

    WORK_START, WORK_END = 540, 1080  # 09:00 – 18:00
    free = []
    cursor = WORK_START
    for b in busy_sorted:
        bstart = to_minutes(b["startTime"])
        bend = to_minutes(b["endTime"])
        if cursor < bstart:
            free.append({"start": f"{cursor // 60:02d}:{cursor % 60:02d}", "end": f"{bstart // 60:02d}:{bstart % 60:02d}"})
        cursor = max(cursor, bend)
    if cursor < WORK_END:
        free.append({"start": f"{cursor // 60:02d}:{cursor % 60:02d}", "end": "18:00"})

    recommended = [s for s in free if (to_minutes(s["end"]) - to_minutes(s["start"])) >= duration]

    # --- Build individual time-slot grid ---
    slots = []
    slot_time = WORK_START
    while slot_time + duration <= WORK_END:
        slot_start_str = f"{slot_time // 60:02d}:{slot_time % 60:02d}"
        slot_end_min = slot_time + duration
        slot_end_str = f"{slot_end_min // 60:02d}:{slot_end_min % 60:02d}"
        is_busy = False
        conflict_info = None
        for b in busy_sorted:
            bstart = to_minutes(b["startTime"])
            bend = to_minutes(b["endTime"])
            if slot_time < bend and slot_end_min > bstart:
                is_busy = True
                conflict_info = b
                break
        slots.append({
            "start": slot_start_str,
            "end": slot_end_str,
            "available": not is_busy,
            "conflict": conflict_info,
        })
        slot_time += 30  # advance by 30 min for the grid

    return {
        "busy": busy_sorted,
        "free": free,
        "recommended": recommended,
        "slots": slots,
        "duration": duration,
        "calendarSource": calendar_source,
        "calendarError": calendar_error,
        "date": date,
        "interviewer": interviewer,
    }


@router.get("/check-conflict")
def check_conflict(interviewer: str = "", date: str = "", start_time: str = "", end_time: str = "",
                   exclude_id: str = "", db: Session = Depends(get_db), user=Depends(require_hr)):
    """Check if a proposed time slot conflicts with existing interviews."""
    if not interviewer or not date or not start_time:
        raise HTTPException(status_code=400, detail="interviewer, date, and start_time are required")

    tokens = [t.strip().lower() for t in interviewer.split(",") if t.strip()]
    interviews = db.query(models.Interview).filter(
        _active(),
        models.Interview.interview_date == date,
    ).all()

    def to_minutes(t):
        try:
            h, m = t.split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 540

    proposed_start = to_minutes(start_time)
    proposed_end = to_minutes(end_time) if end_time else proposed_start + 60

    conflicts = []
    for iv in interviews:
        if exclude_id and iv.id == exclude_id:
            continue
        iv_tokens = [t.strip().lower() for t in (iv.interviewer or "").split(",") if t.strip()]
        if not any(t in iv_tokens for t in tokens):
            continue
        iv_start = to_minutes(iv.start_time or "09:00")
        iv_end = to_minutes(iv.end_time or "10:00")
        if proposed_start < iv_end and proposed_end > iv_start:
            conflicts.append({
                "id": iv.id,
                "candidateName": iv.candidate_name,
                "roundName": iv.round_name,
                "startTime": iv.start_time,
                "endTime": iv.end_time,
            })

    return {"hasConflict": len(conflicts) > 0, "conflicts": conflicts}


@router.get("/refresh-availability")
def refresh_availability(interviewer: str = "", date: str = "", duration: int = 30,
                        exclude_id: str = "",
                        db: Session = Depends(get_db), user=Depends(require_hr)):
    """Force-refresh calendar availability — used just before final booking
    to avoid stale data.  Always fetches Graph calendar events."""
    return check_availability(
        interviewer=interviewer, date=date, duration=duration,
        fetch_calendar=True, exclude_id=exclude_id,
        db=db, user=user,
    )


def _check_double_booking(db: Session, interviewer: str, date: str,
                          start_time: str, end_time: str, exclude_id: str = "") -> list:
    """Check both DB interviews AND Graph calendar for scheduling conflicts.
    Returns a list of conflict dicts (empty = no conflict)."""
    tokens = [t.strip().lower() for t in interviewer.split(",") if t.strip()]
    if not tokens or not date or not start_time:
        return []

    def to_minutes(t):
        try:
            h, m = t.split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 0

    proposed_start = to_minutes(start_time)
    proposed_end = to_minutes(end_time) if end_time else proposed_start + 60
    if proposed_end <= proposed_start:
        proposed_end = proposed_start + 60

    conflicts = []

    # 1. Check internal interview records
    interviews = db.query(models.Interview).filter(
        _active(), models.Interview.interview_date == date,
    ).all()
    for iv in interviews:
        if exclude_id and iv.id == exclude_id:
            continue
        iv_tokens = [t.strip().lower() for t in (iv.interviewer or "").split(",") if t.strip()]
        if not any(t in iv_tokens for t in tokens):
            continue
        iv_start = to_minutes(iv.start_time or "09:00")
        iv_end = to_minutes(iv.end_time or "10:00")
        if proposed_start < iv_end and proposed_end > iv_start:
            conflicts.append({
                "source": "internal",
                "id": iv.id,
                "candidateName": iv.candidate_name,
                "roundName": iv.round_name,
                "startTime": iv.start_time,
                "endTime": iv.end_time,
            })

    # 2. Check Outlook calendar via Graph (best-effort)
    if ms_graph.app_configured():
        for token in tokens:
            email = token if "@" in token else None
            if not email:
                emp = db.query(models.Employee).filter(models.Employee.name.ilike(token)).first()
                if emp and emp.email:
                    email = emp.email.lower()
            if not email:
                continue
            logger.info(
                "Double-booking check: interviewer=%s email=%s date=%s proposed=%s-%s",
                token, email, date, start_time, end_time or f"+{60}min",
            )
            cal = ms_graph.get_calendar_events(email, date, date)
            if not cal.get("ok"):
                logger.warning(
                    "Double-booking: calendar fetch failed for %s: %s",
                    email, cal.get("message"),
                )
                # If we can't read the calendar, we can't guarantee no conflict.
                # Return a conflict to be safe (fail-closed).
                conflicts.append({
                    "source": "graph_unavailable",
                    "id": f"graph_unavail_{email}",
                    "candidateName": f"Cannot verify calendar for {email}",
                    "roundName": "Calendar Unavailable",
                    "startTime": start_time,
                    "endTime": end_time or "",
                })
                continue
            for ev in cal.get("events", []):
                if ev.get("isAllDay") or ev.get("showAs") in ("free", "oof"):
                    continue
                # get_calendar_events() returns IST HH:MM strings directly
                ev_start_str = ev.get("start", "")
                ev_end_str = ev.get("end", "")
                if not ev_start_str or not ev_end_str:
                    continue
                ev_s = to_minutes(ev_start_str)
                ev_e = to_minutes(ev_end_str)
                if proposed_start < ev_e and proposed_end > ev_s:
                    conflicts.append({
                        "source": "graph",
                        "id": f"graph_{email}_{ev_start_str}",
                        "candidateName": ev.get("subject", "Calendar Event"),
                        "roundName": "Outlook Calendar",
                        "startTime": ev_start_str,
                        "endTime": ev_end_str,
                    })
    return conflicts


@router.get("/upcoming")
def upcoming_interviews(db: Session = Depends(get_db), user=Depends(require_hr)):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    interviews = db.query(models.Interview).filter(
        _active(),
        models.Interview.interview_date >= today,
        models.Interview.status.in_(["Scheduled", "Rescheduled"])
    ).order_by(models.Interview.interview_date, models.Interview.start_time).all()
    return [serialize(i) for i in interviews]


@router.get("/referral/{referral_id}")
def get_interviews_by_referral(referral_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    interviews = db.query(models.Interview).filter(
        _active(),
        models.Interview.referral_id == referral_id
    ).order_by(models.Interview.created_at.desc()).all()
    return [serialize(i) for i in interviews]


@router.post("")
def create_interview(payload: schemas.InterviewIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    referral = db.query(models.Referral).filter(models.Referral.id == payload.referralId).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    job_id = payload.jobId or referral.job_id

    # --- Double-booking prevention: check DB + Graph calendar ---
    if payload.interviewer and payload.interviewDate and payload.startTime:
        conflicts = _check_double_booking(
            db, payload.interviewer, payload.interviewDate,
            payload.startTime, payload.endTime,
        )
        if conflicts:
            details = "; ".join(
                f"{c['candidateName']} ({c['roundName']}) {c['startTime']}-{c['endTime']}"
                for c in conflicts[:3]
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Scheduling conflict: the interviewer is not available at the requested time. "
                    f"Conflicts: {details}. Please choose a different time slot."
                ),
            )

    interview = models.Interview(
        referral_id=payload.referralId,
        job_id=job_id,
        candidate_name=payload.candidateName or referral.candidate_name,
        round_name=payload.roundName,
        interview_type=payload.interviewType,
        interview_date=payload.interviewDate,
        start_time=payload.startTime,
        end_time=payload.endTime,
        interviewer=payload.interviewer,
        meeting_link=payload.meetingLink,
        location=payload.location,
        notes=payload.notes,
        status="Scheduled",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    log_activity(
        db, payload.referralId,
        "Interview Scheduled",
        f"{payload.roundName} scheduled with {payload.interviewer} on {payload.interviewDate} ({payload.startTime}-{payload.endTime})",
        user.name,
    )
    log_audit(db, user, "Interview created", target="interview", target_id=interview.id,
              details=f"{payload.roundName} | candidate: {interview.candidate_name} | {payload.interviewDate}")

    return serialize(interview)


@router.put("/{interview_id}")
def update_interview(interview_id: str, payload: schemas.InterviewUpdate,
                     db: Session = Depends(get_db), user=Depends(require_hr)):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if payload.interviewType is not None:
        interview.interview_type = payload.interviewType
    if payload.interviewDate is not None:
        interview.interview_date = payload.interviewDate
    if payload.startTime is not None:
        interview.start_time = payload.startTime
    if payload.endTime is not None:
        interview.end_time = payload.endTime
    if payload.interviewer is not None:
        interview.interviewer = payload.interviewer
    if payload.meetingLink is not None:
        interview.meeting_link = payload.meetingLink
    if payload.location is not None:
        interview.location = payload.location
    if payload.notes is not None:
        interview.notes = payload.notes
    if payload.status is not None:
        interview.status = payload.status
    if payload.result is not None:
        interview.result = payload.result
    if payload.feedback is not None:
        interview.feedback = payload.feedback
    if payload.score is not None:
        interview.score = payload.score

    interview.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(interview)

    log_activity(
        db, interview.referral_id,
        "Interview Updated",
        f"{interview.round_name} updated — status: {interview.status}",
        user.name,
    )
    log_audit(db, user, "Interview updated", target="interview", target_id=interview_id,
              details=f"{interview.round_name} | status: {interview.status} | result: {interview.result or '—'}")

    return serialize(interview)


@router.post("/{interview_id}/send-invitation")
def send_interview_invitation(interview_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    referral = db.query(models.Referral).filter(models.Referral.id == interview.referral_id).first()
    job = db.query(models.Job).filter(models.Job.id == interview.job_id).first()

    candidate_name = referral.candidate_name if referral else interview.candidate_name
    candidate_email = referral.email if referral else ""
    job_title = job.title if job else "the role"

    if not candidate_email:
        raise HTTPException(status_code=400, detail="Candidate has no email address on file")

    meeting_info = ""
    if interview.meeting_link:
        meeting_info = f"Meeting Link: {interview.meeting_link}"
    elif interview.location:
        meeting_info = f"Location: {interview.location}"

    try:
        email_service.send_interview_invitation_email(
            candidate_email, candidate_name, job_title,
            interview.interview_date, interview.start_time or interview.interview_time if hasattr(interview, 'interview_time') else interview.start_time,
            meeting_info, interview.notes or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    log_activity(
        db, interview.referral_id,
        "Invitation Sent",
        f"{interview.round_name} invitation sent to {candidate_name}",
        user.name,
    )

    return {"ok": True, "message": f"Invitation sent to {candidate_email}"}


@router.post("/{interview_id}/create-teams-meeting")
def create_teams_meeting(interview_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Create (or re-use) a Microsoft Teams online meeting for an interview.

    Requires the acting HR user to have signed in via Microsoft SSO so we can
    act on their behalf (Graph OnlineMeetings.ReadWrite). If SSO tokens aren't
    available it returns a 409 with a helpful message instead of failing loudly.
    """
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    from .. import ms_graph
    if not ms_graph.available(user.id):
        raise HTTPException(
            status_code=409,
            detail="Teams integration is not connected. Sign in via 'Continue with Microsoft' once, then retry.",
        )

    referral = db.query(models.Referral).filter(models.Referral.id == interview.referral_id).first()
    job = db.query(models.Job).filter(models.Job.id == interview.job_id).first()
    subject = f"Interview: {interview.candidate_name} — {interview.round_name}"
    if job:
        subject += f" ({job.title})"

    attendee = None
    if referral and referral.email:
        attendee = referral.email

    meeting = ms_graph.create_online_meeting(
        user.id,
        subject=subject,
        start_dt=interview.interview_date,
        start_time=interview.start_time,
        end_time=interview.end_time,
        attendee_email=attendee,
    )

    interview.meeting_link = meeting["joinUrl"]
    interview.meeting_id = meeting["id"]
    db.commit()
    db.refresh(interview)

    log_activity(
        db, interview.referral_id,
        "Teams Meeting Created",
        f"Microsoft Teams meeting created for {interview.round_name} — {interview.meeting_link}",
        user.name,
    )
    log_audit(db, user, "Teams meeting created", target="interview", target_id=interview_id,
              details=f"{interview.candidate_name} | {interview.round_name} | {meeting['joinUrl']}")

    if attendee:
        try:
            email_service.send_interview_invitation_email(
                attendee, interview.candidate_name,
                job.title if job else "the role",
                interview.interview_date, interview.start_time or "",
                f"Meeting Link: {interview.meeting_link}", interview.notes or "",
            )
        except Exception:
            pass

    return serialize(interview)


class ScheduleTeamsIn(BaseModel):
    timezone: str = ""  # IANA timezone, e.g. "Asia/Kolkata". Sent by the browser.


def _resolve_participants(db: Session, interview: models.Interview):
    """Resolve the interviewer string into an organizer mailbox + attendee list.

    The interviewer field is free text ("Comma-separated names"). Each token is
    resolved to a mailbox: an explicit email is used as-is; otherwise we match
    against the Employee directory by name. The first resolvable interviewer
    becomes the calendar organizer (the meeting lands in their Outlook/Teams
    calendar); the rest become required attendees.
    """
    organizer = None
    attendees = []
    for token in (interview.interviewer or "").split(","):
        name = token.strip()
        if not name:
            continue
        if "@" in name:
            email = name.lower()
        else:
            emp = db.query(models.Employee).filter(models.Employee.name.ilike(name)).first()
            if not emp or not emp.email:
                emp = db.query(models.Employee).filter(
                    models.Employee.email.ilike(f"{name}@%"),
                    models.Employee.is_active == True,
                ).first()
            email = emp.email.lower() if emp and emp.email else None
        if not email:
            raise HTTPException(
                status_code=400,
                detail=(f"Interviewer '{name}' could not be matched to a mailbox. "
                        f"Add them as an Employee with a valid email, or enter their email address directly."),
            )
        if organizer is None:
            organizer = email
        else:
            attendees.append(email)
    if not organizer:
        raise HTTPException(
            status_code=400,
            detail="An interviewer is required to schedule a Teams interview.",
        )
    return organizer, attendees


@router.post("/{interview_id}/schedule-teams")
def schedule_teams_interview(interview_id: str, payload: ScheduleTeamsIn,
                             db: Session = Depends(get_db), user=Depends(require_hr)):
    """Automatically schedule a Teams interview using Microsoft Graph.

    Priority:
      1. Application (client-credentials) auth — works without any user sign-in.
      2. Delegated (SSO) auth — only if the HR user signed in via Microsoft.

    The operation is idempotent: if a calendar event was already created for
    this interview, the existing details are returned without creating a
    duplicate. No Azure secret is ever returned in the response.
    """
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # --- Idempotency: short-circuit if already scheduled on Graph ----------
    if interview.graph_event_id:
        return {
            **serialize(interview),
            "scheduled": True,
            "alreadyExisting": True,
            "teamsJoinUrl": interview.meeting_link,
            "calendarEventId": interview.graph_event_id,
            "organizer": "",
        }

    # --- Validation --------------------------------------------------------
    if not interview.interview_date:
        raise HTTPException(status_code=400, detail="Interview date is required before scheduling.")
    if not interview.start_time:
        raise HTTPException(status_code=400, detail="Interview start time is required before scheduling.")

    referral = db.query(models.Referral).filter(models.Referral.id == interview.referral_id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Candidate (referral) not found for this interview.")

    try:
        start_dt = _parse_time(interview.interview_date, interview.start_time)
    except Exception:
        raise HTTPException(status_code=400, detail="Interview date/time could not be parsed. Use YYYY-MM-DD and HH:MM.")
    if interview.end_time:
        try:
            end_dt = _parse_time(interview.interview_date, interview.end_time)
        except Exception:
            end_dt = start_dt + timedelta(minutes=45)
    else:
        end_dt = start_dt + timedelta(minutes=45)
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(minutes=45)

    timezone = (payload.timezone or "").strip() or "Asia/Kolkata"

    organizer, attendee_emails = _resolve_participants(db, interview)

    # --- Double-booking prevention: refresh calendar before final booking ---
    conflicts = _check_double_booking(
        db, interview.interviewer, interview.interview_date,
        interview.start_time, interview.end_time, exclude_id=interview_id,
    )
    if conflicts:
        details = "; ".join(
            f"{c['candidateName']} ({c['roundName']}) {c['startTime']}-{c['endTime']}"
            for c in conflicts[:3]
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Scheduling conflict detected during final check: the interviewer is no longer available. "
                f"Conflicts: {details}. Please refresh availability and choose a different time slot."
            ),
        )

    job = db.query(models.Job).filter(models.Job.id == interview.job_id).first()
    subject = f"Interview: {interview.candidate_name} — {interview.round_name}"
    if job:
        subject += f" ({job.title})"
    body = (f"Interview round: {interview.round_name}\n"
            f"Candidate: {interview.candidate_name}\n"
            f"Interviewer(s): {interview.interviewer}\n"
            f"Type: {interview.interview_type}\n")
    if interview.notes:
        body += f"Notes: {interview.notes}\n"

    # Candidate is an attendee too (if they have an email).
    all_attendees = list(attendee_emails)
    if referral.email:
        cand_email = referral.email.lower()
        if cand_email not in all_attendees and cand_email != organizer.lower():
            all_attendees.append(cand_email)

    # --- Scheduling path ---------------------------------------------------
    try:
        if ms_graph.app_configured():
            meeting = ms_graph.create_teams_interview(
                organizer_upn=organizer,
                subject=subject,
                start_dt=start_dt,
                end_dt=end_dt,
                timezone=timezone,
                attendee_emails=all_attendees,
                body=body,
            )
            auth_method = "application"
        elif ms_graph.available(user.id):
            # Delegated fallback: meeting is created in the HR user's own calendar.
            meeting_info = ms_graph.create_online_meeting(
                user.id, subject=subject,
                start_dt=interview.interview_date, start_time=interview.start_time,
                end_time=interview.end_time,
                attendee_email=organizer,
            )
            evt = ms_graph.create_calendar_event(
                user.id, subject=subject,
                start_dt=interview.interview_date, start_time=interview.start_time,
                end_time=interview.end_time, join_url=meeting_info["joinUrl"],
                attendee_email=organizer, body=body,
            )
            meeting = {
                "event_id": evt.get("id", ""),
                "web_link": evt.get("webLink", ""),
                "join_url": meeting_info["joinUrl"],
                "online_meeting_id": meeting_info["id"],
                "organizer": organizer,
            }
            auth_method = "delegated"
        else:
            missing = ms_graph.missing_app_config()
            raise HTTPException(
                status_code=409,
                detail=("Microsoft Graph integration is not configured. Set "
                        + ", ".join(missing)
                        + " in the backend .env for automatic scheduling, or sign in via "
                        "'Continue with Microsoft' for delegated access."),
            )
    except HTTPException:
        raise
    except RuntimeError as exc:
        # Secret-free, actionable error surfaced to the frontend.
        raise HTTPException(status_code=502, detail=str(exc))

    # --- Persist -----------------------------------------------------------
    interview.meeting_link = meeting["join_url"]
    interview.meeting_id = meeting["online_meeting_id"]
    interview.graph_event_id = meeting["event_id"]
    interview.timezone = timezone
    db.commit()
    db.refresh(interview)

    log_activity(
        db, interview.referral_id,
        "Teams Interview Scheduled",
        f"Microsoft Teams interview scheduled for {interview.round_name} "
        f"({interview.interview_date} {interview.start_time}) — organizer: {organizer}",
        user.name,
    )
    log_audit(db, user, "Teams interview scheduled", target="interview", target_id=interview_id,
              details=f"{interview.candidate_name} | {interview.round_name} | auth={auth_method} | {meeting['join_url']}")

    return {
        **serialize(interview),
        "scheduled": True,
        "alreadyExisting": False,
        "teamsJoinUrl": meeting["join_url"],
        "calendarEventId": meeting["event_id"],
        "calendarWebLink": meeting["web_link"],
        "organizer": organizer,
        "authMethod": auth_method,
        "attendees": all_attendees,
    }


@router.delete("/{interview_id}")
def delete_interview(interview_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Soft-delete an interview — hidden from calendars/lists but kept for audit."""
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    if interview.is_deleted:
        raise HTTPException(status_code=400, detail="This interview has already been deleted")

    referral_id = interview.referral_id
    round_name = interview.round_name
    interview.is_deleted = True
    interview.deleted_at = datetime.utcnow()
    interview.deleted_by = user.name
    db.commit()

    log_activity(
        db, referral_id,
        "Interview Deleted",
        f"{round_name} interview deleted",
        user.name,
    )
    log_audit(db, user, "Interview deleted (soft)", target="interview", target_id=interview_id,
              details=f"{round_name} | candidate: {interview.candidate_name}")

    return {"ok": True, "message": "Interview deleted. Record retained for audit."}
