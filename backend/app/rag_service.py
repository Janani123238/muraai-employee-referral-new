"""Real-time, role-aware RAG context builder for the MuraAI AI Assistant.

Unlike a static FAQ, this service answers strictly from live database data:
jobs, referrals, interviews, offers, email history and policy — scoped to the
caller's role. For common quantitative questions it computes the exact number
from the database first, then lets the LLM phrase the answer, so the assistant
never returns a canned/hardcoded response.

Employee scope    -> own referrals + open jobs + policy + rewards
Manager scope     -> own + team (same department) referrals + jobs + policy
HR / Admin scope  -> everything (all referrals, interviews, offers, emails)
"""
import re
import time
from datetime import datetime, date, timedelta

from . import models
from .auth import HR_ROLES
from . import vector_store

_TODAY_CACHE = {}
_CONTEXT_CACHE = {}
_CONTEXT_CACHE_TTL = 60  # seconds - context changes when data updates


def _today():
    return date.today()


def _context_key(user_id, message):
    """Create a cache key for the conversation context."""
    return f"{user_id}|{message.strip()[:200]}"


def is_hr_role(role: str) -> bool:
    return role in HR_ROLES


def _referrer_name(db, referral):
    emp = db.query(models.Employee).filter(models.Employee.id == referral.referred_by).first()
    return emp.name if emp else "—"


def scoped_referrals(db, user):
    """Return the referrals the given user is allowed to see (soft-deleted rows are excluded)."""
    base = models.Referral.is_deleted.is_(False)
    if is_hr_role(user.role):
        return db.query(models.Referral).filter(base).all()
    if user.role == "manager" and user.employee_id:
        me = db.query(models.Employee).filter(models.Employee.id == user.employee_id).first()
        dept = me.dept if me else ""
        emp_ids = [e.id for e in db.query(models.Employee).filter(models.Employee.dept == dept).all()] if dept else [user.employee_id]
        if user.employee_id not in emp_ids:
            emp_ids.append(user.employee_id)
        return db.query(models.Referral).filter(base, models.Referral.referred_by.in_(emp_ids)).all()
    if user.employee_id:
        return db.query(models.Referral).filter(base, models.Referral.referred_by == user.employee_id).all()
    return []


def _job_title(db, job_id):
    if not job_id:
        return "—"
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    return job.title if job else "—"


def jd_context(db, job, query_text: str = "", max_chunks: int = 3) -> str:
    """Job-scoped RAG context for resume-vs-JD matching.

    Pulls this job's chunks from the vector index (sourceType='job') and,
    when the JD was split into more chunks than needed, ranks them by cosine
    similarity to `query_text` (usually the resume text) so only the relevant
    JD segments reach the LLM prompt. Falls back to concatenating the chunks
    (or rebuilding a summary from the raw job row) so matching never breaks
    when embeddings/Ollama are unavailable.
    """
    try:
        if job is None:
            return ""
        rows = (
            db.query(models.DocumentChunk)
            .filter(
                models.DocumentChunk.source_type == "job",
                models.DocumentChunk.source_id == getattr(job, "id", None),
            )
            .all()
        )
        contents = [(c.content or "").strip() for c in rows]
        contents = [c for c in contents if c]
        if not contents:
            # Index not built (or stale): rebuild a minimal JD body directly.
            skills = ", ".join(getattr(job, "skills", None) or [])
            body = (
                f"{getattr(job, 'title', '')} | dept: {getattr(job, 'dept', '')} | "
                f"exp: {getattr(job, 'exp', '')} | loc: {getattr(job, 'location', '')} | "
                f"skills: {skills}\n{getattr(job, 'description', '') or ''}"
            ).strip()
            return body[:2400]
        joined = "\n".join(contents)
        if len(contents) <= max_chunks:
            return joined[:2400]
        q = (query_text or "").strip()
        emb = vector_store.embed_text(q[:1800]) if q else None
        if not emb:
            return joined[:2400]

        def _cos(row):
            vec = vector_store._to_float_list(row.embedding)
            en = sum(v * v for v in vec) ** 0.5
            qn = sum(v * v for v in emb) ** 0.5
            if not en or not qn:
                return 0.0
            return sum(a * b for a, b in zip(emb, vec)) / (qn * en)

        ranked = sorted(zip(rows, contents), key=lambda rc: _cos(rc[0]), reverse=True)
        return "\n".join(content for _, content in ranked[:max_chunks])[:2400]
    except Exception as exc:
        import logging
        logging.getLogger("rag").warning("jd_context skipped: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Live question detection — computes real numbers/rows straight from the DB.
# ---------------------------------------------------------------------------
_LIVE_PATTERNS = [
    ("shortlisted_today", re.compile(r"(shortlist|candidates?).{0,20}(today|this week)", re.I),
     "count of candidates shortlisted/submitted into the interview pipeline today"),
    ("referrals_this_month", re.compile(r"(referrals?).{0,20}(this month|in the last 30 days|last month)", re.I),
     "referrals submitted this month"),
    ("pending_interviews", re.compile(r"(pending|upcoming|scheduled|scheduled interviews?)", re.I),
     "pending interviews"),
    ("active_jobs", re.compile(r"(active|open|live) jobs?", re.I),
     "open/active jobs"),
    ("rejected_candidates", re.compile(r"rejected candidates?", re.I),
     "rejected candidates"),
    ("pending_offers", re.compile(r"pending offers?", re.I),
     "pending offers"),
    ("conversion_rate", re.compile(r"(conversion|success) rate", re.I),
     "referral conversion rate"),
    ("who_referred", re.compile(r"who referred (.+?)(\?|$)", re.I),
     "referrer for a specific candidate"),
    ("candidate_status", re.compile(r"(status|stage) (of|for) (.+?)(\?|$)", re.I),
     "current status of a candidate"),
    ("my_referrals_count", re.compile(r"how many (referrals?|people) (have|did) (i|you)", re.I),
     "count of the user's own referrals"),
    ("total_hires", re.compile(r"(total hires?|hired (so far|overall|to date))", re.I),
     "total successful hires"),
    ("offer_acceptance", re.compile(r"(offer acceptance|accepted offers?)", re.I),
     "offer acceptance rate"),
    ("my_rewards", re.compile(r"(my )?(rewards?|bonus (payout|earned|eligible)|how much (is|are) (my )?(rewards?|bonus))", re.I),
     "the user's own referral rewards / bonus"),
]


def _detect_live_question(message: str):
    for key, pattern, _desc in _LIVE_PATTERNS:
        if pattern.search(message):
            return key
    return None


def _compute_live_answer(db, user, kind: str, message: str = "") -> dict:
    """Compute the precise answer for a detected question from live DB data."""
    refs = scoped_referrals(db, user)
    today = _today()
    month_start = datetime(today.year, today.month, 1)
    yesterday = datetime.now() - timedelta(days=1)

    def in_range(dt, start):
        return dt and dt >= start

    jobs = db.query(models.Job).filter(models.Job.is_deleted.is_(False)).all()

    if kind == "shortlisted_today":
        pipeline = {"Shortlisted", "Interview Scheduled", "Interview Completed", "Selected", "Offer Released", "Offer", "Joined", "Technical Round", "Manager Round", "HR Round"}
        rows = [r for r in refs if r.status in pipeline and in_range(r.submitted_date, yesterday)]
        names = ", ".join(f"{r.candidate_name} ({r.status})" for r in rows[:8])
        return {"answer": f"{len(rows)} candidate(s) were shortlisted/advanced into the interview pipeline today.", "detail": names, "count": len(rows)}

    if kind == "referrals_this_month":
        rows = [r for r in refs if in_range(r.submitted_date, month_start)]
        return {"answer": f"{len(rows)} referral(s) were submitted this month.", "detail": ", ".join(r.candidate_name for r in rows[:8]), "count": len(rows)}

    if kind == "pending_interviews":
        pending = [iv for r in refs for iv in (r.interviews or []) if iv.status in ("Scheduled", "Rescheduled", "Pending")]
        detail = ", ".join(f"{iv.candidate_name} ({iv.round_name}, {iv.interview_date})" for iv in pending[:8])
        return {"answer": f"{len(pending)} interview(s) are currently pending/scheduled.", "detail": detail, "count": len(pending)}

    if kind == "active_jobs":
        open_jobs = [j for j in jobs if (j.status or "").lower() == "open"]
        return {"answer": f"There {'is' if len(open_jobs) == 1 else 'are'} {len(open_jobs)} active open job(s).", "detail": ", ".join(j.title for j in open_jobs[:10]), "count": len(open_jobs)}

    if kind == "rejected_candidates":
        rows = [r for r in refs if r.status == "Rejected"]
        return {"answer": f"{len(rows)} candidate(s) have been rejected.", "detail": ", ".join(r.candidate_name for r in rows[:8]), "count": len(rows)}

    if kind == "pending_offers":
        rows = [r for r in refs if r.status in ("Offer Released", "Offer", "Selected")]
        return {"answer": f"{len(rows)} offer(s) are pending/outstanding.", "detail": ", ".join(r.candidate_name for r in rows[:8]), "count": len(rows)}

    if kind == "conversion_rate":
        joined = sum(1 for r in refs if r.status == "Joined")
        rate = round(joined / len(refs) * 100) if refs else 0
        return {"answer": f"Referral conversion rate is {rate}% ({joined} hired out of {len(refs)} referrals).", "detail": f"{joined}/{len(refs)} joined", "count": rate}

    if kind == "who_referred":
        m = None
        for p in _LIVE_PATTERNS:
            if p[0] == "who_referred":
                m = p[1].search(message)
                break
        if not m:
            return {"answer": "Could not identify the candidate.", "detail": "", "count": 0}
        name = m.group(1).strip().strip("?.")
        matches = [r for r in refs if name.lower() in r.candidate_name.lower()]
        if not matches:
            return {"answer": f"No candidate named '{name}' was found in your visible referrals.", "detail": "", "count": 0}
        r = matches[0]
        return {"answer": f"{r.candidate_name} was referred by {_referrer_name(db, r)} for {_job_title(db, r.job_id)} (status: {r.status}).", "detail": "", "count": 1}

    if kind == "candidate_status":
        m = None
        for p in _LIVE_PATTERNS:
            if p[0] == "candidate_status":
                m = p[1].search(message)
                break
        if not m:
            return {"answer": "Could not identify the candidate.", "detail": "", "count": 0}
        name = m.group(3).strip().strip("?.")
        matches = [r for r in refs if name.lower() in r.candidate_name.lower()]
        if not matches:
            return {"answer": f"No candidate named '{name}' was found in your visible referrals.", "detail": "", "count": 0}
        r = matches[0]
        return {"answer": f"{r.candidate_name}'s current stage is '{r.status}' for {_job_title(db, r.job_id)} (match {r.match_percent or 0}%).", "detail": "", "count": 1}

    if kind == "my_referrals_count":
        return {"answer": f"You have submitted {len(refs)} referral(s).", "detail": ", ".join(r.candidate_name for r in refs[:8]), "count": len(refs)}

    if kind == "total_hires":
        joined = sum(1 for r in refs if r.status == "Joined")
        return {"answer": f"{joined} successful hire(s) in total.", "detail": "", "count": joined}

    if kind == "offer_acceptance":
        offers = sum(1 for r in refs if r.status in ("Offer Released", "Offer", "Selected"))
        joined = sum(1 for r in refs if r.status == "Joined")
        rate = round(joined / offers * 100) if offers else 0
        return {"answer": f"Offer acceptance rate is {rate}% ({joined} accepted out of {offers} offers).", "detail": "", "count": rate}

    if kind == "my_rewards":
        jobs = db.query(models.Job).filter(models.Job.is_deleted.is_(False)).all()
        job_bonus = {j.id: j.bonus or 0 for j in jobs}
        earned = sum(job_bonus.get(r.job_id, 0) for r in refs if r.status == "Joined")
        pending = sum(job_bonus.get(r.job_id, 0) for r in refs if r.status in ("Offer Released", "Offer", "Selected"))
        detail = ", ".join(
            f"{r.candidate_name} → ₹{job_bonus.get(r.job_id, 0):,}" for r in refs
            if r.status in ("Joined", "Offer Released", "Offer", "Selected")
        )[:300]
        return {"answer": f"Your earned referral bonus totals ₹{earned:,}, with ₹{pending:,} pending on outstanding offers.", "detail": detail, "count": earned}

    return {"answer": "", "detail": "", "count": 0}


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------
def build_context(db, user, message: str) -> dict:
    """Return {system, context, live} where live is a computed DB answer (or None).

    Designed for speed: quantitative/status questions short-circuit via `live`,
    and the LLM context is kept tight (recent referrals, concise KB summaries,
    and semantic top-k only for non-live questions). Uses caching to avoid
    rebuilding the context on repeated calls.
    """
    cache_k = _context_key(user.id, message)
    cached = _CONTEXT_CACHE.get(cache_k)
    if cached and cached["ts"] + _CONTEXT_CACHE_TTL > time.time():
        # Use cached context - but verify live data is still current
        ctx = cached["ctx"]
        # Recompute live answer from fresh DB data (it's cheap)
        kind = _detect_live_question(message)
        live = _compute_live_answer(db, user, kind, message) if kind else None
        ctx["live"] = live
        return ctx
    kind = _detect_live_question(message)
    live = _compute_live_answer(db, user, kind, message) if kind else None

    parts = []
    parts.append(f"Current user: {user.name} ({user.role}). Today is {_today().isoformat()}.")

    # Jobs - only open/active ones, limit count
    jobs = db.query(models.Job).filter(models.Job.is_deleted.is_(False)).all()
    open_jobs = [j for j in jobs if (j.status or "").lower() == "open"]
    job_lines = []
    for j in open_jobs[:10]:  # limit to 10 open jobs max
        status = j.status or "Open"
        skills = ", ".join(j.skills or [])
        job_lines.append(f"- {j.title} | dept: {j.dept} | exp: {j.exp} | loc: {j.location} | status: {status} | skills: {skills}")
    if open_jobs:
        parts.append("OPEN JOBS:\n" + "\n".join(job_lines))
    else:
        parts.append("OPEN JOBS: none posted yet.")

    # Referrals (scoped) - only recent + status summary to keep the prompt small
    refs = scoped_referrals(db, user)
    if refs:
        by_status = {}
        for r in refs:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        status_summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items(), key=lambda x: -x[1]))
        # Only show most recent 8 referrals
        recent = sorted(refs, key=lambda r: r.submitted_date or datetime.min, reverse=True)[:8]
        ref_lines = []
        for r in recent:
            score = r.match_percent or 0
            ref_lines.append(
                f"- {r.candidate_name} | job: {_job_title(db, r.job_id)} | "
                f"referred by: {_referrer_name(db, r)} | status: {r.status} | match: {score}%"
            )
        parts.append(
            f"REFERRALS (role-scoped, {len(refs)} total): status breakdown -> {status_summary}\n"
            + "RECENT:\n" + "\n".join(ref_lines)
        )
    else:
        parts.append("REFERRALS: none in your visible scope.")

    # Interviews (scoped, recent only) - limit to 8
    interviews = [iv for r in refs for iv in (r.interviews or [])]
    if interviews:
        iv_lines = [f"- {iv.candidate_name} | round: {iv.round_name} | date: {iv.interview_date} {iv.start_time} | status: {iv.status} | result: {iv.result or '—'}" for iv in interviews[:8]]
        parts.append("INTERVIEWS:\n" + "\n".join(iv_lines))

    # Offers / joined (scoped) - limit to 8
    offer_rows = [r for r in refs if r.status in ("Offer Released", "Offer", "Selected", "Joined")]
    if offer_rows:
        job_bonus = {j.id: j.bonus or 0 for j in open_jobs}  # use open_jobs instead of all jobs
        parts.append("OFFERS/HIRES:\n" + "\n".join(
            f"- {r.candidate_name} | status: {r.status} | job: {_job_title(db, r.job_id)} | bonus: ₹{job_bonus.get(r.job_id, 0)}" for r in offer_rows[:8]))

    # Email history (HR/admin only, recent, limit to 5)
    if is_hr_role(user.role):
        emails = db.query(models.EmailRecord).order_by(models.EmailRecord.created_at.desc()).limit(5).all()
        if emails:
            em_lines = [f"- {e.to_email} | {e.email_type} | {e.status} | subject: {e.subject}" for e in emails]
            parts.append("RECENT EMAIL HISTORY (sent via Email Center):\n" + "\n".join(em_lines))

    # Policy - limit to 800 chars
    policy = db.query(models.ReferralPolicy).first()
    if policy and policy.content:
        parts.append("REFERRAL POLICY:\n" + policy.content[:800])

    # Knowledge base (role-scoped) - concise titles/summaries; limit to 5 articles
    kb_audience = "hr" if is_hr_role(user.role) else "employee"
    kb_rows = (
        db.query(models.KnowledgeArticle).all()
        if kb_audience == "hr"
        else db.query(models.KnowledgeArticle)
        .filter(models.KnowledgeArticle.audience.in_(["all", "employee"]))
        .limit(5)  # limit KB articles
        .all()
    )
    if kb_rows:
        kb_lines = [f"- [{a.category}] {a.title}: {a.content[:140]}" for a in kb_rows]
        parts.append("KNOWLEDGE BASE:\n" + "\n".join(kb_lines))

    context = "\n\n".join(parts)

    # Semantic retrieval over the vector store (best-effort) — only for
    # open-ended questions; live questions already have an exact DB answer so
    # we skip the (slower) embedding round-trip entirely.
    if kind is None:
        try:
            relevant = vector_store.retrieve(db, message, audience=kb_audience, top_k=3)
            if relevant:
                semantic = [
                    f"- {r['title']}: {r['content'][:800]} (source: {r['sourceType']})"
                    for r in relevant
                ]
                context += "\n\nMOST RELEVANT KNOWLEDGE (semantic search):\n" + "\n".join(semantic)
        except Exception as exc:
            import logging
            logging.getLogger("rag").warning("vector retrieval skipped: %s", exc)

    system = (
        "You are MuraAI, the enterprise AI assistant for the MuraAI Refer referral platform. "
        "Answer using ONLY the live data in CONTEXT below (real database records). Never invent "
        "candidates, jobs, numbers, or statuses that are not in the context. If you have the exact "
        "answer, state it directly with numbers and names. If the question cannot be answered from "
        "context, say so and suggest what the user can ask instead. Keep answers concise and "
        "professional. Prefer plain English; use lists when helpful.\n\nCONTEXT:\n" + context
    )

    result = {"system": system, "context": context, "live": live}
    # Cache the context (without the system prompt, which is always the same structure)
    _CONTEXT_CACHE[cache_k] = {"ts": time.time(), "ctx": result}
    # Keep cache size manageable
    if len(_CONTEXT_CACHE) > 50:
        now = time.time()
        stale = [k for k, v in _CONTEXT_CACHE.items() if now - v["ts"] > _CONTEXT_CACHE_TTL]
        for k in stale:
            _CONTEXT_CACHE.pop(k, None)
    return result
