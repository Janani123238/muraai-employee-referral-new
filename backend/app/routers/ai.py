import asyncio
import json
import logging
import re
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, ai_service
from ..auth import get_current_user, require_hr
from .. import rag_service
from ..shortlist import shortlist_for_score, rank_label_for_score

logger = logging.getLogger("ai_router")

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Small in-process answer cache: repeated questions (the common case in an
# enterprise assistant) return instantly instead of re-running the LLM/embed.
_chat_cache = {}
_CHAT_CACHE_TTL = 300  # seconds


def _chat_cache_key(user_id, message, kind=""):
    return f"{user_id}|{kind}|{message.strip().lower()[:180]}"


def _chat_cache_get(user_id, message, kind=""):
    key = _chat_cache_key(user_id, message, kind)
    entry = _chat_cache.get(key)
    if entry and entry["ts"] + _CHAT_CACHE_TTL > time.time():
        return entry["reply"]
    _chat_cache.pop(key, None)
    return None


def _chat_cache_set(user_id, message, kind, reply):
    key = _chat_cache_key(user_id, message, kind)
    _chat_cache[key] = {"ts": time.time(), "reply": reply}
    if len(_chat_cache) > 200:
        now = time.time()
        stale = [k for k, v in _chat_cache.items() if now - v["ts"] > _CHAT_CACHE_TTL]
        for k in stale:
            _chat_cache.pop(k, None)


_CHAT_MAX_HISTORY = 20  # last 20 messages (10 Q&A pairs) sent to LLM
_CHAT_MAX_RETRIES = 2   # exponential backoff retries (not for validation errors)
_CHAT_TIMEOUT_SECONDS = 90  # per-request timeout for the provider


def _structured_error(error_type: str, message: str) -> dict:
    return {"success": False, "error": error_type, "message": message}


def _cap_history(history):
    if not history:
        return []
    return history[-_CHAT_MAX_HISTORY:]


@router.get("/status")
async def ai_status(user=Depends(get_current_user)):
    """Check if the AI provider is configured and reachable."""
    ps = ai_service._get_provider_settings()
    provider = ps["provider"]
    available = await ai_service._check_ai_available()
    return {
        "provider": provider,
        "model": ps["model"],
        "available": available,
        "message": f"AI ({provider}) is ready." if available else f"AI ({provider}) is not available. Using built-in analysis instead.",
    }


def get_job_or_404(db, job_id):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def get_referral_or_404(db, ref_id):
    r = db.query(models.Referral).filter(models.Referral.id == ref_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Referral not found")
    return r


@router.post("/parse-resume")
async def parse_resume(payload: schemas.ResumeTextIn, user=Depends(get_current_user)):
    result = await ai_service.ai_parse_resume(payload.resumeText)
    if result is None:
        raise HTTPException(status_code=502, detail="AI could not parse the resume. Please try again or paste the text manually.")
    return result


@router.post("/match-job")
async def match_job(payload: schemas.MatchJobIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Resume vs selected-JD match score. JD Match Scores are internal HR
    metrics — employees/candidates never receive them."""
    job = get_job_or_404(db, payload.jobId)
    try:
        rag_ctx = rag_service.jd_context(db, job, payload.resumeText)
    except Exception:
        rag_ctx = ""
    result = await ai_service.ai_match_job(payload.resumeText, job, rag_ctx)
    if result is None:
        raise HTTPException(status_code=502, detail="AI matching failed. Please try again.")
    return result


@router.post("/detailed-match")
async def detailed_match(
    payload: schemas.ResumeTextIn,
    jobId: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_hr),
):
    if not jobId:
        raise HTTPException(status_code=400, detail="jobId query parameter is required")
    job = get_job_or_404(db, jobId)
    result = await ai_service.ai_detailed_match(payload.resumeText, job)
    return result


@router.post("/match-all-jobs")
async def match_all_jobs(payload: schemas.ResumeTextIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Compute resume vs JD match scores for every open role.

    HR/admin only: JD Match Scores are internal metrics, not shown to employees
    or candidates. The employee referral flow is locked to one selected role.
    """
    jobs = db.query(models.Job).filter(models.Job.is_deleted.is_(False)).all()
    if not jobs:
        return []

    async def match_one(job):
        m = await ai_service.ai_match_job(payload.resumeText, job)
        if m:
            return {
                "job": {"id": job.id, "title": job.title, "dept": job.dept, "location": job.location},
                "match": m,
            }
        return None

    tasks = [match_one(job) for job in jobs]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)
    results = [r for r in results_raw if r is not None and not isinstance(r, Exception)]
    results.sort(key=lambda x: x["match"].get("matchPercent", 0), reverse=True)
    return results


@router.post("/summary")
async def summary(payload: schemas.ResumeTextIn, user=Depends(get_current_user)):
    result = await ai_service.ai_summary(payload.resumeText)
    if result is None:
        return {"summary": "AI summary unavailable — the model may be loading.", "suitableFor": ""}
    return result


@router.post("/fraud-check")
async def fraud_check(payload: schemas.ResumeTextIn, user=Depends(get_current_user)):
    result = await ai_service.ai_fraud_check(payload.resumeText)
    if result is None:
        return {"riskLevel": "low", "flags": [], "aiGeneratedProbability": 0}
    return result


@router.post("/interview-prediction")
async def interview_prediction(payload: schemas.MatchJobIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    job = get_job_or_404(db, payload.jobId)
    result = await ai_service.ai_interview_prediction(payload.resumeText, job)
    if result is None:
        return {"chance": 50, "reasons": ["AI prediction unavailable — please try again."]}
    return result


@router.post("/auto-tags")
async def auto_tags(payload: schemas.ResumeTextIn, user=Depends(get_current_user)):
    return {"tags": await ai_service.ai_auto_tags(payload.resumeText)}


@router.post("/compare-candidates")
async def compare_candidates(payload: schemas.CompareIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ref_a = get_referral_or_404(db, payload.referralIds[0])
    ref_b = get_referral_or_404(db, payload.referralIds[1])
    job = db.query(models.Job).filter(models.Job.id == ref_a.job_id).first()
    result = await ai_service.ai_compare_candidates(ref_a, ref_b, job)
    if result is None:
        return {
            "strongerCandidate": "A",
            "verdict": "AI comparison could not be completed at this time.",
            "candidateAStrengths": [f"{ref_a.candidate_name}: referral submitted"],
            "candidateBStrengths": [f"{ref_b.candidate_name}: referral submitted"],
        }
    return result


@router.post("/generate-email")
async def generate_email(payload: schemas.GenerateEmailIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    referral = get_referral_or_404(db, payload.referralId)
    job = db.query(models.Job).filter(models.Job.id == referral.job_id).first()
    text = await ai_service.ai_generate_email(referral, job)
    return {"email": text}


@router.post("/generate-jd")
async def generate_jd(payload: schemas.GenerateJdIn, user=Depends(get_current_user)):
    text = await ai_service.ai_generate_jd(payload.brief)
    return {"jd": text}


@router.post("/chat")
async def chat(payload: schemas.ChatMessageIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Real-time, role-aware AI assistant backed by live database data (RAG).

    Fast path: quantitative/status questions are answered instantly from a
    computed DB result (no LLM round-trip). Everything else is answered by the
    LLM over a trimmed, role-scoped context. Repeated questions hit the cache.

    Retries up to _CHAT_MAX_RETRIES times with exponential backoff on
    provider/network errors (but NOT on validation errors)."""
    request_id = f"chat-{int(time.time()*1000)}-{user.id}"
    t_start = time.time()
    logger.info("AI_REQUEST_START id=%s user=%s msg=%s", request_id, user.id, payload.message[:80])

    ctx = rag_service.build_context(db, user, payload.message)

    if ctx["live"]:
        reply = ctx["live"]["answer"]
        if ctx["live"].get("detail"):
            reply += "\n" + ctx["live"]["detail"]
        logger.info("AI_REQUEST_END id=%s provider=live duration=%.2fs ok=True", request_id, time.time()-t_start)
        return {"reply": reply, "live": ctx["live"], "source": "live", "fast": True}

    cached = _chat_cache_get(user.id, payload.message, "")
    if cached is not None:
        logger.info("AI_REQUEST_END id=%s provider=cache duration=%.2fs ok=True", request_id, time.time()-t_start)
        return {"reply": cached, "live": None, "source": "cache", "fast": True}

    history = _cap_history(payload.history)
    last_error = None
    for attempt in range(1 + _CHAT_MAX_RETRIES):
        delay = (2 ** attempt) * 0.5
        t_llm = time.time()
        logger.info("AI_PROVIDER_REQUEST id=%s attempt=%d model=%s timeout=%ds",
                     request_id, attempt+1, ai_service.settings.OLLAMA_MODEL, _CHAT_TIMEOUT_SECONDS)
        try:
            reply = await ai_service.ai_chat(payload.message, history, ctx["context"])
            elapsed = time.time() - t_llm
            logger.info("AI_PROVIDER_RESPONSE id=%s attempt=%d duration=%.2fs ok=True", request_id, attempt+1, elapsed)
            if not reply or "couldn't process" in reply:
                logger.info("AI_REQUEST_END id=%s provider=ollama duration=%.2fs ok=False error=empty_reply",
                             request_id, time.time()-t_start)
                return {"reply": reply or "Sorry, the AI service is unavailable right now. Please try again in a moment.",
                        "live": None, "source": "rag", "fast": False}
            _chat_cache_set(user.id, payload.message, "", reply)
            logger.info("AI_REQUEST_END id=%s provider=ollama duration=%.2fs ok=True", request_id, time.time()-t_start)
            return {"reply": reply, "live": None, "source": "rag", "fast": False}
        except HTTPException as exc:
            elapsed = time.time() - t_llm
            last_error = exc
            is_validation = exc.status_code in (400, 422)
            logger.warning("AI_PROVIDER_RESPONSE id=%s attempt=%d duration=%.2fs ok=False status=%d validation=%s",
                           request_id, attempt+1, elapsed, exc.status_code, is_validation)
            if is_validation or attempt >= _CHAT_MAX_RETRIES:
                break
        except Exception as exc:
            elapsed = time.time() - t_llm
            last_error = exc
            is_validation = False
            logger.warning("AI_PROVIDER_RESPONSE id=%s attempt=%d duration=%.2fs ok=False err=%s",
                           request_id, attempt+1, elapsed, exc)
            if attempt >= _CHAT_MAX_RETRIES:
                break
        if attempt < _CHAT_MAX_RETRIES:
            await asyncio.sleep(delay)

    logger.info("AI_REQUEST_END id=%s provider=ollama duration=%.2fs ok=False error=%s",
                request_id, time.time()-t_start, last_error)
    if last_error and hasattr(last_error, 'status_code') and last_error.status_code == 504:
        return {"success": False, "error": "AI provider timeout",
                "message": "The AI service took too long to respond. Please try again."}
    return {"success": False, "error": "AI response failed",
            "message": "AI response failed. Please try again."}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat/stream")
async def chat_stream(payload: schemas.ChatMessageIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """SSE streaming chat. Live questions stream instantly; LLM answers stream
    token-by-token so the first words appear within the timeout."""
    request_id = f"chat-{int(time.time()*1000)}-{user.id}"
    t_start = time.time()
    logger.info("AI_REQUEST_START id=%s user=%s msg=%s stream=True", request_id, user.id, payload.message[:80])

    ctx = rag_service.build_context(db, user, payload.message)

    if ctx["live"]:
        reply = ctx["live"]["answer"]
        if ctx["live"].get("detail"):
            reply += "\n" + ctx["live"]["detail"]

        async def gen_live():
            yield _sse({"delta": reply})
            yield _sse({"done": True, "reply": reply})

        logger.info("AI_REQUEST_END id=%s provider=live duration=%.2fs ok=True", request_id, time.time()-t_start)
        return StreamingResponse(gen_live(), media_type="text/event-stream")

    cached = _chat_cache_get(user.id, payload.message, "")
    if cached is not None:
        async def gen_cache():
            yield _sse({"delta": cached})
            yield _sse({"done": True, "reply": cached})

        logger.info("AI_REQUEST_END id=%s provider=cache duration=%.2fs ok=True", request_id, time.time()-t_start)
        return StreamingResponse(gen_cache(), media_type="text/event-stream")

    history = _cap_history(payload.history)

    async def gen_stream():
        full = ""
        last_error = None
        for attempt in range(1 + _CHAT_MAX_RETRIES):
            full = ""
            delay = (2 ** attempt) * 0.5
            t_llm = time.time()
            logger.info("AI_PROVIDER_REQUEST id=%s attempt=%d model=%s timeout=%ds stream=True",
                         request_id, attempt+1, ai_service.settings.OLLAMA_MODEL, _CHAT_TIMEOUT_SECONDS)
            try:
                async for chunk in ai_service.ai_chat_stream(payload.message, history, ctx["context"]):
                    if not chunk:
                        continue
                    full += chunk
                    yield _sse({"delta": full})
                logger.info("AI_PROVIDER_RESPONSE id=%s attempt=%d duration=%.2fs ok=True stream=True",
                            request_id, attempt+1, time.time()-t_llm)
                break
            except HTTPException as exc:
                elapsed = time.time() - t_llm
                last_error = exc
                is_validation = exc.status_code in (400, 422)
                logger.warning("AI_PROVIDER_RESPONSE id=%s attempt=%d duration=%.2fs ok=False status=%d validation=%s",
                               request_id, attempt+1, elapsed, exc.status_code, is_validation)
                if is_validation or attempt >= _CHAT_MAX_RETRIES:
                    break
            except Exception as exc:
                elapsed = time.time() - t_llm
                last_error = exc
                logger.warning("AI_PROVIDER_RESPONSE id=%s attempt=%d duration=%.2fs ok=False err=%s",
                               request_id, attempt+1, elapsed, exc)
                if attempt >= _CHAT_MAX_RETRIES:
                    break
            if attempt < _CHAT_MAX_RETRIES:
                await asyncio.sleep(delay)
        if not full.strip():
            if last_error and hasattr(last_error, 'status_code') and last_error.status_code == 504:
                err = _structured_error("AI provider timeout",
                                        "The AI service took too long to respond. Please try again.")
            else:
                err = _structured_error("AI response failed", "AI error occurred. Please try again.")
            logger.info("AI_REQUEST_END id=%s provider=ollama duration=%.2fs ok=False error=%s",
                        request_id, time.time()-t_start, err["error"])
            yield _sse(err)
            return
        _chat_cache_set(user.id, payload.message, "", full)
        logger.info("AI_REQUEST_END id=%s provider=ollama duration=%.2fs ok=True", request_id, time.time()-t_start)
        yield _sse({"done": True, "reply": full})

    return StreamingResponse(gen_stream(), media_type="text/event-stream")


@router.post("/shortlist")
async def shortlist(payload: schemas.ShortlistIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Apply the AI shortlisting rules to a match score (or compute it live from
    resume text + job, then apply). Returns the decision, category, and action.

    Thresholds (configurable product decision, HR-friendly):
      >= 80 Recommended / auto-interview | 40-79 HR Review | < 40 Auto Reject.
    """
    score = payload.matchPercent
    job = None
    if payload.jobId:
        job = get_job_or_404(db, payload.jobId)
    if score is None and payload.resumeText:
        if job is None:
            raise HTTPException(status_code=400, detail="jobId is required when computing the match from resume text.")
        result = await ai_service.ai_detailed_match(payload.resumeText, job)
        score = (result or {}).get("overallMatch", 0)
    if score is None:
        raise HTTPException(status_code=400, detail="Provide matchPercent (or resumeText + jobId).")
    decision = shortlist_for_score(score)
    decision["rankLabel"] = rank_label_for_score(score)
    decision["thresholds"] = {"autoInterviewMin": 95, "hrReviewMin": 80, "manualEvaluationMin": 40}
    if job:
        decision["job"] = {"id": job.id, "title": job.title, "dept": job.dept}
    return decision


@router.post("/compose-email")
async def compose_email(payload: schemas.AiComposeEmailIn, user=Depends(get_current_user)):
    """AI-powered email composer. Generates professional email content from a prompt."""
    context_map = {
        "interview_invite": "Generate a professional interview invitation email",
        "reminder": "Generate a professional interview reminder email",
        "rejection": "Generate a professional and empathetic rejection email",
        "offer": "Generate a professional job offer letter email",
        "follow_up": "Generate a professional follow-up email",
        "document_request": "Generate a professional document request email",
        "general": "Generate a professional business email",
    }

    context_instruction = context_map.get(payload.context, context_map["general"])

    prompt = (
        f"{context_instruction}.\n\n"
        f"Candidate Name: {payload.candidateName or 'the candidate'}\n"
        f"Job Title: {payload.jobTitle or 'the position'}\n"
        f"Company: {payload.companyName}\n"
        f"Additional context from HR: {payload.prompt}\n\n"
        "Return the result as JSON with exactly these keys:\n"
        "subject: the email subject line\n"
        "body: the full email body (use proper paragraphs, professional tone)\n"
        "Do NOT include any other keys. Return valid JSON only."
    )

    try:
        raw = await ai_service.call_ai("You are a professional HR email composer.", prompt, max_tokens=800)
    except Exception as e:
        logger.warning("AI compose-email failed: %s", e)
        raw = None
    if not raw:
        return {
            "subject": f"Regarding {payload.jobTitle or 'your application'} at {payload.companyName}",
            "body": f"Dear {payload.candidateName or 'Candidate'},\n\n{payload.prompt}\n\nBest regards,\n{payload.companyName} HR Team"
        }

    import json
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:-1])
        data = json.loads(cleaned)
        return {"subject": data.get("subject", ""), "body": data.get("body", "")}
    except (json.JSONDecodeError, KeyError):
        return {
            "subject": f"Regarding {payload.jobTitle or 'your application'} at {payload.companyName}",
            "body": raw
        }


@router.post("/send-email")
async def send_email(payload: schemas.SendEmailIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Send an email directly from the email composer."""
    from .. import email_service
    from ..routers.emails import record_email
    result = email_service.send_email_direct(
        to_emails=payload.to,
        cc_emails=payload.cc,
        bcc_emails=payload.bcc,
        subject=payload.subject,
        body=payload.body,
    )
    sent_status = result.get("sent", 0) > 0
    for to in payload.to:
        record_email(
            db, to, payload.subject, payload.body, "ai", "composed",
            "sent" if sent_status else "failed",
            error="" if sent_status else result.get("message", ""),
            cc=", ".join(payload.cc), bcc=", ".join(payload.bcc),
            referral_id=payload.referralId or "", job_id=payload.jobId or "",
            created_by=f"{user.name} ({user.role})",
        )
    return result


@router.post("/deep-screen")
async def deep_screen(payload: schemas.DeepScreenIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    """Run the advanced AI screening (candidate passport) for a referral.

    Computes deterministic heuristics (employment gaps, date integrity,
    credibility, duplicates) plus an AI narrative of the fake-experience /
    resume-risk verdict, then persists the passport on the referral.
    """
    from .. import screening as screening_mod

    referral = db.query(models.Referral).filter(models.Referral.id == payload.referralId).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    passport = screening_mod.deep_screen(db, referral)

    # AI narrative — best-effort; heuristics above are the source of truth.
    narrative = ""
    if referral.resume_text:
        try:
            prompt = (
                "You are an experienced HR fraud reviewer. A candidate resume has these automated screening "
                f"findings:\n{json.dumps(passport, default=str)[:1600]}\n\n"
                "Write a concise, professional risk assessment for HR (2-4 sentences). State whether "
                "experience appears genuine or shows signs of fabrication/exaggeration, note any employment "
                "gaps or duplicate concerns, and recommend a verification step (e.g. 'verify with offer "
                "letters / LinkedIn'). Do not mention this prompt."
            )
            raw = await ai_service.call_ai("You are a senior HR screening analyst.", prompt, max_tokens=350)
            if raw:
                narrative = raw.strip()
        except Exception as exc:
            logger.warning("deep-screen AI narrative failed: %s", exc)

    passport["aiNarrative"] = narrative
    referral.screening = passport
    db.commit()

    from .admin import log_audit
    from .activity import log_activity
    log_activity(db, referral.id, "AI Deep Screening",
                 f"Advanced screening run — risk level {passport['riskLevel']} (score {passport['riskScore']}/100).",
                 user.name)
    log_audit(db, user, "AI deep-screen referral", target="referral", target_id=referral.id,
              details=f"Candidate: {referral.candidate_name} | risk {passport['riskScore']}/100 | "
                      f"{len(passport['redFlags'])} flag(s)")

    return {"passport": passport, "referralId": referral.id}


# ====================== AI Email Communication Assistant ======================

class EmailAssistantChatIn(BaseModel):
    referralId: str
    message: str
    currentSubject: str = ""
    currentBody: str = ""


class EmailAssistantSendIn(BaseModel):
    referralId: str
    to: str
    cc: str = ""
    bcc: str = ""
    subject: str
    body: str


def _build_candidate_context(db: Session, referral: models.Referral) -> dict:
    job = db.query(models.Job).filter(models.Job.id == referral.job_id).first() if referral.job_id else None
    referrer = db.query(models.Employee).filter(models.Employee.id == referral.referred_by).first() if referral.referred_by else None
    interviews = db.query(models.Interview).filter(
        models.Interview.referral_id == referral.id,
        models.Interview.is_deleted == False,
    ).order_by(models.Interview.created_at.desc()).all()

    interview_data = []
    for iv in interviews:
        interview_data.append({
            "round": iv.round_name,
            "type": iv.interview_type,
            "date": iv.interview_date,
            "startTime": iv.start_time,
            "endTime": iv.end_time,
            "interviewer": iv.interviewer,
            "status": iv.status,
            "result": iv.result,
            "meetingLink": iv.meeting_link,
            "location": iv.location,
        })

    return {
        "candidateName": referral.candidate_name,
        "email": referral.email or "",
        "phone": referral.phone or "",
        "status": referral.status,
        "jobTitle": job.title if job else "",
        "jobDept": job.dept if job else "",
        "jobLocation": job.location if job else "",
        "jobSkills": job.skills if job else [],
        "matchPercent": referral.match_percent or 0,
        "referredByName": referrer.name if referrer else "",
        "referredByEmail": referrer.email if referrer else "",
        "submittedDate": referral.submitted_date.strftime("%d %b %Y") if referral.submitted_date else "",
        "skills": referral.skills or [],
        "currentCompany": referral.current_company or "",
        "currentDesignation": referral.current_designation or "",
        "totalExperience": referral.total_experience or "",
        "location": referral.location or "",
        "education": referral.education or "",
        "interviews": interview_data,
        "strengths": referral.strengths or [],
        "weaknesses": referral.weaknesses or [],
    }


def _build_context_prompt(ctx: dict) -> str:
    lines = [
        f"Candidate: {ctx['candidateName']}",
        f"Email: {ctx['email']}" if ctx['email'] else "",
        f"Phone: {ctx['phone']}" if ctx['phone'] else "",
        f"Current Status: {ctx['status']}",
        f"Position: {ctx['jobTitle']}" if ctx['jobTitle'] else "",
        f"Department: {ctx['jobDept']}" if ctx['jobDept'] else "",
        f"Location: {ctx['jobLocation']}" if ctx['jobLocation'] else "",
        f"Match Score: {ctx['matchPercent']}%" if ctx['matchPercent'] else "",
        f"Referred By: {ctx['referredByName']} ({ctx['referredByEmail']})" if ctx['referredByName'] else "",
        f"Applied: {ctx['submittedDate']}" if ctx['submittedDate'] else "",
        f"Skills: {', '.join(ctx['skills'])}" if ctx['skills'] else "",
        f"Experience: {ctx['totalExperience']}" if ctx['totalExperience'] else "",
        f"Education: {ctx['education']}" if ctx['education'] else "",
    ]
    if ctx['interviews']:
        lines.append("Interview History (newest first):")
        for iv in ctx['interviews']:
            status_str = f" [{iv['status']}]" if iv.get('status') else ""
            date_str = f" on {iv['date']}" if iv.get('date') else ""
            time_str = f" at {iv['startTime']}" if iv.get('startTime') else ""
            interviewer_str = f" with {iv['interviewer']}" if iv.get('interviewer') else ""
            link_str = f" (Link: {iv['meetingLink']})" if iv.get('meetingLink') else ""
            lines.append(f"  - {iv['round']}{status_str}{date_str}{time_str}{interviewer_str}{link_str}")
    return "\n".join(l for l in lines if l)


STRUCTURED_EMAIL_SYSTEM = """You are MuraAI, a professional HR communication assistant for an enterprise recruitment platform.

You generate STRUCTURED, PROFESSIONAL emails for candidate communications. You NEVER write unstructured paragraphs.

When the HR message is informal, poorly spelled, or incomplete (e.g. "hi akash my 6 months compleetd can i apply incntive"), you FIRST infer the true intent — correct grammar, spelling, punctuation and sentence structure — then produce a polished, professional email. You understand what the user means even when the phrasing is broken, and you preserve the original intent, names, dates, amounts, and facts exactly. You never invent details the user did not provide. If the user's wording is already clear and professional, only improve it where necessary.

Every email you generate MUST follow this structure:
1. Greeting (Dear [Name],)
2. Opening statement (1 sentence)
3. Purpose of the email
4. Key details section (formatted with labels and values, using **bold** labels)
5. Action required (if any)
6. Closing (1-2 sentences)
7. Signature

For interview-related emails, you MUST include an "Interview Details" section with:
- Date
- Time
- Interview Type
- Position
- Department
- Interviewer (if known)
- Meeting Link (if available)

CRITICAL RULES:
- You MUST use the candidate's actual name from the context.
- You must ONLY use facts explicitly present in the provided context. NEVER invent dates, times, interviewer names, meeting links, phone numbers, or URLs. If a detail is missing or marked "Not set", write "will be shared shortly" or "to be confirmed" instead.
- Do not use markdown tables, bullet dashes, or code blocks. Format details as simple lines like: **Date:** Thursday, 27 August 2026
- Do not wrap the whole answer in bold or headings.
- Avoid unnecessarily complicated vocabulary. Keep the email natural, concise, accurate, and professional.
- If the HR's tone request is "friendly", "formal", "concise", or "polite", match that tone.

When the HR provides a REVISION request (like "make it shorter", "change the time", "add CC"), you modify ONLY the relevant part of the email without rewriting everything.

Your entire response MUST be exactly one JSON object and nothing else — no explanations before or after, no markdown code fences:
{"subject": "...", "body": "...", "missingInfo": ["...", ...]}"""


def _extract_ai_json(raw: str) -> dict:
    """Robustly extract a JSON object from an LLM response that may contain
    markdown fences, leading/trailing commentary, or extra prose."""
    cleaned = (raw or "").strip()
    # Prefer content inside a fenced block
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    else:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
    return json.loads(cleaned)


def _email_body_to_html(text: str) -> str:
    """Convert the plain-text composed email into clean HTML for delivery.
    Escapes HTML characters, converts **bold** to <b>, and newlines to <br>."""
    import html as _html
    escaped = _html.escape(text or "")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped.replace("\n", "<br>")


@router.get("/email-assistant/employees")
async def email_assistant_employees(
    search: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_hr),
):
    """Search employees for CC/BCC fields."""
    q = db.query(models.Employee).filter(models.Employee.is_active == True)
    if search:
        like = f"%{search}%"
        q = q.filter(
            models.Employee.name.ilike(like) |
            models.Employee.email.ilike(like)
        )
    employees = q.order_by(models.Employee.name).limit(30).all()
    return [{"name": e.name, "email": e.email, "dept": e.dept or ""} for e in employees]


@router.get("/email-assistant/candidates")
async def email_assistant_candidates(
    search: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_hr),
):
    q = db.query(models.Referral).filter(models.Referral.is_deleted == False)
    if search:
        like = f"%{search}%"
        q = q.filter(
            models.Referral.candidate_name.ilike(like) |
            models.Referral.email.ilike(like)
        )
    referrals = q.order_by(models.Referral.submitted_date.desc()).limit(100).all()

    results = []
    for r in referrals:
        job = db.query(models.Job).filter(models.Job.id == r.job_id).first() if r.job_id else None
        referrer = db.query(models.Employee).filter(models.Employee.id == r.referred_by).first() if r.referred_by else None
        interviews = db.query(models.Interview).filter(
            models.Interview.referral_id == r.id,
            models.Interview.is_deleted == False,
        ).all()
        results.append({
            "referralId": r.id,
            "candidateName": r.candidate_name,
            "email": r.email or "",
            "phone": r.phone or "",
            "status": r.status,
            "jobId": r.job_id or "",
            "jobTitle": job.title if job else "",
            "jobDept": job.dept if job else "",
            "jobLocation": job.location if job else "",
            "matchPercent": r.match_percent or 0,
            "referredByName": referrer.name if referrer else "",
            "referredByEmail": referrer.email if referrer else "",
            "submittedDate": r.submitted_date.strftime("%d %b %Y") if r.submitted_date else "",
            "skills": r.skills or [],
            "currentCompany": r.current_company or "",
            "currentDesignation": r.current_designation or "",
            "totalExperience": r.total_experience or "",
            "location": r.location or "",
            "interviews": [{"round": iv.round_name, "date": iv.interview_date, "time": iv.start_time, "endTime": iv.end_time, "interviewer": iv.interviewer, "status": iv.status, "type": iv.interview_type, "meetingLink": iv.meeting_link, "location": iv.location} for iv in interviews],
        })
    return results


@router.post("/email-assistant/chat")
async def email_assistant_chat(
    payload: EmailAssistantChatIn,
    db: Session = Depends(get_db),
    user=Depends(require_hr),
):
    referral = db.query(models.Referral).filter(models.Referral.id == payload.referralId).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    ctx = _build_candidate_context(db, referral)
    ctx_prompt = _build_context_prompt(ctx)

    msg_lower = payload.message.lower()
    intent = "general"
    if any(w in msg_lower for w in ["interview invitation", "invite", "schedule interview", "interview for"]):
        intent = "interview_invite"
    elif any(w in msg_lower for w in ["reminder", "remind"]):
        intent = "reminder"
    elif any(w in msg_lower for w in ["reject", "rejection", "unfortunately", "not selected", "not moving forward"]):
        intent = "rejection"
    elif any(w in msg_lower for w in ["shortlist", "shortlisted", "proceed to", "move forward"]):
        intent = "shortlist"
    elif any(w in msg_lower for w in ["offer", "offered", "pleased to offer", "extending an offer"]):
        intent = "offer"
    elif any(w in msg_lower for w in ["availability", "available", "free", "schedule a time"]):
        intent = "availability"
    elif any(w in msg_lower for w in ["document", "submit", "resume", "certificates", "Upload"]):
        intent = "document_request"
    elif any(w in msg_lower for w in ["thank", "appreciation", "grateful"]):
        intent = "thank_you"
    elif any(w in msg_lower for w in ["reschedule", "postpone", "move to"]):
        intent = "reschedule"
    elif any(w in msg_lower for w in ["follow", "follow-up", "following up"]):
        intent = "follow_up"

    is_revision = bool(payload.currentSubject and payload.currentBody)

    hr_msg = models.EmailChatMessage(
        referral_id=payload.referralId,
        role="hr",
        content=payload.message,
        created_by=user.name,
    )
    db.add(hr_msg)

    intent_descriptions = {
        "interview_invite": "Generate a structured interview invitation email.",
        "reminder": "Generate a structured interview reminder email.",
        "rejection": "Generate a professional, empathetic rejection email.",
        "shortlist": "Generate a shortlist notification email.",
        "offer": "Generate a structured job offer letter email.",
        "availability": "Generate an email asking the candidate for their availability.",
        "document_request": "Generate an email requesting the candidate to submit required documents.",
        "thank_you": "Generate a professional thank-you email after an interview.",
        "reschedule": "Generate an email informing about interview rescheduling.",
        "follow_up": "Generate a professional follow-up email.",
        "general": "Generate a professional HR email based on the instruction.",
    }

    interview_ctx = ""
    if ctx["interviews"]:
        latest = ctx["interviews"][0]
        interview_ctx = (
            f"\nLatest scheduled interview:\n"
            f"  Round: {latest['round']}\n"
            f"  Type: {latest.get('type', 'Online')}\n"
            f"  Date: {latest.get('date', 'Not set')}\n"
            f"  Time: {latest.get('startTime', 'Not set')}"
            f"{' - ' + latest.get('endTime', '') if latest.get('endTime') else ''}\n"
            f"  Interviewer: {latest.get('interviewer', 'Details will be shared shortly')}\n"
            f"  Meeting Link: {latest.get('meetingLink', 'Will be provided')}\n"
            f"  Location: {latest.get('location', 'Online')}\n"
            f"  Status: {latest.get('status', 'Scheduled')}\n"
        )
    else:
        interview_ctx = (
            "\nIMPORTANT: No interview has been scheduled yet for this candidate. "
            "You must NOT invent any date, time, interviewer name, or meeting link. "
            "Use phrases like \"will be shared shortly\" or \"to be confirmed\" instead.\n"
        )

    if is_revision:
        ai_prompt = (
            f"The HR wants to REVISE the existing email. Make ONLY the requested changes.\n\n"
            f"=== CURRENT EMAIL ===\n"
            f"Subject: {payload.currentSubject}\n"
            f"Body:\n{payload.currentBody}\n\n"
            f"=== CANDIDATE CONTEXT ===\n{ctx_prompt}\n"
            f"{interview_ctx}\n"
            f"=== REVISION REQUEST ===\n{payload.message}\n\n"
            f"Modify the email according to the revision request. Keep everything else the same.\n"
            f"The signature must end with: {user.name}, MuraAI Refer (replace any [HR Name] placeholder).\n"
            f"Return exactly one JSON object: {{\"subject\": \"...\", \"body\": \"...\", \"missingInfo\": []}}"
        )
    else:
        ai_prompt = (
            f"{intent_descriptions.get(intent, intent_descriptions['general'])}\n\n"
            f"=== CANDIDATE CONTEXT ===\n{ctx_prompt}\n"
            f"{interview_ctx}\n"
            f"=== HR INSTRUCTION ===\n{payload.message}\n\n"
            f"The HR instruction may be informal or contain spelling/grammar mistakes — infer the real intent, "
            f"correct the grammar and spelling, then generate the email accordingly. Do NOT copy the raw informal "
            f"wording into the email.\n"
            f"Generate a STRUCTURED email. Use this format:\n"
            f"- Greeting: Dear [Candidate Name],\n"
            f"- Opening: 1 sentence acknowledging the context\n"
            f"- Purpose: Clear statement of why you're writing\n"
            f"- Details section with **bold labels** and values (simple lines, no tables)\n"
            f"- Action required (if any)\n"
            f"- Closing: Professional sign-off\n"
            f"- Signature: {user.name}, MuraAI Refer\n\n"
            f"Rules:\n"
            f"- Use the candidate's ACTUAL name (never 'Candidate')\n"
            f"- Use ONLY facts from the context above — never invent dates, times, interviewer names, or links\n"
            f"- Preserve names, dates, amounts, and technical terms from the instruction exactly\n"
            f"- If interview time/date is 'Not set', write 'will be shared shortly'\n"
            f"- Professional, warm, enterprise tone; clear sections, not one long paragraph\n"
            f"- Keep sentences concise and clear (natural, not overly complex vocabulary)\n"
            f"Return exactly one JSON object: {{\"subject\": \"...\", \"body\": \"...\", \"missingInfo\": [...]}}"
        )

    try:
        raw = await ai_service.call_ai(STRUCTURED_EMAIL_SYSTEM, ai_prompt, max_tokens=1200)
    except Exception as e:
        logger.warning("AI email-assistant failed: %s", e)
        raw = None

    email_subject = ""
    email_body = ""
    missing_info = []
    ai_reply = ""

    if raw:
        try:
            data = _extract_ai_json(raw)
            email_subject = (data.get("subject") or "").strip()
            email_body = (data.get("body") or "").strip()
            missing_info = data.get("missingInfo") or []
            if is_revision:
                ai_reply = "I've updated the email as requested."
            else:
                ai_reply = f"I've prepared the {intent.replace('_', ' ')} email for {ctx['candidateName']}."
        except (json.JSONDecodeError, ValueError, AttributeError):
            # JSON extraction failed — strip obvious fences and use the raw text as body
            fallback = re.sub(r"```(?:json)?|```", "", raw).strip()
            email_subject = f"Regarding {ctx['jobTitle'] or 'Your Application'} — MuraAI"
            email_body = fallback
            missing_info = []
            ai_reply = f"I've prepared a draft for {ctx['candidateName']}. Please review it carefully."
    else:
        email_subject = f"Regarding Your Application — {ctx['jobTitle'] or 'MuraAI'}"
        email_body = (
            f"Dear {ctx['candidateName']},\n\n"
            f"{payload.message}\n\n"
            f"We will be in touch with further details.\n\n"
            f"Best regards,\n{user.name}\nMuraAI Refer"
        )
        ai_reply = "AI was unavailable. A basic template has been generated."

    ai_msg = models.EmailChatMessage(
        referral_id=payload.referralId,
        role="ai",
        content=ai_reply,
        email_subject=email_subject,
        email_body=email_body,
        email_to=ctx["email"],
        created_by="MuraAI",
    )
    db.add(ai_msg)
    db.commit()

    return {
        "reply": ai_reply,
        "emailPreview": {
            "to": ctx["email"],
            "toName": ctx["candidateName"],
            "subject": email_subject,
            "body": email_body,
        },
        "missingInfo": missing_info,
        "intent": intent,
    }


@router.post("/email-assistant/send")
async def email_assistant_send(
    payload: EmailAssistantSendIn,
    db: Session = Depends(get_db),
    user=Depends(require_hr),
):
    from .. import email_service
    from ..routers.emails import record_email

    referral = db.query(models.Referral).filter(models.Referral.id == payload.referralId).first()
    job_id = referral.job_id if referral else ""

    to_list = [payload.to] if payload.to else []
    cc_list = [e.strip() for e in payload.cc.split(",") if e.strip()] if payload.cc else []
    bcc_list = [e.strip() for e in payload.bcc.split(",") if e.strip()] if payload.bcc else []

    result = email_service.send_email_direct(
        to_emails=to_list,
        cc_emails=cc_list,
        bcc_emails=bcc_list,
        subject=payload.subject,
        body=_email_body_to_html(payload.body),
    )
    sent_status = result.get("sent", 0) > 0

    for to in to_list:
        record_email(
            db, to, payload.subject, payload.body,
            "ai", "composed",
            "sent" if sent_status else "failed",
            error="" if sent_status else result.get("message", ""),
            cc=", ".join(cc_list), bcc=", ".join(bcc_list),
            referral_id=payload.referralId,
            job_id=job_id or "",
            created_by=f"{user.name} ({user.role})",
        )

    chat_msg = db.query(models.EmailChatMessage).filter(
        models.EmailChatMessage.referral_id == payload.referralId,
        models.EmailChatMessage.role == "ai",
        models.EmailChatMessage.email_subject == payload.subject,
    ).order_by(models.EmailChatMessage.created_at.desc()).first()
    if chat_msg:
        chat_msg.email_sent = True
        db.commit()

    cc_str = f", CC: {payload.cc}" if payload.cc else ""
    sys_msg = models.EmailChatMessage(
        referral_id=payload.referralId,
        role="system",
        content=f"Email sent to {payload.to}{cc_str} — Subject: {payload.subject}",
        created_by=user.name,
    )
    db.add(sys_msg)
    db.commit()

    return result


@router.get("/email-assistant/history/{referral_id}")
async def email_assistant_history(
    referral_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_hr),
):
    chat_msgs = db.query(models.EmailChatMessage).filter(
        models.EmailChatMessage.referral_id == referral_id,
    ).order_by(models.EmailChatMessage.created_at.asc()).all()

    chat_history = []
    for m in chat_msgs:
        chat_history.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "emailSubject": m.email_subject,
            "emailBody": m.email_body,
            "emailTo": m.email_to,
            "emailSent": m.email_sent,
            "createdBy": m.created_by,
            "createdAt": m.created_at.isoformat() if m.created_at else "",
        })

    email_records = db.query(models.EmailRecord).filter(
        models.EmailRecord.referral_id == referral_id,
    ).order_by(models.EmailRecord.created_at.desc()).limit(50).all()

    email_history = []
    for e in email_records:
        email_history.append({
            "id": e.id,
            "toEmail": e.to_email,
            "subject": e.subject,
            "status": e.status,
            "category": e.category,
            "emailType": e.email_type,
            "createdBy": e.created_by,
            "createdAt": e.created_at.isoformat() if e.created_at else "",
        })

    return {"chatHistory": chat_history, "emailHistory": email_history}
