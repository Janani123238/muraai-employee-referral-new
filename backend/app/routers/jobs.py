from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user, require_hr
from .admin import log_audit

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/public", response_model=list[schemas.JobOut])
def list_jobs_public(db: Session = Depends(get_db)):
    """Public endpoint — no auth needed. For the landing page."""
    return db.query(models.Job).filter(
        models.Job.status == "Open",
        models.Job.is_deleted.is_(False),
    ).order_by(models.Job.posted.desc()).all()


@router.get("", response_model=list[schemas.JobOut])
def list_jobs(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.Job).filter(models.Job.is_deleted.is_(False)).order_by(models.Job.posted.desc()).all()


@router.post("", response_model=schemas.JobOut)
def create_job(payload: schemas.JobIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    job = models.Job(**payload.dict(), posted=datetime.utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)
    log_audit(db, user, "Job created", target="job", target_id=job.id,
              details=f"{job.title} | dept: {job.dept} | bonus: ₹{job.bonus}")
    return job


@router.put("/{job_id}", response_model=schemas.JobOut)
def update_job(job_id: str, payload: schemas.JobIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    old_status = job.status
    for k, v in payload.dict().items():
        setattr(job, k, v)
    db.commit()
    db.refresh(job)
    log_audit(db, user, "Job updated", target="job", target_id=job_id,
              details=f"{job.title} | status: {old_status} -> {job.status}")
    return job


@router.delete("/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Soft-delete a job. The record (and any referral history) is retained for
    audit purposes but hidden from the open jobs list, referral forms, and
    dashboards. Referrals already against the job keep their data intact."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_deleted:
        raise HTTPException(status_code=400, detail="This job has already been deleted")

    job.is_deleted = True
    job.deleted_at = datetime.utcnow()
    job.deleted_by = user.name
    job.status = "Closed"
    referral_count = db.query(models.Referral).filter(
        models.Referral.job_id == job_id,
        models.Referral.is_deleted.is_(False),
    ).count()
    db.commit()
    log_audit(db, user, "Job deleted (soft)", target="job", target_id=job_id,
              details=f"{job.title} | {referral_count} active referral(s) retained for audit")
    return {"ok": True, "message": f"Job '{job.title}' deleted. Existing referral data is retained."}
