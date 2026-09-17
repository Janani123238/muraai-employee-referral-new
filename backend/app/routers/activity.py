from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..auth import get_current_user

router = APIRouter(prefix="/api/activity", tags=["activity"])


def serialize(a: models.ActivityLog):
    return {
        "id": a.id,
        "referralId": a.referral_id,
        "action": a.action,
        "description": a.description,
        "performedBy": a.performed_by,
        "created_at": a.created_at,
    }


def log_activity(db: Session, referral_id: str, action: str, description: str, performed_by: str = ""):
    entry = models.ActivityLog(
        referral_id=referral_id,
        action=action,
        description=description,
        performed_by=performed_by,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    return entry


class ActivityLogIn(BaseModel):
    referralId: str
    action: str
    description: str = ""
    performedBy: Optional[str] = ""


@router.get("/{referral_id}")
def get_activity_logs(referral_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    logs = db.query(models.ActivityLog).filter(
        models.ActivityLog.referral_id == referral_id
    ).order_by(models.ActivityLog.created_at.desc()).all()
    return [serialize(l) for l in logs]


@router.post("")
def create_activity_log(payload: ActivityLogIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    entry = log_activity(
        db,
        payload.referralId,
        payload.action,
        payload.description,
        payload.performedBy or user.name,
    )
    return serialize(entry)


@router.get("/timeline/{referral_id}")
def candidate_timeline(referral_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Full hiring timeline combining activity logs + interview records."""
    referral = db.query(models.Referral).filter(models.Referral.id == referral_id).first()
    if not referral:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Referral not found")

    activities = db.query(models.ActivityLog).filter(
        models.ActivityLog.referral_id == referral_id
    ).order_by(models.ActivityLog.created_at.asc()).all()

    interviews = db.query(models.Interview).filter(
        models.Interview.referral_id == referral_id
    ).order_by(models.Interview.created_at.asc()).all()

    timeline = []

    timeline.append({
        "type": "status",
        "title": "Applied",
        "description": f"{referral.candidate_name} referred for the position",
        "date": referral.submitted_date.isoformat() if referral.submitted_date else "",
        "performedBy": "",
        "icon": "📨",
    })

    for a in activities:
        timeline.append({
            "type": "activity",
            "title": a.action,
            "description": a.description,
            "date": a.created_at.isoformat() if a.created_at else "",
            "performedBy": a.performed_by,
            "icon": "🔄" if "status" in a.action.lower() else "📋",
        })

    for iv in interviews:
        result_info = f" — {iv.result}" if iv.result else ""
        timeline.append({
            "type": "interview",
            "title": f"{iv.round_name}: {iv.status}{result_info}",
            "description": f"{iv.interviewer} | {iv.interview_date} {iv.start_time}" + (f" | Score: {iv.score}" if iv.score else ""),
            "date": iv.created_at.isoformat() if iv.created_at else "",
            "performedBy": iv.interviewer,
            "icon": "🗓️" if iv.status == "Scheduled" else "✅" if iv.status == "Completed" else "📅",
        })

    timeline.sort(key=lambda x: x["date"] or "", reverse=False)

    return {
        "referralId": referral_id,
        "candidateName": referral.candidate_name,
        "currentStatus": referral.status,
        "timeline": timeline,
    }
