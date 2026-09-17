import asyncio
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, ai_service, resume_parser
from ..auth import get_current_user, require_hr
from ..routers.notifications import create_notification
from ..routers.activity import log_activity
from .. import email_service
from .. import rag_service
from ..routers.emails import record_email
from ..routers.admin import log_audit
from ..routers.resumes import _mime_type
from ..shortlist import (
    shortlist_for_score,
    rank_label_for_score,
    AI_RECOMMENDED_REJECT,
    HR_REVIEW_PENDING,
)

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


def serialize(r: models.Referral, user=None):
    """Serialize a referral for the API.

    JD Match Score and the AI-shortlist review fields (which can echo match
    percentages) are exposed only to HR/admin roles. Employees, referrers and
    candidates never receive scoring data — enforced here on the backend, not
    just hidden in the UI.
    """
    score_visible = user is not None and rag_service.is_hr_role(user.role)

    data = {
        "id": r.id,
        "candidateName": r.candidate_name,
        "phone": r.phone,
        "email": r.email,
        "resumeText": r.resume_text,
        "resumeFileUrl": r.resume_file_url,
        "resumeFileName": r.resume_file_name,
        "linkedin": r.linkedin,
        "github": r.github,
        "portfolio": r.portfolio,
        "location": r.location,
        "expectedSalary": r.expected_salary,
        "noticePeriod": r.notice_period,
        "currentCompany": r.current_company,
        "currentDesignation": r.current_designation or "",
        "totalExperience": r.total_experience or "",
        "relevantExperience": r.relevant_experience or "",
        "skills": r.skills or [],
        "education": r.education or "",
        "certifications": r.certifications or [],
        "projects": r.projects or [],
        "relationship": r.relationship_to_referrer,
        "referredBy": r.referred_by,
        "jobId": r.job_id,
        "status": r.status,
        "submittedDate": r.submitted_date,
        "aiSummary": r.ai_summary,
        "missingSkills": r.missing_skills,
        "tags": r.tags,
        "fraudFlags": r.fraud_flags,
        "interviewPrediction": r.interview_prediction,
        "strengths": r.strengths or [],
        "weaknesses": r.weaknesses or [],
        "screening": r.screening or {},
        "isDeleted": bool(r.is_deleted),
        "deletedAt": r.deleted_at,
        "deletedBy": r.deleted_by or "",
        "autoRejected": bool(r.auto_rejected),
        "reviewStatus": r.review_status or "",
        "evaluationHistory": r.evaluation_history or [],
        "reviewDeadline": r.review_deadline,
        "lastReviewReminder": r.last_review_reminder,
        "rejectionConfirmedBy": r.rejection_confirmed_by or "",
        "rejectionConfirmedAt": r.rejection_confirmed_at,
        "rejectionEmailSent": bool(r.rejection_email_sent),
        "rejectionEmailSentAt": r.rejection_email_sent_at,
        "rejectionEmailStatus": r.rejection_email_status or "",
        "rejectionEmailError": r.rejection_email_error or "",
    }

    if score_visible:
        data.update({
            "matchPercent": r.match_percent,
            "originalMatch": r.original_match or 0,
            "rankLabel": r.rank_label or "",
            "recommendation": r.recommendation or "",
            "aiRecommendation": r.ai_recommendation or "",
            "rejectionReason": r.rejection_reason or "",
            "matchBreakdown": r.match_breakdown or {},
        })

    return data


def _append_history(referral, action, from_status, to_status, by="", reason="",
                    match_before=None, match_after=None, verdict=""):
    hist = list(referral.evaluation_history or [])
    hist.append({
        "action": action,
        "fromStatus": from_status,
        "toStatus": to_status,
        "by": by,
        "reason": reason,
        "matchBefore": match_before,
        "matchAfter": match_after,
        "verdict": verdict,
        "at": datetime.utcnow().isoformat(),
    })
    referral.evaluation_history = hist[-50:]


@router.get("")
def list_referrals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Role-scoped referral list.

    HR/admin see everything; managers see their own + team (same department);
    employees see only their own referrals.
    """
    refs = rag_service.scoped_referrals(db, user)
    refs = sorted(refs, key=lambda r: r.submitted_date, reverse=True)
    return [serialize(r, user) for r in refs]


@router.get("/pending-reviews")
def pending_reviews(db: Session = Depends(get_db), user=Depends(require_hr)):
    """Return referrals with active review deadlines for the dashboard."""
    now = datetime.utcnow()
    TERMINAL_STATUSES = {"Selected", "Rejected", "Offer", "Offer Released", "Joined"}
    refs = db.query(models.Referral).filter(
        models.Referral.is_deleted.is_(False),
        models.Referral.review_deadline.isnot(None),
        models.Referral.status.notin_(TERMINAL_STATUSES),
    ).all()

    due_today = []
    due_tomorrow = []
    due_this_week = []
    overdue = []

    for r in refs:
        if not r.review_deadline:
            continue
        days_left = (r.review_deadline - now).total_seconds() / 86400
        entry = {**serialize(r, user), "daysLeft": round(days_left, 1)}
        if days_left < 0:
            overdue.append(entry)
        elif days_left < 1:
            due_today.append(entry)
        elif days_left < 2:
            due_tomorrow.append(entry)
        elif days_left <= 7:
            due_this_week.append(entry)

    return {
        "dueToday": due_today,
        "dueTomorrow": due_tomorrow,
        "dueThisWeek": due_this_week,
        "overdue": overdue,
        "total": len(due_today) + len(due_tomorrow) + len(due_this_week) + len(overdue),
    }


@router.get("/mine")
def my_referrals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user.employee_id:
        return []
    q = db.query(models.Referral).filter(
        models.Referral.referred_by == user.employee_id,
        models.Referral.is_deleted.is_(False),
    ).order_by(models.Referral.submitted_date.desc())
    return [serialize(r, user) for r in q.all()]


@router.get("/check-duplicate")
def check_duplicate(email: str = "", phone: str = "", name: str = "",
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(models.Referral)
    match = None
    for r in q.all():
        if email and r.email and r.email.lower() == email.lower():
            match = r
            break
        if phone and r.phone and r.phone.replace(" ", "") == phone.replace(" ", ""):
            match = r
            break
        if name and r.candidate_name.lower() == name.lower():
            match = r
            break
    if not match:
        return {"duplicate": False}
    referrer = db.query(models.Employee).filter(models.Employee.id == match.referred_by).first()
    return {
        "duplicate": True,
        "candidateName": match.candidate_name,
        "referredByName": referrer.name if referrer else None,
        "submittedDate": match.submitted_date,
    }


@router.post("")
async def create_referral(payload: schemas.ReferralIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user.employee_id:
        raise HTTPException(status_code=400, detail="Only employee accounts can submit referrals")

    job = db.query(models.Job).filter(models.Job.id == payload.jobId).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_deleted or job.status != "Open":
        raise HTTPException(status_code=400, detail="This position is no longer open for referrals")

    referral = models.Referral(
        candidate_name=payload.candidateName,
        phone=payload.phone,
        email=payload.email,
        resume_text=payload.resumeText or "No resume text provided.",
        resume_file_url=payload.resumeFileUrl,
        resume_file_name=payload.resumeFileName,
        linkedin=payload.linkedin,
        github=payload.github,
        portfolio=payload.portfolio,
        location=payload.location,
        expected_salary=payload.expectedSalary,
        notice_period=payload.noticePeriod,
        current_company=payload.currentCompany,
        current_designation=payload.currentDesignation,
        total_experience=payload.totalExperience,
        relevant_experience=payload.relevantExperience,
        skills=payload.skills,
        education=payload.education,
        certifications=payload.certifications,
        projects=payload.projects,
        relationship_to_referrer=payload.relationship,
        referred_by=user.employee_id,
        job_id=payload.jobId,
        status="Submitted",
        submitted_date=datetime.utcnow(),
        review_deadline=datetime.utcnow() + timedelta(days=7),
        match_percent=0,
        interview_prediction={"chance": 60, "reasons": []},
    )

    db.add(referral)
    db.commit()
    db.refresh(referral)

    # Best-effort AI enrichment runs in background (non-blocking)
    import asyncio as _bg_asyncio
    async def _enrich(referral_id, resume_text, job_dict):
        from ..database import SessionLocal
        _db = SessionLocal()
        try:
            _ref = _db.query(models.Referral).filter(models.Referral.id == referral_id).first()
            if not _ref:
                return
            _job_row = (
                _db.query(models.Job).filter(models.Job.id == _ref.job_id).first()
                if _ref.job_id else None
            )
            try:
                _rag_ctx = rag_service.jd_context(_db, _job_row, resume_text)
            except Exception:
                _rag_ctx = ""
            summary, tags, fraud, prediction, match_detail = await _bg_asyncio.gather(
                ai_service.ai_summary(resume_text),
                ai_service.ai_auto_tags(resume_text),
                ai_service.ai_fraud_check(resume_text),
                ai_service.ai_interview_prediction(resume_text, job_dict),
                ai_service.ai_match_job(resume_text, job_dict, _rag_ctx),
                return_exceptions=True,
            )
            if isinstance(summary, dict):
                _ref.ai_summary = summary.get("summary", "")
            if isinstance(tags, list) and tags:
                _ref.tags = tags
            if isinstance(fraud, dict):
                _ref.fraud_flags = fraud.get("flags", [])
            if isinstance(prediction, dict):
                _ref.interview_prediction = prediction
            if isinstance(match_detail, dict):
                _ref.match_percent = match_detail.get("jd_vs_resume_match", _ref.match_percent)
                _ref.missing_skills = match_detail.get("missing_skills", [])
                _ref.recommendation = match_detail.get("recommendation", _ref.recommendation)
                _new_match = _ref.match_percent or 0
                _ref.original_match = _ref.original_match or _new_match
                _ref.rank_label = rank_label_for_score(_new_match)
                _ref.match_breakdown = match_detail.get("match_breakdown", {}) or {}
                _decision = shortlist_for_score(_new_match)
                # HR-controlled rejection: the AI only recommends; no rejection
                # email is sent until HR confirms via /confirm-rejection.
                if _decision["verdict"] == "ai_recommended_reject":
                    _ref.status = AI_RECOMMENDED_REJECT
                    _ref.ai_recommendation = "ai_recommended_reject"
                    _ref.auto_rejected = False
                    _ref.review_status = HR_REVIEW_PENDING
            _db.commit()
        except Exception:
            pass
        finally:
            _db.close()

    job_dict = {"id": job.id, "title": job.title, "skills": job.skills, "description": job.description, "exp": job.exp} if job else {}
    try:
        loop = _bg_asyncio.get_event_loop()
        if loop.is_running():
            _bg_asyncio.ensure_future(_enrich(referral.id, referral.resume_text, job_dict))
        else:
            loop.create_task(_enrich(referral.id, referral.resume_text, job_dict))
    except Exception:
        pass

    # Notify all HR users
    hr_users = db.query(models.User).filter(models.User.role.in_(["hr", "admin"])).all()
    for hr in hr_users:
        create_notification(db, hr.id, "New Referral Submitted",
                          f"{user.name} referred {payload.candidateName} for {job.title}",
                          "info", "referral")

    # Email referrer
    try:
        email_service.send_referral_submitted_email(user.email, user.name, payload.candidateName, job.title)
    except Exception:
        pass

    return serialize(referral, user)


@router.patch("/{referral_id}/status")
def update_status(referral_id: str, payload: schemas.ReferralStatusUpdate,
                   db: Session = Depends(get_db), user=Depends(require_hr)):
    referral = db.query(models.Referral).filter(models.Referral.id == referral_id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    old_status = referral.status
    if old_status == payload.status:
        return serialize(referral, user)

    # Guard: prevent bypassing the HR-confirmed auto-rejection workflow.
    # Candidates in 'Auto-Reject Recommended' must go through the
    # /confirm-rejection endpoint, not the generic PATCH status route.
    if old_status == AI_RECOMMENDED_REJECT and payload.status == "Rejected":
        raise HTTPException(
            status_code=400,
            detail="Use the Confirm Auto-Rejection workflow to reject this candidate. "
                   "Direct status change to Rejected is not allowed from Auto-Reject Recommended."
        )

    referral.status = payload.status

    # Stop review reminders when referral reaches a terminal status
    TERMINAL_STATUSES = {"Selected", "Rejected", "Offer", "Offer Released", "Joined"}
    if payload.status in TERMINAL_STATUSES:
        referral.review_deadline = None
        referral.last_review_reminder = None

    # Moving away from Auto-Reject Recommended clears the pending recommendation
    if old_status == AI_RECOMMENDED_REJECT and payload.status != AI_RECOMMENDED_REJECT:
        referral.ai_recommendation = ""
        referral.review_status = ""

    # Moving to Auto-Reject Recommended sets the pending AI recommendation
    if payload.status == AI_RECOMMENDED_REJECT:
        referral.ai_recommendation = "ai_recommended_reject"
        referral.review_status = HR_REVIEW_PENDING
        referral.auto_rejected = False

    # Manual rejection vs AI auto-reject provenance
    if payload.status == "Rejected":
        referral.auto_rejected = False
        referral.review_status = "REJECTED"
        if not referral.rejection_reason:
            referral.rejection_reason = f"Manually rejected by {user.name}."

    # Moving out of Rejected is an HR override of the AI decision
    if old_status == "Rejected":
        _append_history(referral, "HR override", old_status, payload.status,
                        by=user.name, reason="HR overrode the rejection decision.",
                        match_before=referral.original_match or referral.match_percent,
                        match_after=referral.match_percent)

    db.commit()
    db.refresh(referral)

    # Log activity
    log_activity(db, referral_id, f"Status changed to {payload.status}",
                 f"Status changed from {old_status} to {payload.status} by {user.name}",
                 user.name)

    # Audit log
    from .admin import log_audit
    log_audit(db, user, f"Referral status: {old_status} -> {payload.status}",
              target="referral", target_id=referral_id,
              details=f"Candidate: {referral.candidate_name}")

    # Auto-create interview record when moving to interview stages
    interview_rounds = ["Technical Round", "Manager Round", "HR Round", "HR Screening",
                        "Technical Round 1", "Technical Round 2", "Director Round", "HR Final Discussion"]
    if payload.status in interview_rounds:
        existing = db.query(models.Interview).filter(
            models.Interview.referral_id == referral_id,
            models.Interview.round_name == payload.status
        ).first()
        if not existing:
            interview = models.Interview(
                referral_id=referral_id,
                job_id=referral.job_id,
                candidate_name=referral.candidate_name,
                round_name=payload.status,
                status="Scheduled",
            )
            db.add(interview)
            db.commit()

    # Find referrer's user account for notification
    job = db.query(models.Job).filter(models.Job.id == referral.job_id).first()
    job_title = job.title if job else "the role"
    referrer_emp = db.query(models.Employee).filter(models.Employee.id == referral.referred_by).first()
    if referrer_emp:
        referrer_user = db.query(models.User).filter(models.User.employee_id == referrer_emp.id).first()
        if referrer_user:
            create_notification(db, referrer_user.id, f"Referral Update — {referral.candidate_name}",
                              f"Status changed from {old_status} to {payload.status}",
                              "success" if payload.status in ("Offer", "Joined") else "info",
                              "referral", f"/tracking")
            try:
                email_service.send_referral_status_email(referrer_user.email, referral.candidate_name,
                                                        payload.status, job_title)
            except Exception:
                pass

            if payload.status in ("Interview", "Technical Round", "Manager Round", "HR Round"):
                try:
                    email_service.send_interview_scheduled_email(referrer_user.email, referral.candidate_name,
                                                                job_title, payload.status)
                except Exception:
                    pass
            elif payload.status == "Offer":
                try:
                    email_service.send_offer_email(referrer_user.email, referral.candidate_name, job_title)
                except Exception:
                    pass
            elif payload.status == "Joined":
                bonus_amount = job.bonus if job else 0
                if bonus_amount > 0:
                    try:
                        email_service.send_bonus_credited_email(referrer_user.email, referrer_user.name, bonus_amount, referral.candidate_name)
                    except Exception:
                        pass
                    create_notification(db, referrer_user.id, f"Referral Bonus Credited",
                                      f"A bonus of ₹{bonus_amount:,} has been credited for {referral.candidate_name}",
                                      "success", "bonus", "/rewards")

    if payload.status == "Submitted":
        log_activity(db, referral_id, "Referral submitted",
                     f"Referral submitted by {user.name}", user.name)
    elif payload.status in ("Shortlisted", "Resume Screening", "Interview Scheduled", "Interview Completed", "Selected", "Offer Released", "Rejected", "Offer", "Joined"):
        from .emails import record_email
        if referral.email:
            try:
                if payload.status in ("Shortlisted", "Interview Scheduled", "Interview Completed", "Selected", "Offer Released"):
                    if payload.status == "Selected":
                        email_service.send_selection_email(referral.email, referral.candidate_name, job_title)
                    else:
                        email_service.send_interview_scheduled_email(
                            referral.email, referral.candidate_name, job_title, payload.status)
                    record_email(db, referral.email, f"Referral Update — {referral.candidate_name}",
                                 f"Your application status for {job_title} is now: {payload.status}.",
                                 "automated", "shortlist", "sent", referral_id=referral_id, job_id=referral.job_id or "",
                                 created_by=f"{user.name} ({user.role})")
            except Exception:
                pass
        if payload.status == "Offer" and referral.email:
            try:
                email_service.send_offer_email(referral.email, referral.candidate_name, job_title)
                record_email(db, referral.email, f"Offer Extended — {referral.candidate_name}",
                             f"An offer has been extended to {referral.candidate_name} for the {job_title} position.",
                             "automated", "offer", "sent", referral_id=referral_id, job_id=referral.job_id or "",
                             created_by=f"{user.name} ({user.role})")
            except Exception:
                pass
        elif payload.status == "Rejected" and referral.email:
            try:
                email_service.send_rejection_email(referral.email, referral.candidate_name, job_title)
                record_email(db, referral.email, f"Referral Update — {referral.candidate_name}",
                             f"Unfortunately, {referral.candidate_name}'s application for {job_title} was not successful this time.",
                             "automated", "rejection", "sent", referral_id=referral_id, job_id=referral.job_id or "",
                             created_by=f"{user.name} ({user.role})")
            except Exception:
                pass
        elif payload.status == "Joined" and referral.email:
            try:
                email_service.send_joining_confirmation_email(referral.email, referral.candidate_name, job_title)
                record_email(db, referral.email, f"Joining Confirmation — {referral.candidate_name}",
                             f"{referral.candidate_name} has officially joined the team for the {job_title} position.",
                             "automated", "joining", "sent", referral_id=referral_id, job_id=referral.job_id or "",
                             created_by=f"{user.name} ({user.role})")
            except Exception:
                pass

    return serialize(referral, user)


# ---------------------------------------------------------------------------
# HR-Confirmed Auto-Rejection Workflow
# ---------------------------------------------------------------------------

@router.post("/{referral_id}/confirm-rejection")
def confirm_rejection(referral_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    """HR explicitly confirms auto-rejection and triggers the rejection email.

    This is the ONLY path that sends a rejection email for AI-recommended
    rejections. Uses database-level locking to prevent race conditions and
    duplicate emails.
    """
    from sqlalchemy import text as sql_text

    # Lock the row within a transaction to prevent concurrent confirmations
    referral = db.query(models.Referral).filter(
        models.Referral.id == referral_id
    ).with_for_update().first()

    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    # Verify the candidate is eligible for HR rejection confirmation
    if referral.status != AI_RECOMMENDED_REJECT:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate is not in 'Auto-Reject Recommended' status (current: {referral.status})."
        )

    # Prevent duplicate confirmation
    if referral.rejection_confirmed_by:
        raise HTTPException(
            status_code=400,
            detail="Rejection has already been confirmed."
        )

    # Prevent duplicate email sending
    if referral.rejection_email_sent:
        raise HTTPException(
            status_code=400,
            detail="Rejection has already been confirmed and the email was already sent."
        )

    # Update candidate status to Rejected (source of truth — backend only)
    old_status = referral.status
    referral.status = "Rejected"
    referral.auto_rejected = True
    referral.ai_recommendation = ""
    referral.review_status = "REJECTED"
    referral.rejection_confirmed_by = user.name
    referral.rejection_confirmed_at = datetime.utcnow()
    referral.review_deadline = None
    referral.last_review_reminder = None

    # Append to evaluation history
    _append_history(
        referral, "HR confirmed rejection", old_status, "Rejected",
        by=user.name,
        reason=f"HR confirmed AI auto-rejection recommendation.",
        match_before=referral.original_match or referral.match_percent,
        match_after=referral.match_percent,
    )

    db.commit()
    db.refresh(referral)

    # Log activity
    log_activity(db, referral_id, "HR confirmed rejection",
                 f"HR ({user.name}) confirmed AI auto-rejection recommendation for {referral.candidate_name}.",
                 user.name)

    from .admin import log_audit
    log_audit(db, user, "HR confirmed auto-rejection",
              target="referral", target_id=referral_id,
              details=f"Candidate: {referral.candidate_name} | match {referral.match_percent}%")

    # Send rejection email
    job = db.query(models.Job).filter(models.Job.id == referral.job_id).first()
    job_title = job.title if job else "the role"
    email_ok = False
    email_error = ""

    if referral.email:
        try:
            email_service.send_rejection_email(referral.email, referral.candidate_name, job_title)
            email_ok = True
            referral.rejection_email_sent = True
            referral.rejection_email_sent_at = datetime.utcnow()
            referral.rejection_email_status = "sent"
            referral.rejection_email_error = ""
            db.commit()
            db.refresh(referral)

            from .emails import record_email
            record_email(db, referral.email, f"Referral Update — {referral.candidate_name}",
                         f"Unfortunately, {referral.candidate_name}'s application for {job_title} was not successful this time.",
                         "automated", "rejection", "sent", referral_id=referral_id, job_id=referral.job_id or "",
                         created_by=f"{user.name} ({user.role})")

            log_activity(db, referral_id, "Rejection email sent",
                         f"Rejection email sent to {referral.email} for {referral.candidate_name}.",
                         user.name)
        except Exception as exc:
            email_error = str(exc)
            referral.rejection_email_sent = False
            referral.rejection_email_status = "failed"
            referral.rejection_email_error = email_error
            db.commit()
            db.refresh(referral)

            log_activity(db, referral_id, "Rejection email failed",
                         f"Rejection email to {referral.email} failed: {email_error}",
                         user.name)
    else:
        referral.rejection_email_status = "no_email"
        referral.rejection_email_error = "No email address on file."
        db.commit()
        db.refresh(referral)

    # Notify referrer
    referrer_emp = db.query(models.Employee).filter(models.Employee.id == referral.referred_by).first()
    if referrer_emp:
        referrer_user = db.query(models.User).filter(models.User.employee_id == referrer_emp.id).first()
        if referrer_user:
            create_notification(db, referrer_user.id, f"Referral Rejected — {referral.candidate_name}",
                                f"Status changed from {old_status} to Rejected by {user.name}.",
                                "warning", "referral", "/tracking")
            try:
                email_service.send_rejection_email(referrer_user.email, referral.candidate_name, job_title)
            except Exception:
                pass

    if email_ok:
        return {
            "success": True,
            "status": "Rejected",
            "email_status": "sent",
            "message": "Candidate rejected and rejection email sent successfully.",
            "referral": serialize(referral, user),
        }
    else:
        return {
            "success": True,
            "status": "Rejected",
            "email_status": "failed",
            "message": "Candidate rejected, but the rejection email could not be sent. Please retry the email.",
            "emailError": email_error,
            "referral": serialize(referral, user),
        }


@router.post("/{referral_id}/move-to-review")
def move_to_review(referral_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    """HR moves a candidate from Auto-Reject Recommended to review.

    Removes the pending auto-rejection state without sending any email.
    The original AI recommendation is preserved in evaluation_history.
    """
    referral = db.query(models.Referral).filter(
        models.Referral.id == referral_id
    ).with_for_update().first()

    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    if referral.status != AI_RECOMMENDED_REJECT:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate is not in 'Auto-Reject Recommended' status (current: {referral.status})."
        )

    old_status = referral.status
    referral.status = "Under Review"
    referral.ai_recommendation = ""
    referral.auto_rejected = False
    referral.review_status = "HR_REVIEWED"

    _append_history(
        referral, "HR moved to review", old_status, "Under Review",
        by=user.name,
        reason="HR chose to review the candidate instead of confirming rejection.",
        match_before=referral.original_match or referral.match_percent,
        match_after=referral.match_percent,
    )

    db.commit()
    db.refresh(referral)

    log_activity(db, referral_id, "HR moved candidate to review",
                 f"HR ({user.name}) moved {referral.candidate_name} from Auto-Reject Recommended to Under Review.",
                 user.name)

    from .admin import log_audit
    log_audit(db, user, "HR moved candidate to review",
              target="referral", target_id=referral_id,
              details=f"Candidate: {referral.candidate_name} | Auto-Reject Recommended -> Under Review")

    return serialize(referral, user)


@router.post("/{referral_id}/retry-rejection-email")
def retry_rejection_email(referral_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Retry sending the rejection email for a candidate whose rejection was
    confirmed but the email failed to send.

    Prevents duplicate emails after successful delivery.
    """
    referral = db.query(models.Referral).filter(
        models.Referral.id == referral_id
    ).with_for_update().first()

    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    if referral.status != "Rejected":
        raise HTTPException(
            status_code=400,
            detail=f"Candidate is not rejected (current: {referral.status})."
        )

    if referral.rejection_email_sent:
        raise HTTPException(
            status_code=400,
            detail="Rejection email was already sent successfully."
        )

    if not referral.rejection_confirmed_by:
        raise HTTPException(
            status_code=400,
            detail="Rejection has not been confirmed by HR yet."
        )

    job = db.query(models.Job).filter(models.Job.id == referral.job_id).first()
    job_title = job.title if job else "the role"

    if not referral.email:
        referral.rejection_email_status = "no_email"
        referral.rejection_email_error = "No email address on file."
        db.commit()
        db.refresh(referral)
        raise HTTPException(status_code=400, detail="No email address on file for this candidate.")

    try:
        email_service.send_rejection_email(referral.email, referral.candidate_name, job_title)
        referral.rejection_email_sent = True
        referral.rejection_email_sent_at = datetime.utcnow()
        referral.rejection_email_status = "sent"
        referral.rejection_email_error = ""
        db.commit()
        db.refresh(referral)

        from .emails import record_email
        record_email(db, referral.email, f"Referral Update — {referral.candidate_name}",
                     f"Unfortunately, {referral.candidate_name}'s application for {job_title} was not successful this time.",
                     "automated", "rejection", "sent", referral_id=referral_id, job_id=referral.job_id or "",
                     created_by=f"{user.name} ({user.role})")

        log_activity(db, referral_id, "Rejection email retried and sent",
                     f"Rejection email resent to {referral.email} for {referral.candidate_name}.",
                     user.name)

        return {
            "success": True,
            "email_status": "sent",
            "message": "Rejection email sent successfully.",
            "referral": serialize(referral, user),
        }
    except Exception as exc:
        referral.rejection_email_status = "failed"
        referral.rejection_email_error = str(exc)
        db.commit()
        db.refresh(referral)

        log_activity(db, referral_id, "Rejection email retry failed",
                     f"Rejection email retry to {referral.email} failed: {exc}",
                     user.name)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to send rejection email: {exc}"
        )


@router.delete("/{referral_id}")
def delete_referral(referral_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Soft-delete a referral (audit-safe).

    - Employees may withdraw their own referrals, but only while they are still
      in 'Submitted' / 'Applied' (no interviews/history to preserve).
    - HR / admin may soft-delete any referral at any stage. The row is hidden
      from all lists/reports but kept in the database for audit purposes.
    """
    referral = db.query(models.Referral).filter(models.Referral.id == referral_id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")
    if referral.is_deleted:
        raise HTTPException(status_code=400, detail="This referral has already been deleted")

    is_hr = user.role in ("hr", "hr_manager", "chro", "vp", "cto", "ceo", "system_admin", "admin")
    if not is_hr and referral.referred_by != user.employee_id:
        raise HTTPException(status_code=403, detail="You can only delete your own referrals")
    if not is_hr and referral.status not in ("Submitted", "Applied"):
        raise HTTPException(status_code=400, detail=f"Cannot delete a referral with status '{referral.status}'. Only referrals in 'Submitted' or 'Applied' status can be withdrawn.")

    candidate_name = referral.candidate_name
    from .admin import log_audit

    if is_hr:
        referral.is_deleted = True
        referral.deleted_at = datetime.utcnow()
        referral.deleted_by = user.name
        db.commit()
        log_audit(db, user, "Referral deleted (soft)",
                  target="referral", target_id=referral_id,
                  details=f"Candidate: {candidate_name} | status at delete: {referral.status}")
        return {"ok": True, "message": "Referral deleted. Record retained for audit."}

    # Employee self-withdrawal — hard delete (no history yet), as before
    db.query(models.ActivityLog).filter(models.ActivityLog.referral_id == referral_id).delete(synchronize_session=False)
    db.query(models.Interview).filter(models.Interview.referral_id == referral_id).delete(synchronize_session=False)
    db.commit()
    log_audit(db, user, "Referral withdrawn",
              target="referral", target_id=referral_id,
              details=f"Candidate: {candidate_name}")
    db.delete(referral)
    db.commit()
    return {"ok": True, "message": "Referral withdrawn successfully"}


@router.post("/{referral_id}/reanalyze")
async def reanalyze_referral(referral_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Re-run the full AI resume evaluation for a referral (resume re-evaluation).

    Recomputes summary, quality scores, tags, fraud flags, interview prediction,
    job match, missing skills and the AI shortlist verdict. If the candidate was
    auto-rejected and now scores above the reject threshold, the referral is
    re-opened so HR can move it forward — this powers the 'Reopen AI decision'
    flow from the shortlisting screen.
    """
    referral = db.query(models.Referral).filter(models.Referral.id == referral_id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")
    if not referral.resume_text and not referral.resume_file_url:
        raise HTTPException(status_code=400, detail="This referral has no resume text to re-evaluate")

    # Re-run OCR from the stored resume file (best-effort) so edits to the file are picked up.
    if referral.resume_file_url and referral.resume_file_url.startswith("/api/resumes/file/"):
        file_key = referral.resume_file_url.rsplit("/", 1)[-1]
        stored = db.query(models.ResumeFile).filter(models.ResumeFile.id == file_key).first()
        if stored:
            try:
                fresh_text = resume_parser.extract_text(stored.file_name, stored.file_data)
                if fresh_text and len(fresh_text.strip()) > 20:
                    referral.resume_text = fresh_text
            except Exception:
                pass

    job = db.query(models.Job).filter(models.Job.id == referral.job_id).first()
    job_dict = {"id": job.id, "title": job.title, "skills": job.skills,
                "description": job.description, "exp": job.exp} if job else {}
    try:
        rag_ctx = rag_service.jd_context(db, job, referral.resume_text)
    except Exception:
        rag_ctx = ""

    summary, tags, fraud, prediction, match_detail = await asyncio.gather(
        ai_service.ai_summary(referral.resume_text),
        ai_service.ai_auto_tags(referral.resume_text),
        ai_service.ai_fraud_check(referral.resume_text),
        ai_service.ai_interview_prediction(referral.resume_text, job_dict),
        ai_service.ai_match_job(referral.resume_text, job_dict, rag_ctx),
        return_exceptions=True,
    )

    previous = dict(
        match=referral.match_percent,
        status=referral.status,
        rank=referral.rank_label,
    )

    if isinstance(summary, dict):
        referral.ai_summary = summary.get("summary", referral.ai_summary)
    if isinstance(tags, list) and tags:
        referral.tags = tags
    if isinstance(fraud, dict):
        referral.fraud_flags = fraud.get("flags", referral.fraud_flags)
    if isinstance(prediction, dict):
        referral.interview_prediction = prediction
    if isinstance(match_detail, dict):
        referral.match_percent = match_detail.get("jd_vs_resume_match", referral.match_percent)
        referral.missing_skills = match_detail.get("missing_skills", [])
        referral.recommendation = match_detail.get("recommendation", referral.recommendation)
        referral.rank_label = rank_label_for_score(referral.match_percent or 0)
        referral.match_breakdown = match_detail.get("match_breakdown", {}) or {}
        referral.original_match = referral.original_match or referral.match_percent or 0

    # Refresh the candidate passport (employment gaps, duplicates, credibility, risk).
    try:
        from .. import screening as screening_mod
        referral.screening = screening_mod.deep_screen(db, referral)
    except Exception:
        pass

    was_recommended = referral.status == AI_RECOMMENDED_REJECT
    was_confirmed_rejected = referral.status == "Rejected"
    new_match = referral.match_percent or 0
    decision = shortlist_for_score(new_match)

    # HR-controlled rejection: below the bar always stays pending — the AI never
    # rejects on its own. Previously recommended or confirmed candidates are only
    # re-opened for HR when the re-run clears the bar.
    reopened = False
    if decision["verdict"] == "ai_recommended_reject":
        referral.ai_recommendation = "ai_recommended_reject"
        referral.auto_rejected = False
        if was_recommended:
            referral.review_status = HR_REVIEW_PENDING
        elif not was_confirmed_rejected:
            referral.status = AI_RECOMMENDED_REJECT
            referral.review_status = HR_REVIEW_PENDING
    elif was_recommended or was_confirmed_rejected:
        referral.status = "Under Review"
        referral.ai_recommendation = ""
        referral.auto_rejected = False
        referral.review_status = "HR_REVIEWED"
        reopened = True
        log_activity(db, referral.id, "AI decision reopened",
                     f"Re-evaluation scored {new_match}% (was auto-rejected) — candidate reopened by {user.name}.",
                     user.name)
    else:
        referral.ai_recommendation = decision["verdict"]
        referral.review_status = ""

    _append_history(
        referral, "AI re-evaluation", previous["status"], referral.status,
        by=user.name,
        reason=f"Re-run of OCR + JD matching + AI score + passport.",
        match_before=previous["match"], match_after=new_match, verdict=decision["category"],
    )

    db.commit()
    db.refresh(referral)

    from .admin import log_audit
    log_audit(db, user, "Referral re-evaluated (AI)",
              target="referral", target_id=referral_id,
              details=f"Candidate: {referral.candidate_name} | match {previous['match']}% -> {new_match}% | "
                      f"status: {previous['status']} -> {referral.status} | verdict: {decision['category']}")

    return {
        "referral": serialize(referral, user),
        "verdict": decision,
        "previous": previous,
        "reopened": reopened,
    }


@router.post("/{referral_id}/override")
def override_decision(referral_id: str, payload: schemas.OverrideDecisionIn,
                      db: Session = Depends(get_db), user=Depends(require_hr)):
    """HR manually overrides the AI decision and moves the candidate to a stage."""
    allowed = {"Resume Screening", "Under Review", "Shortlisted", "Interview Scheduled",
               "Interview Completed", "Selected", "Offer Released", "Joined", "Rejected"}
    target = payload.targetStatus.strip()
    if target not in allowed:
        raise HTTPException(status_code=422, detail=f"Unsupported target status '{target}'")

    referral = db.query(models.Referral).filter(models.Referral.id == referral_id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    old_status = referral.status
    _append_history(
        referral, "HR override", old_status, target,
        by=user.name, reason=payload.reason or "HR manually overrode the AI decision.",
        match_before=referral.original_match or referral.match_percent,
        match_after=referral.match_percent,
    )
    referral.status = target
    if target == "Rejected":
        referral.auto_rejected = False
        referral.review_status = "REJECTED"
        referral.rejection_confirmed_by = user.name
        referral.rejection_confirmed_at = datetime.utcnow()
        if not referral.rejection_reason:
            referral.rejection_reason = f"Manually rejected by {user.name}."
    else:
        referral.review_status = ""
        if old_status == AI_RECOMMENDED_REJECT:
            referral.ai_recommendation = ""
            referral.auto_rejected = False

    db.commit()
    db.refresh(referral)

    log_activity(db, referral.id, "HR override AI decision",
                 f"AI decision overridden: {old_status} -> {target} by {user.name}."
                 f"{(' Reason: ' + payload.reason) if payload.reason else ''}",
                 user.name)

    from .admin import log_audit
    log_audit(db, user, "HR override AI decision",
              target="referral", target_id=referral_id,
              details=f"Candidate: {referral.candidate_name} | {old_status} -> {target}"
                      f"{(' | ' + payload.reason) if payload.reason else ''}")

    return serialize(referral, user)


@router.get("/{referral_id}")
def get_referral(referral_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    referral = db.query(models.Referral).filter(models.Referral.id == referral_id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")
    if not rag_service.is_hr_role(user.role):
        if referral.referred_by != user.employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own referrals")
    return serialize(referral, user)


@router.post("/{referral_id}/send-email")
def send_referral_email(referral_id: str, payload: schemas.ReferralEmailSendIn,
                        db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Send the generated referral mail for a candidate from the configured
    Microsoft Graph mailbox, optionally attaching the stored resume.

    Access mirrors GET /{referral_id}: HR roles may send for any referral;
    employees/referrers may send only for their own referrals. Every attempt is
    recorded in email_history (category "ai", type "referral-mail") and logged
    to audit + activity feeds.
    """
    referral = db.query(models.Referral).filter(models.Referral.id == referral_id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")
    if not rag_service.is_hr_role(user.role):
        if referral.referred_by != user.employee_id:
            raise HTTPException(status_code=403, detail="You can only send email for your own referrals")

    status = email_service.get_email_status()
    from_email = status.get("sender", "")
    if not from_email:
        raise HTTPException(
            status_code=400,
            detail="No sending mailbox is configured. Set GRAPH_SENDER_EMAIL in the backend .env.",
        )

    attachments = []
    if payload.attachResume and referral.resume_file_url and referral.resume_file_url.startswith("/api/resumes/file/"):
        file_key = referral.resume_file_url.rsplit("/", 1)[-1]
        stored = db.query(models.ResumeFile).filter(models.ResumeFile.id == file_key).first()
        if stored and stored.file_data:
            ext = os.path.splitext(stored.file_name or "")[1].lower()
            attachments.append({
                "filename": stored.file_name or ("resume" + (ext or ".pdf")),
                "content_bytes": stored.file_data,
                "content_type": _mime_type(ext),
            })

    result = email_service.send_email_direct(
        to_emails=[str(e) for e in payload.to],
        cc_emails=[str(e) for e in payload.cc],
        bcc_emails=[str(e) for e in payload.bcc],
        subject=payload.subject,
        body=email_service.plain_to_html(payload.body),
        from_name=user.name,
        attachments=attachments,
    )
    sent_status = result.get("sent", 0) > 0
    cc = ", ".join([str(e) for e in payload.cc])
    bcc = ", ".join([str(e) for e in payload.bcc])
    for to in payload.to:
        record_email(
            db, str(to), payload.subject, payload.body, "ai", "referral-mail",
            "sent" if sent_status else "failed",
            error="" if sent_status else result.get("message", ""),
            cc=cc, bcc=bcc, referral_id=referral.id, job_id=referral.job_id or "",
            created_by=f"{user.name} ({user.role})",
        )

    job = db.query(models.Job).filter(models.Job.id == referral.job_id).first()
    job_title = job.title if job else ""
    log_audit(db, user, "Referral email sent", target="referral", target_id=referral.id,
              details=f"{len(payload.to)} recipient(s){f' for {job_title}' if job_title else ''}: {payload.subject}")
    log_activity(db, referral.id, "Referral email sent",
                 f"Referral email sent to {', '.join(str(e) for e in payload.to)} by {user.name}",
                 user.name)

    if not sent_status:
        raise HTTPException(status_code=500, detail="Failed to send referral email. Please try again.")

    return {
        "ok": True,
        "sent": result.get("sent", 0),
        "failed": result.get("failed", 0),
        "message": result.get("message", ""),
        "from": from_email,
        "tracked": True,
        "attachments": len(attachments),
    }
