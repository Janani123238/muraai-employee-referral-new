from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..schemas import SettingsIn
from ..auth import get_current_user, require_hr, require_admin
from .. import resume_parser
from .. import email_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _is_admin(user) -> bool:
    return user.role in {"admin", "system_admin"}


def serialize(s: models.AppSettings) -> dict:
    """Serialise settings for the frontend. The SMTP password is NEVER returned
    — callers only learn whether a password is set via smtpPasswordSet."""
    return {
        "resumeParsing": s.resume_parsing,
        "duplicateDetection": s.duplicate_detection,
        "fraudDetection": s.fraud_detection,
        "interviewPrediction": s.interview_prediction,
        "chatAssistant": s.chat_assistant,
        "aiProvider": s.ai_provider,
        "aiModel": s.ai_model,
        "aiApiKey": s.ai_api_key,
        "aiTemperature": s.ai_temperature,
        "aiMaxTokens": s.ai_max_tokens,
        "ocrEnabled": s.ocr_enabled,
        "ocrLanguage": s.ocr_language,
        "smtpHost": s.smtp_host,
        "smtpPort": s.smtp_port,
        "smtpUser": s.smtp_user,
        "smtpFrom": s.smtp_from,
        "smtpUseTls": s.smtp_use_tls,
        "senderName": getattr(s, "sender_name", "") or "",
        "smtpPasswordSet": bool(getattr(s, "smtp_password", "")),
        "smtpConfigured": bool((s.smtp_host or "").strip()),
    }


def _validate_smtp_on_save(s: models.AppSettings) -> None:
    """SMTP has been removed. Email is now sent exclusively via Microsoft Graph
    (configured through the backend .env). No validation needed here."""
    return None


@router.get("")
def get_settings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.query(models.AppSettings).first()
    return serialize(s)


@router.put("")
def update_settings(payload: SettingsIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    """HR can toggle AI feature flags. Admin-only fields (AI provider, SMTP) are
    only updated when the caller is an admin."""
    s = db.query(models.AppSettings).first()
    if payload.resumeParsing is not None:
        s.resume_parsing = payload.resumeParsing
    if payload.duplicateDetection is not None:
        s.duplicate_detection = payload.duplicateDetection
    if payload.fraudDetection is not None:
        s.fraud_detection = payload.fraudDetection
    if payload.interviewPrediction is not None:
        s.interview_prediction = payload.interviewPrediction
    if payload.chatAssistant is not None:
        s.chat_assistant = payload.chatAssistant
    # Admin-only: AI provider config
    if _is_admin(user):
        if payload.aiProvider is not None:
            s.ai_provider = payload.aiProvider
        if payload.aiModel is not None:
            s.ai_model = payload.aiModel
        if payload.aiApiKey is not None:
            s.ai_api_key = payload.aiApiKey
        if payload.aiTemperature is not None:
            s.ai_temperature = payload.aiTemperature
        if payload.aiMaxTokens is not None:
            s.ai_max_tokens = payload.aiMaxTokens
        # SMTP was removed — email is sent exclusively via Microsoft Graph
        # (configured in the backend .env). Old SMTP fields are ignored.
        _validate_smtp_on_save(s)
    if payload.ocrEnabled is not None:
        s.ocr_enabled = payload.ocrEnabled
    if payload.ocrLanguage is not None:
        s.ocr_language = payload.ocrLanguage
    db.commit()
    db.refresh(s)
    # Sync OCR language to the parser module
    resume_parser.set_ocr_language(s.ocr_language)
    return serialize(s)


@router.post("/test-smtp")
def test_smtp(db: Session = Depends(get_db), user=Depends(require_admin)):
    """Test the Microsoft Graph email connection (SMTP has been removed). Uses
    the Azure app credentials + MAIL_FROM from the backend .env. Requires admin
    privileges."""
    return email_service.test_email_connection()
