"""Email Center backend.

Provides delivery-tracked email sending for the Email Center UI:
  - single / group sends (recorded in email_history)
  - bulk campaigns filtered from live candidate data (status/job/dept/match)
  - AI-generated email composition (delegates to the shared AI composer)
  - email history with sent / scheduled / failed statuses
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user, require_hr
from .. import email_service
from ..routers.admin import log_audit

router = APIRouter(prefix="/api/emails", tags=["emails"])


def record_email(db: Session, to_email: str, subject: str, body: str, category: str,
                 email_type: str, status: str, error: str = "",
                 cc: str = "", bcc: str = "", referral_id: str = "", job_id: str = "",
                 created_by: str = "", schedule_for: str = "") -> models.EmailRecord:
    rec = models.EmailRecord(
        to_email=to_email,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        category=category,
        email_type=email_type,
        status=status,
        error=error,
        referral_id=referral_id or "",
        job_id=job_id or "",
        created_by=created_by,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _serialize(rec: models.EmailRecord) -> dict:
    return {
        "id": rec.id,
        "toEmail": rec.to_email,
        "cc": rec.cc,
        "bcc": rec.bcc,
        "subject": rec.subject,
        "body": rec.body,
        "category": rec.category,
        "emailType": rec.email_type,
        "status": rec.status,
        "error": rec.error,
        "referralId": rec.referral_id,
        "jobId": rec.job_id,
        "createdBy": rec.created_by,
        "createdAt": rec.created_at,
    }


@router.get("/history")
def email_history(status: str = "", category: str = "", limit: int = 200,
                  db: Session = Depends(get_db), user=Depends(require_hr)):
    q = db.query(models.EmailRecord).order_by(models.EmailRecord.created_at.desc())
    if status:
        q = q.filter(models.EmailRecord.status == status)
    if category:
        q = q.filter(models.EmailRecord.category == category)
    recs = q.limit(min(limit, 500)).all()
    return [_serialize(r) for r in recs]


@router.get("/history/{email_id}")
def email_history_item(email_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    rec = db.query(models.EmailRecord).filter(models.EmailRecord.id == email_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Email record not found")
    return _serialize(rec)


@router.get("/sender")
def email_sender(user=Depends(get_current_user)):
    """Return the company/approved mailbox used for sending (no secrets).
    Any authenticated user may read it so the referral-mail composer can prefill
    the read-only From field."""
    status = email_service.get_email_status()
    return {
        "from": status.get("sender", ""),
        "configured": bool(status.get("configured", False)),
        "message": status.get("message", ""),
    }


@router.post("/send")
def send_email(payload: schemas.EmailSendIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Send a single/group email now (or record as scheduled) and track delivery."""
    if not payload.to:
        raise HTTPException(status_code=400, detail="At least one recipient is required")
    cc = ", ".join(payload.cc)
    bcc = ", ".join(payload.bcc)
    result = email_service.send_email_direct(
        to_emails=payload.to, cc_emails=payload.cc, bcc_emails=payload.bcc,
        subject=payload.subject, body=payload.body,
    )
    sent_status = result.get("sent", 0) > 0
    for to in payload.to:
        status = "scheduled" if payload.scheduleFor else ("sent" if sent_status else "failed")
        record_email(
            db, to, payload.subject, payload.body, payload.category, payload.emailType,
            status, error="" if status != "failed" else result.get("message", ""),
            cc=cc, bcc=bcc, referral_id=payload.referralId or "", job_id=payload.jobId or "",
            created_by=f"{user.name} ({user.role})",
        )
    log_audit(db, user, "Email sent", target="email", details=f"To {len(payload.to)} recipient(s): {payload.subject}")
    return {
        "ok": True,
        "sent": result.get("sent", 0),
        "failed": result.get("failed", 0),
        "message": result.get("message", ""),
        "tracked": True,
    }


def _filter_candidates(db: Session, flt: schemas.BulkEmailFilterIn) -> list:
    """Return candidate rows matching the bulk-email filter criteria."""
    q = db.query(models.Referral)
    if flt.status:
        q = q.filter(models.Referral.status == flt.status)
    if flt.jobId:
        q = q.filter(models.Referral.job_id == flt.jobId)
    if flt.dept:
        job_ids = [j.id for j in db.query(models.Job).filter(models.Job.dept == flt.dept).all()]
        q = q.filter(models.Referral.job_id.in_(job_ids))
    if flt.startDate:
        q = q.filter(models.Referral.submitted_date >= flt.startDate)
    if flt.endDate:
        q = q.filter(models.Referral.submitted_date <= flt.endDate)
    candidates = q.all()
    if flt.matchMin is not None:
        candidates = [r for r in candidates if (r.match_percent or 0) >= flt.matchMin]
    if flt.matchMax is not None:
        candidates = [r for r in candidates if (r.match_percent or 0) <= flt.matchMax]
    if flt.excludeEmailed:
        already = {e.to_email.lower() for e in db.query(models.EmailRecord).all()}
        candidates = [r for r in candidates if (r.email or "").lower() not in already]
    return [r for r in candidates if r.email]


@router.post("/bulk/candidates")
def bulk_candidate_preview(flt: schemas.BulkEmailFilterIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Preview the candidate group a bulk email would go to."""
    candidates = _filter_candidates(db, flt)
    out = []
    for r in candidates:
        job = db.query(models.Job).filter(models.Job.id == r.job_id).first()
        emp = db.query(models.Employee).filter(models.Employee.id == r.referred_by).first()
        out.append({
            "referralId": r.id,
            "candidateName": r.candidate_name,
            "email": r.email,
            "jobTitle": job.title if job else "—",
            "status": r.status,
            "matchPercent": r.match_percent or 0,
            "referredBy": emp.name if emp else "—",
        })
    return {"total": len(out), "candidates": out}


@router.post("/bulk/send")
def bulk_send(payload: schemas.BulkEmailSendIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Send a bulk email to every candidate matching the filter. Supports a
    dryRun that previews recipients without actually sending."""
    candidates = _filter_candidates(db, payload)
    if not candidates:
        raise HTTPException(status_code=400, detail="No candidates match the selected filter criteria.")
    emails = [r.email for r in candidates]

    if payload.dryRun:
        return {"dryRun": True, "recipients": emails, "total": len(emails)}

    result = email_service.send_email_direct(
        to_emails=emails, cc_emails=[], bcc_emails=[],
        subject=payload.subject, body=payload.body,
    )
    sent_status = result.get("sent", 0) > 0
    for r in candidates:
        record_email(
            db, r.email, payload.subject, payload.body, "bulk", payload.emailType,
            "sent" if sent_status else "failed",
            error="" if sent_status else result.get("message", ""),
            referral_id=r.id, job_id=r.job_id or "",
            created_by=f"{user.name} ({user.role})",
        )
    log_audit(db, user, "Bulk email sent", target="email", details=f"{len(emails)} recipients: {payload.subject}")
    return {
        "ok": True,
        "sent": result.get("sent", 0),
        "failed": result.get("failed", 0),
        "recipients": len(emails),
        "message": result.get("message", ""),
        "tracked": True,
    }
