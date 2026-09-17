from sqlalchemy.orm import Session
from . import models
from .auth import hash_password
from .config import settings


def _ensure_user(db: Session, name: str, email: str, password: str, role: str):
    existing = db.query(models.User).filter(models.User.email == email).first()
    if not existing:
        emp = models.Employee(name=name, dept="General", email=email)
        db.add(emp)
        db.flush()
        db.add(models.User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=role,
            employee_id=emp.id,
        ))
        db.commit()
    else:
        if existing.password_hash != hash_password(password):
            existing.password_hash = hash_password(password)
        if existing.role != role:
            existing.role = role
        db.commit()


def _ensure_jobs(db: Session):
    if db.query(models.Job).count() > 0:
        return
    sample_jobs = [
        {"title": "Senior Software Engineer", "dept": "Engineering", "category": "Engineering",
         "exp": "5-8 years", "location": "Bangalore", "salary": "25-35 LPA", "bonus": 15000,
         "skills": ["Python", "FastAPI", "React", "PostgreSQL"],
         "description": "Build scalable backend services and APIs for our recruitment platform."},
        {"title": "Product Manager", "dept": "Product", "category": "Product",
         "exp": "4-7 years", "location": "Remote", "salary": "20-30 LPA", "bonus": 12000,
         "skills": ["Product Strategy", "Agile", "Data Analysis", "Stakeholder Management"],
         "description": "Drive product roadmap and execution for our HR-tech platform."},
        {"title": "UI/UX Designer", "dept": "Design", "category": "Design",
         "exp": "3-5 years", "location": "Hyderabad", "salary": "15-22 LPA", "bonus": 10000,
         "skills": ["Figma", "User Research", "Prototyping", "CSS"],
         "description": "Design intuitive user experiences for enterprise recruitment tools."},
    ]
    for j in sample_jobs:
        db.add(models.Job(**j, status="Open"))
    db.commit()


def _ensure_kb(db: Session):
    """Seed the HR / Employee knowledge base only when it's empty."""
    if db.query(models.KnowledgeArticle).count() > 0:
        return
    articles = [
        {
            "title": "How to submit a referral",
            "category": "Referral Process",
            "audience": "all",
            "tags": ["referral", "how-to", "submit"],
            "content": (
                "To refer a candidate, open the 'Refer Candidate' page and fill in the candidate's "
                "details: name, email, phone, and the resume (PDF, DOCX, or image). The AI will "
                "parse the resume, score the match against the selected job, and attach a "
                "recommendation. Once submitted, the candidate enters the pipeline and HR is "
                "notified. You can track the status any time from 'My Referrals'."
            ),
        },
        {
            "title": "Referral bonus and payout schedule",
            "category": "Rewards",
            "audience": "all",
            "tags": ["bonus", "payout", "reward"],
            "content": (
                "The referral bonus is paid for every candidate who joins and completes probation. "
                "The bonus amount is listed on each open job card (e.g. ₹50,000). Bonuses are "
                "credited via payroll in the month following the 30-day confirmation period. There "
                "is no cap on referrals per employee per quarter."
            ),
        },
        {
            "title": "Interview process overview",
            "category": "Interviews",
            "audience": "all",
            "tags": ["interview", "rounds", "process"],
            "content": (
                "Shortlisted candidates go through HR screening, one or two technical rounds, a "
                "manager round, and a final HR discussion. Interview invitations are sent by email "
                "with a meeting link. Candidates can be rescheduled up to 24 hours before the slot. "
                "Interviewers record feedback and a pass/hold/reject decision after each round."
            ),
        },
        {
            "title": "Duplicate referral rule",
            "category": "Referral Process",
            "audience": "all",
            "tags": ["duplicate", "eligibility", "policy"],
            "content": (
                "Only the first referral for a candidate within 90 days is eligible for the bonus. "
                "The system auto-detects duplicates by email, phone, and name when you submit, and "
                "flags them before you confirm. Re-submitting a candidate already in the pipeline "
                "will be marked as a duplicate."
            ),
        },
        {
            "title": "Tracking your referral status",
            "category": "Referral Process",
            "audience": "all",
            "tags": ["tracking", "status", "stages"],
            "content": (
                "The 'My Referrals' page shows every candidate you referred with their current "
                "stage: Applied, Resume Screening, Shortlisted, Interview Scheduled, Interview "
                "Completed, Selected, Offer Released, Rejected, or Joined. Stages are updated "
                "automatically by the workflow and by HR actions."
            ),
        },
        {
            "title": "AI shortlisting rules and score bands",
            "category": "Candidate Management",
            "audience": "hr",
            "tags": ["shortlist", "scoring", "auto-reject"],
            "content": (
                "The AI scores every resume against the target job from 0-100. Scores of 95-100 "
                "auto-move to the interview stage. Scores of 80-94 require HR review before "
                "advancing. Scores of 40-79 are kept for manual evaluation by HR. Scores below 40 "
                "are auto-rejected and a rejection email is sent automatically. HR retains full "
                "control of the middle band so strong candidates who just miss keywords are not lost."
            ),
        },
        {
            "title": "Candidate management best practices",
            "category": "Candidate Management",
            "audience": "hr",
            "tags": ["candidates", "workflow", "best-practices"],
            "content": (
                "Review AI scores alongside the strengths/weaknesses the system extracts — never "
                "advance or reject solely on a number. Keep the status dropdown in sync with each "
                "candidate's real stage so dashboards and the AI assistant report accurate numbers. "
                "Record interview feedback promptly; pending feedback blocks the next round."
            ),
        },
        {
            "title": "Interview feedback guidelines",
            "category": "Interviews",
            "audience": "hr",
            "tags": ["feedback", "interviewer", "guidelines"],
            "content": (
                "Each interview round records a result (Pass / Hold / Reject) plus written feedback. "
                "Feedback should be factual and specific: cite examples from the interview rather "
                "than general impressions. Holds require a follow-up date. Completed feedback "
                "automatically notifies the next interviewer and updates the candidate's stage."
            ),
        },
    ]
    for art in articles:
        db.add(models.KnowledgeArticle(**art, updated_by="MuraAI Admin"))
    db.commit()


def bootstrap(db: Session):
    """Runs on every startup. Creates only what a real deployment actually
    needs to function — never any fake candidates, jobs, or employees.
    """
    if db.query(models.AppSettings).count() == 0:
        db.add(models.AppSettings(id=1))

    if db.query(models.ReferralPolicy).count() == 0:
        db.add(models.ReferralPolicy(id=1))

    _ensure_kb(db)

    db.commit()

    if settings.BOOTSTRAP_ADMIN_EMAIL and settings.BOOTSTRAP_ADMIN_PASSWORD:
        existing = db.query(models.User).filter(
            models.User.email == settings.BOOTSTRAP_ADMIN_EMAIL
        ).first()
        if not existing:
            emp = models.Employee(
                name=settings.BOOTSTRAP_ADMIN_NAME or "Admin",
                dept="Management",
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
            )
            db.add(emp)
            db.flush()
            db.add(models.User(
                name=settings.BOOTSTRAP_ADMIN_NAME or "Admin",
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                role="admin",
                employee_id=emp.id,
            ))
            db.commit()
        else:
            existing.name = settings.BOOTSTRAP_ADMIN_NAME or existing.name or "Admin"
            existing.role = "admin"
            existing.password_hash = hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD)
            if not existing.employee_id:
                emp = models.Employee(
                    name=existing.name,
                    dept="Management",
                    email=existing.email,
                )
                db.add(emp)
                db.flush()
                existing.employee_id = emp.id
            db.commit()

    _ensure_user(db, "HR Manager", "hr@muraai.com", "Test1234!", "hr")
    _ensure_user(db, "HR Manager", "hrmanager@muraai.com", "Test1234!", "hr_manager")
    _ensure_user(db, "VP Engineering", "vp@muraai.com", "Test1234!", "vp")
    _ensure_user(db, "CTO", "cto@muraai.com", "Test1234!", "cto")
    _ensure_user(db, "CEO", "ceo@muraai.com", "Test1234!", "ceo")
    _ensure_user(db, "System Admin", "sysadmin@muraai.com", "Test1234!", "system_admin")
    _ensure_user(db, "Test Employee", "test@muraai.com", "Test1234!", "employee")
    _ensure_user(db, "Test Manager", "manager@muraai.com", "Test1234!", "manager")

    _ensure_jobs(db)
