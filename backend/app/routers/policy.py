import os
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, resume_parser
from ..auth import get_current_user, require_hr

router = APIRouter(prefix="/api/policy", tags=["policy"])

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".webp", ".txt"}


@router.get("")
def get_policy(db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(models.ReferralPolicy).first()
    if not p:
        p = models.ReferralPolicy(id=1)
        db.add(p)
        db.commit()
        db.refresh(p)
    return {"content": p.content, "updatedAt": p.updated_at, "updatedBy": p.updated_by}


@router.post("/import")
async def import_policy_document(file: UploadFile = File(...), user=Depends(require_hr)):
    """Extract policy text from an uploaded document (PDF/DOCX/image/TXT) using the
    same real extraction + OCR pipeline as resumes. Text is returned to the caller;
    nothing is persisted here."""
    original_name = file.filename or "policy"
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
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process the file. Please try again.")

    return {
        "fileName": original_name,
        "extractedText": extracted_text,
        "charCount": len(extracted_text),
    }


@router.put("")
def update_policy(payload: schemas.PolicyUpdateIn, db: Session = Depends(get_db),
                  user=Depends(require_hr)):
    p = db.query(models.ReferralPolicy).first()
    if not p:
        p = models.ReferralPolicy(id=1)
        db.add(p)
    p.content = payload.content
    p.updated_at = datetime.utcnow()
    p.updated_by = user.name
    db.commit()
    db.refresh(p)
    return {"content": p.content, "updatedAt": p.updated_at, "updatedBy": p.updated_by}
