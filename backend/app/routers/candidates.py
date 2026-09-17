import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    validate_password_strength,
)

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


def _user_public(user: models.User):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "employeeId": user.employee_id,
    }


@router.post("/register", response_model=schemas.TokenOut)
def candidate_register(payload: schemas.CandidateRegisterIn, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    validate_password_strength(payload.password)

    employee = models.Employee(name=payload.name, dept="Candidate", email=payload.email)
    db.add(employee)
    db.flush()

    user = models.User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="candidate",
        employee_id=employee.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id})
    return {"access_token": token, "user": _user_public(user), "notice": None}


@router.post("/login", response_model=schemas.TokenOut)
def candidate_login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="This login is for candidates only")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "user": _user_public(user)}


@router.get("/me")
def candidate_me(user: models.User = Depends(get_db)):
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access required")
    profile = _user_public(user)
    if user.employee_id:
        emp = db_get_employee(user.employee_id)
        if emp:
            profile["phone"] = getattr(emp, "phone", "")
            profile["location"] = getattr(emp, "location", "")
            profile["experience"] = getattr(emp, "experience", "")
            profile["education"] = getattr(emp, "education", "")
            profile["skills"] = getattr(emp, "skills", "")
    return profile


@router.patch("/profile")
def candidate_update_profile(
    payload: schemas.CandidateUpdateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access required")
    if user.employee_id:
        emp = db.query(models.Employee).filter(models.Employee.id == user.employee_id).first()
        if emp:
            for field in ["phone", "location", "experience", "education", "skills"]:
                val = getattr(payload, field, None)
                if val is not None:
                    setattr(emp, field, val)
    if payload.name:
        user.name = payload.name
    db.commit()
    db.refresh(user)
    return _user_public(user)


@router.post("/withdraw/{application_id}")
def candidate_withdraw(
    application_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access required")
    referral = db.query(models.Referral).filter(
        models.Referral.id == application_id,
        models.Referral.email == user.email,
    ).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Application not found")
    referral.status = "Withdrawn"
    db.commit()
    return {"message": "Application withdrawn", "id": referral.id}


@router.post("/apply")
def candidate_apply(
    payload: schemas.CandidateApplyIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access required")
    job = db.query(models.Job).filter(models.Job.id == payload.jobId).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    referral = models.Referral(
        candidate_name=user.name,
        email=user.email,
        phone=payload.phone,
        resume_text=payload.resumeText,
        resume_file_name=payload.resumeFileName,
        linkedin=payload.linkedin,
        github=payload.github,
        portfolio=payload.portfolio,
        location=payload.location,
        current_company=payload.currentCompany,
        current_designation=payload.currentDesignation,
        total_experience=payload.totalExperience,
        relevant_experience=payload.relevantExperience,
        skills=payload.skills,
        education=payload.education,
        certifications=payload.certifications,
        projects=payload.projects,
        referred_by="",
        job_id=payload.jobId,
        status="Applied",
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)

    return {
        "id": referral.id,
        "candidateName": referral.candidate_name,
        "jobId": referral.job_id,
        "jobTitle": job.title,
        "status": referral.status,
        "submittedDate": referral.submitted_date.isoformat() if referral.submitted_date else None,
    }


@router.get("/applications")
def candidate_applications(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role not in ("candidate", "employee"):
        raise HTTPException(status_code=403, detail="Candidate access required")

    referrals = (
        db.query(models.Referral)
        .filter(models.Referral.email == user.email)
        .order_by(models.Referral.submitted_date.desc())
        .all()
    )

    results = []
    for r in referrals:
        job = db.query(models.Job).filter(models.Job.id == r.job_id).first()
        results.append({
            "id": r.id,
            "candidateName": r.candidate_name,
            "jobId": r.job_id,
            "jobTitle": job.title if job else "",
            "status": r.status,
            "submittedDate": r.submitted_date.isoformat() if r.submitted_date else None,
        })
    return results


@router.post("/generate-referral")
def generate_referral_link(
    payload: schemas.GenerateReferralLinkIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user.role not in ("employee", "hr", "admin"):
        raise HTTPException(status_code=403, detail="Employee access required")

    short_id = user.id[-6:] if user.employee_id else user.id[-6:]
    random_part = uuid.uuid4().hex[:8].upper()
    referral_code = f"REF-{short_id}-{random_part}"

    return {
        "referralCode": referral_code,
        "candidateEmail": payload.candidateEmail,
        "candidateName": payload.candidateName,
        "jobId": payload.jobId,
        "generatedBy": user.name,
    }


def db_get_employee(employee_id: str):
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        return db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    finally:
        db.close()
