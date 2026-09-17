import os
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import Response

from ..auth import get_current_user, require_hr
from .. import resume_parser, ai_service, models, rag_service
from ..database import SessionLocal

logger = logging.getLogger("resumes")

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".webp", ".txt"}


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), user=Depends(get_current_user)):
    original_name = file.filename or "resume"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=422, detail="File too large — max 10 MB")

    try:
        extracted_text = resume_parser.extract_text(original_name, file_bytes)
    except resume_parser.ResumeParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected resume extraction failure for %s", original_name)
        raise HTTPException(status_code=500, detail="Failed to process the resume file. Please try again.")

    file_id = f"res_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        db.add(models.ResumeFile(
            id=file_id,
            file_name=original_name,
            file_type=ext,
            file_data=file_bytes,
        ))
        db.commit()
    finally:
        db.close()

    return {
        "fileId": file_id,
        "fileName": original_name,
        "fileUrl": f"/api/resumes/file/{file_id}",
        "extractedText": extracted_text,
        "charCount": len(extracted_text),
    }


@router.get("/file/{file_id}")
def get_resume_file(file_id: str, user=Depends(get_current_user)):
    db = SessionLocal()
    try:
        rf = db.query(models.ResumeFile).filter(models.ResumeFile.id == file_id).first()
        if not rf:
            raise HTTPException(status_code=404, detail="Resume file not found")
        media_type = _mime_type(rf.file_type)
        return Response(content=rf.file_data, media_type=media_type)
    finally:
        db.close()


def _mime_type(ext: str) -> str:
    return {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".txt": "text/plain",
    }.get(ext, "application/octet-stream")


@router.post("/bulk-import")
async def bulk_import(
    job_id: str = Form(""),
    files: list[UploadFile] = File(...),
    user=Depends(require_hr),
):
    """HR bulk resume import.

    For each file: OCR extraction -> candidate parsing -> duplicate detection ->
    JD matching (AI) -> candidate creation -> returns JD vs Resume Match.
    """
    if len(files) > 50:
        raise HTTPException(status_code=422, detail="Max 50 files per import")

    import asyncio

    db = SessionLocal()
    job = None
    job_dict = {}
    job_title = ""
    rag_ctx = ""
    try:
        if job_id:
            job = db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            job_title = job.title or ""
            job_dict = {"id": job.id, "title": job.title, "skills": job.skills,
                        "description": job.description, "exp": job.exp}
            # JD-scoped RAG grounding, computed once (ranked by title+skills
            # since per-file resume texts differ).
            try:
                rag_query = f"{job.title} {' '.join(job.skills or [])}".strip()
                rag_ctx = rag_service.jd_context(db, job, rag_query)
            except Exception:
                rag_ctx = ""
    finally:
        db.close()

    sem = asyncio.Semaphore(3)

    async def process_one(file: UploadFile):
        async with sem:
            name = file.filename or "resume"
            ext = os.path.splitext(name)[1].lower()
            result = {
                "fileName": name,
                "success": False,
                "duplicate": False,
                "duplicateOf": "",
                "duplicateReasons": [],
                "error": "",
            }
            try:
                if ext not in ALLOWED_EXTENSIONS:
                    result["error"] = f"Unsupported file type '{ext}'"
                    return result
                file_bytes = await file.read()
                if not file_bytes:
                    result["error"] = "Empty file"
                    return result
                if len(file_bytes) > MAX_FILE_BYTES:
                    result["error"] = "File too large — max 10 MB"
                    return result

                text = resume_parser.extract_text(name, file_bytes)
                parsed = ai_service.regex_parse_resume(text)
                candidate_name = parsed.get("name") or os.path.splitext(name)[0].strip()[:80] or "Candidate"
                email = parsed.get("email", "")
                phone = parsed.get("phone", "")

                db = SessionLocal()
                try:
                    dup = screening.find_duplicates(db, email=email, phone=phone,
                                                    name=candidate_name, resume_text=text)
                    if dup["duplicate"]:
                        m = dup["matches"][0]
                        result["duplicate"] = True
                        result["duplicateOf"] = m["candidateName"]
                        result["duplicateReasons"] = m["reasons"]
                        result["fileName"] = name
                        return result
                    result["candidateName"] = candidate_name
                finally:
                    db.close()

                file_id = f"res_{uuid.uuid4().hex[:10]}"
                db = SessionLocal()
                try:
                    db.add(models.ResumeFile(id=file_id, file_name=name, file_type=ext, file_data=file_bytes))

                    referral = models.Referral(
                        candidate_name=candidate_name,
                        phone=phone,
                        email=email,
                        resume_text=text,
                        resume_file_url=f"/api/resumes/file/{file_id}",
                        resume_file_name=name,
                        linkedin=parsed.get("linkedin", ""),
                        github=parsed.get("github", ""),
                        current_company=parsed.get("currentCompany", ""),
                        total_experience=f"{parsed.get('totalExperienceYears') or 0} yrs",
                        skills=parsed.get("skills", []),
                        education=parsed.get("education", ""),
                        certifications=parsed.get("certifications", []),
                        projects=parsed.get("projects", []),
                        relationship_to_referrer="Bulk import",
                        referred_by=user.employee_id,
                        job_id=job_id,
                        status="Submitted",
                        submitted_date=datetime.utcnow(),
                        match_percent=0,
                        evaluation_history=[{
                            "action": "Bulk import",
                            "by": user.name,
                            "at": datetime.utcnow().isoformat(),
                            "fromStatus": "", "toStatus": "Submitted",
                        }],
                    )
                    db.add(referral)
                    db.commit()
                    db.refresh(referral)

                    match_detail = await ai_service.ai_match_job(text, job_dict, rag_ctx)
                    match = 0
                    if isinstance(match_detail, dict):
                        match = int(match_detail.get("jd_vs_resume_match") or 0)
                        referral.match_percent = match
                        referral.missing_skills = match_detail.get("missing_skills", match_detail.get("missingSkills", []))
                    else:
                        # Heuristic fallback: overlap of resume skills with job skills.
                        job_skills = set((job.skills or []) if job else [])
                        resume_skills = set(parsed.get("skills") or [])
                        if job_skills:
                            match = int(round(len(job_skills & resume_skills) / len(job_skills) * 100))
                        else:
                            match = 70
                        referral.match_percent = match

                    from ..shortlist import shortlist_for_score, rank_label_for_score, AI_RECOMMENDED_REJECT, HR_REVIEW_PENDING
                    referral.original_match = referral.original_match or match
                    referral.rank_label = rank_label_for_score(match)
                    referral.match_breakdown = (match_detail.get("match_breakdown", {}) or {}) if isinstance(match_detail, dict) else {}
                    _decision = shortlist_for_score(match)
                    if _decision["verdict"] == "ai_recommended_reject":
                        referral.status = AI_RECOMMENDED_REJECT
                        referral.ai_recommendation = "ai_recommended_reject"
                        referral.review_status = HR_REVIEW_PENDING
                        referral.auto_rejected = False

                    _hist = list(referral.evaluation_history or [])
                    db.commit()

                    from .activity import log_activity
                    log_activity(db, referral.id, "Bulk import",
                                 f"Resume imported by {user.name} — JD vs Resume Match {match}%.",
                                  user.name)
                    from .admin import log_audit
                    log_audit(db, user, "Bulk resume import", target="referral", target_id=referral.id,
                              details=f"Candidate: {referral.candidate_name} | JD vs Resume Match {match}%")

                    result.update({
                        "success": True,
                        "referralId": referral.id,
                        "candidateName": referral.candidate_name,
                        "jd_vs_resume_match": match,
                        "status": referral.status,
                    })
                finally:
                    db.close()
                return result
            except resume_parser.ResumeParseError as exc:
                result["error"] = str(exc)
                return result
            except Exception as exc:
                logger.exception("Bulk import failed for %s", name)
                result["error"] = f"Processing failed: {exc}"
                return result

    results = await asyncio.gather(*(process_one(f) for f in files))

    summary = {
        "total": len(results),
        "success": sum(1 for r in results if r["success"]),
        "duplicates": sum(1 for r in results if r["duplicate"]),
        "failed": sum(1 for r in results if r["error"]),
    }
    return {"summary": summary, "results": results}