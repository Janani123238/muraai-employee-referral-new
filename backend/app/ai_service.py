import json
import re
import logging
import time
import httpx
from fastapi import HTTPException
from .config import settings

logger = logging.getLogger("ai_service")

OLLAMA_URL = "{base_url}/api/chat"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

OLLAMA_TIMEOUT_SECONDS = 120

# Cache for AI availability check (avoid repeated 30s timeouts)
_ai_available_cache = {"checked": False, "available": False}

async def _check_ai_available():
    """Quick check if the configured AI provider is reachable. Cached after first call."""
    global _ai_available_cache
    if _ai_available_cache["checked"]:
        return _ai_available_cache["available"]
    ps = _get_provider_settings()
    provider = ps["provider"]
    try:
        if provider == "ollama":
            url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags"
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(url)
                available = resp.status_code == 200
        elif provider == "openai":
            available = bool(ps.get("api_key") or settings.OPENAI_API_KEY)
        elif provider == "anthropic":
            available = bool(ps.get("api_key") or settings.ANTHROPIC_API_KEY)
        elif provider == "gemini":
            available = bool(ps.get("api_key") or settings.GEMINI_API_KEY)
        else:
            available = False
    except Exception:
        available = False
    _ai_available_cache = {"checked": True, "available": available}
    if not available:
        logger.warning("AI provider '%s' is not available — using fallback mode", provider)
    return available


def _get_provider_settings():
    """Read AI provider config from the database (app_settings table).
    Falls back to env-based config for Ollama."""
    try:
        from .database import SessionLocal
        from . import models
        db = SessionLocal()
        s = db.query(models.AppSettings).first()
        db.close()
        if s:
            return {
                "provider": s.ai_provider or "ollama",
                "model": s.ai_model or settings.OLLAMA_MODEL,
                "api_key": s.ai_api_key or "",
                "temperature": s.ai_temperature or 0.2,
                "max_tokens": s.ai_max_tokens or 1000,
            }
    except Exception:
        pass
    return {
        "provider": "ollama",
        "model": settings.OLLAMA_MODEL,
        "api_key": "",
        "temperature": 0.2,
        "max_tokens": 1000,
    }


_ai_timeout_cache = {"ts": 0.0, "value": None}


def settings_ai_timeout() -> float:
    """Configured AI timeout (seconds). Reads env AI_TIMEOUT_SECONDS (or DB
    ai_timeout if present) with a short TTL cache; falls back to 120s."""
    now = time.time()
    if now - _ai_timeout_cache["ts"] < 5:
        value = _ai_timeout_cache["value"]
        if value is not None:
            return value
        return OLLAMA_TIMEOUT_SECONDS
    _ai_timeout_cache["ts"] = now
    try:
        from .database import SessionLocal
        from . import models
        db = SessionLocal()
        s = db.query(models.AppSettings).first()
        db.close()
        if s:
            db_timeout = getattr(s, "ai_timeout", None)
            if db_timeout:
                value = float(db_timeout)
                _ai_timeout_cache["value"] = value
                return value
    except Exception:
        pass
    value = float(getattr(settings, "AI_TIMEOUT_SECONDS", OLLAMA_TIMEOUT_SECONDS) or OLLAMA_TIMEOUT_SECONDS)
    _ai_timeout_cache["value"] = value
    return value


async def call_ai(system: str, user_content: str, max_tokens: int = 1000, history=None, timeout: float = None) -> str:
    """Unified AI call that routes to the configured provider."""
    ps = _get_provider_settings()
    provider = ps["provider"]
    timeout = timeout or settings_ai_timeout()

    if provider == "openai":
        return await _call_openai(system, user_content, ps, max_tokens, history, timeout)
    elif provider == "gemini":
        return await _call_gemini(system, user_content, ps, max_tokens, history, timeout)
    elif provider == "anthropic":
        return await _call_anthropic(system, user_content, ps, max_tokens, history, timeout)
    else:
        return await call_ollama(system, user_content, max_tokens, history, timeout)


async def _call_openai(system: str, user_content: str, ps: dict, max_tokens: int, history=None, timeout: float = None) -> str:
    api_key = ps["api_key"] or settings.OPENAI_API_KEY if hasattr(settings, 'OPENAI_API_KEY') else ps.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key is not configured. Set it in Admin > AI Settings.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for item in history:
            if isinstance(item, dict):
                messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
    messages.append({"role": "user", "content": user_content})

    body = {
        "model": ps["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": ps["temperature"],
    }

    try:
        async with httpx.AsyncClient(timeout=timeout or OLLAMA_TIMEOUT_SECONDS) as client:
            resp = await client.post(OPENAI_URL, json=body, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI service timed out. Please try again.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach OpenAI: {exc}")

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="OpenAI returned an unreadable response")

    if resp.status_code != 200:
        detail = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
        raise HTTPException(status_code=502, detail=f"OpenAI error: {detail}")

    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not text.strip():
        raise HTTPException(status_code=502, detail="OpenAI returned an empty response")
    return text


async def _call_gemini(system: str, user_content: str, ps: dict, max_tokens: int, history=None, timeout: float = None) -> str:
    api_key = ps.get("api_key", "") or settings.GEMINI_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="Gemini API key is not configured. Set it in Admin > AI Settings.")

    contents = []
    if history:
        for item in history:
            if isinstance(item, dict):
                role = "user" if item.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": item.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": (system + "\n\n" + user_content) if system else user_content}]})

    model = ps["model"] or settings.GEMINI_MODEL
    url = GEMINI_URL.format(model=model)
    body = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": ps["temperature"]},
    }

    try:
        async with httpx.AsyncClient(timeout=timeout or OLLAMA_TIMEOUT_SECONDS) as client:
            resp = await client.post(url + f"?key={api_key}", json=body, headers={"Content-Type": "application/json"})
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gemini timed out. Please try again.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Gemini: {exc}")

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Gemini returned an unreadable response")

    if resp.status_code != 200:
        detail = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
        raise HTTPException(status_code=502, detail=f"Gemini error: {detail}")

    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    if not text.strip():
        raise HTTPException(status_code=502, detail="Gemini returned an empty response")
    return text


async def _call_anthropic(system: str, user_content: str, ps: dict, max_tokens: int, history=None, timeout: float = None) -> str:
    api_key = ps.get("api_key", "") or settings.ANTHROPIC_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key is not configured. Set it in Admin > AI Settings.")

    messages = []
    if history:
        for item in history:
            if isinstance(item, dict):
                messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
    messages.append({"role": "user", "content": user_content})

    model = ps["model"] or settings.ANTHROPIC_MODEL
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "temperature": ps["temperature"],
    }
    if system:
        body["system"] = system

    try:
        async with httpx.AsyncClient(timeout=timeout or OLLAMA_TIMEOUT_SECONDS) as client:
            resp = await client.post(ANTHROPIC_URL, json=body, headers={
                "x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"
            })
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Anthropic timed out. Please try again.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Anthropic: {exc}")

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Anthropic returned an unreadable response")

    if resp.status_code != 200:
        detail = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
        raise HTTPException(status_code=502, detail=f"Anthropic error: {detail}")

    text = data.get("content", [{}])[0].get("text", "")
    if not text.strip():
        raise HTTPException(status_code=502, detail="Anthropic returned an empty response")
    return text


async def call_ollama(system: str, user_content: str, max_tokens: int = 1000, history=None, timeout: float = None) -> str:
    if not settings.OLLAMA_BASE_URL:
        raise HTTPException(status_code=500, detail="OLLAMA_BASE_URL is not configured on the server")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for item in history:
            if isinstance(item, dict):
                role = item.get("role", "user")
                text = item.get("content") or item.get("text") or ""
                if text:
                    messages.append({"role": role, "content": str(text)})
            elif item:
                messages.append({"role": "user", "content": str(item)})
    messages.append({"role": "user", "content": user_content})

    body = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.2,
        },
    }
    url = OLLAMA_URL.format(base_url=settings.OLLAMA_BASE_URL.rstrip('/'))

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=timeout or OLLAMA_TIMEOUT_SECONDS, write=30, pool=10)) as client:
            resp = await client.post(url, json=body)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI service timed out. The model may be loading — please try again in a moment.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach AI service: {exc}")

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail=f"AI service returned an unreadable response (HTTP {resp.status_code})",
        )

    if resp.status_code != 200 or "error" in data:
        message = data.get("error") or f"AI service returned HTTP {resp.status_code}"
        raise HTTPException(status_code=502, detail=f"AI error: {message}")

    text = data.get("message", {}).get("content", "")
    if not text.strip():
        raise HTTPException(status_code=502, detail="AI service returned an empty response")
    return text


async def call_ollama_stream(system: str, user_content: str, max_tokens: int = 500, history=None, timeout: float = OLLAMA_TIMEOUT_SECONDS):
    """Stream a chat completion from Ollama token-by-token (NDJSON lines)."""
    if not settings.OLLAMA_BASE_URL:
        raise HTTPException(status_code=500, detail="OLLAMA_BASE_URL is not configured on the server")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for item in history:
            if isinstance(item, dict):
                role = item.get("role", "user")
                text = item.get("content") or item.get("text") or ""
                if text:
                    messages.append({"role": role, "content": str(text)})
            elif item:
                messages.append({"role": "user", "content": str(item)})
    messages.append({"role": "user", "content": user_content})

    body = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.2,
        },
    }
    url = OLLAMA_URL.format(base_url=settings.OLLAMA_BASE_URL.rstrip('/'))

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=timeout, write=30, pool=10)
        ) as client:
            async with client.stream("POST", url, json=body) as resp:
                if resp.status_code != 200:
                    raw = (await resp.aread()).decode("utf-8", "ignore")
                    raise HTTPException(status_code=502, detail=f"AI error: {raw[:200]}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except ValueError:
                        continue
                    if data.get("error"):
                        raise HTTPException(status_code=502, detail=f"AI error: {data['error']}")
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI service timed out. The model may be loading — please try again in a moment.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach AI service: {exc}")


async def call_claude(system: str, user_content: str, max_tokens: int = 1000, history=None) -> str:
    return await call_ai(system, user_content, max_tokens=max_tokens, history=history)


async def safe_ai_call(system: str, user_content: str, max_tokens: int = 1000, history=None,
                       timeout: float = None, raise_on_timeout: bool = False):
    """Wraps call_ai and returns None on failure instead of raising, so
    callers can degrade gracefully when a single AI call fails.
    If raise_on_timeout is set, 504 timeouts propagate so callers can retry."""
    try:
        return await call_ai(system, user_content, max_tokens=max_tokens, history=history, timeout=timeout)
    except HTTPException as exc:
        if raise_on_timeout and exc.status_code == 504:
            raise
        return None
    except Exception as exc:
        logger.warning("safe_ai_call failed: %s", exc)
        return None


def _balanced_json_end(s: str, start_char: str, end_char: str):
    """Index of the end_char that closes the first start_char, respecting
    JSON string literals. Returns -1 if unbalanced."""
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == start_char:
            depth += 1
        elif ch == end_char:
            depth -= 1
            if depth == 0:
                return i
    return -1


def extract_json(text: str):
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```json\s*", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"^```\s*", "", t).strip()
    t = re.sub(r"\s*```$", "", t).strip()
    starts = [(t.find(start), start, end) for start, end in (("{", "}"), ("[", "]")) if t.find(start) != -1]
    if not starts:
        return None
    s, start_char, end_char = min(starts, key=lambda x: x[0])
    e = _balanced_json_end(t, start_char, end_char)
    if e != -1:
        raw = t[s:e + 1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        try:
            cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
            return json.loads(cleaned)
        except Exception:
            pass
    logger.warning("Failed to extract JSON from AI response (len=%d)", len(text))
    return None


def regex_parse_resume(text: str):
    """Fast regex-based resume parser. No AI needed — works instantly."""
    if not text:
        return {}

    t = text.strip()
    result = {
        "name": "",
        "email": "",
        "phone": "",
        "currentCompany": "",
        "currentDesignation": "",
        "totalExperienceYears": 0,
        "relevantExperience": "",
        "education": "",
        "skills": [],
        "certifications": [],
        "projects": [],
        "location": "",
        "suggestedRole": "",
        "linkedin": "",
        "github": "",
    }

    # Email
    m = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', t)
    if m:
        result["email"] = m.group(0)

    # Phone (Indian or US formats)
    m = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', t)
    if m:
        result["phone"] = m.group(0).strip()

    # Location: explicit 'Location: X' or 'Based in X' first, then known cities.
    loc_m = re.search(r'(?:Location|Currently Based|Based at|Work Location|Address)\s*[:\-]\s*([^\n]{2,50})', t, re.IGNORECASE)
    if loc_m:
        result["location"] = loc_m.group(1).strip().rstrip(".")
    else:
        for city in _KNOWN_LOCATIONS:
            city_pat = r"\s+".join(re.escape(p) for p in city.split())
            m = re.search(rf"\b{city_pat}\b", t, re.IGNORECASE)
            if m:
                result["location"] = city.title()
                break

    # LinkedIn
    m = re.search(r'linkedin\.com/in/[\w-]+', t, re.IGNORECASE)
    if m:
        result["linkedin"] = "https://www." + m.group(0)

    # GitHub
    m = re.search(r'github\.com/[\w-]+', t, re.IGNORECASE)
    if m:
        result["github"] = "https://" + m.group(0)

    # Name: first non-empty line that's short and has no @ or digits
    for line in t.split("\n"):
        line = line.strip()
        if line and len(line) < 60 and "@" not in line and not re.search(r'\d{3}', line) and not re.search(r'(experience|education|skills|summary|profile|objective|address|phone|email)', line, re.IGNORECASE):
            result["name"] = line.split(",")[0].strip()
            break

    # Experience years (several common phrasings)
    exp_pats = [
        r'(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp|work)\b',
        r'(?:experience|exp|worked)\s*(?:of|for|:)?\s*(\d{1,2})\+?\s*(?:years?|yrs?)\b',
        r'(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:building|developing|working|designing|engineering|hands-on)\b',
        r'(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:in|of)\b',
    ]
    for ep in exp_pats:
        m = re.search(ep, t, re.IGNORECASE)
        if m:
            result["totalExperienceYears"] = int(m.group(1))
            break

    # Current company: look for "Company:" or last employer line
    m = re.search(r'(?:Company|Employer|Organization)\s*[:\-]\s*(.+)', t, re.IGNORECASE)
    if m:
        result["currentCompany"] = m.group(1).strip()[:80]
    else:
        # Try to find "at <Company>" or "<Company> — <Role>"
        m = re.search(r'(?:at|@\s*)([A-Z][A-Za-z &.]{2,40})', t)
        if m:
            result["currentCompany"] = m.group(1).strip()

    # Current designation / role
    m = re.search(r'(?:Designation|Position|Current Role|Job Title|Role)\s*[:\-]\s*([^\n]{2,60})', t, re.IGNORECASE)
    if m and not re.search(r'(experience|education)', m.group(1), re.IGNORECASE):
        result["currentDesignation"] = m.group(1).strip().rstrip('.')
    else:
        m = re.search(r'(?i)\b(Senior|Junior|Lead|Principal|Staff|Chief|Sr\.?|Jr\.?)?\s*(Software\s*(?:Engineer|Developer)|Full.?Stack\s*(?:Engineer|Developer)|Data\s*(?:Engineer|Scientist|Analyst)|ML\s*Engineer|DevOps\s*Engineer|Cloud\s*Engineer|Backend|Frontend|QA\s*Engineer|Project\s*Manager|Product\s*Manager|Designer|Manager)\b', t)
        if m:
            result["currentDesignation"] = m.group(0).strip()[:60]

    # Relevant experience (years) - e.g. "X years of relevant experience"
    m = re.search(r'(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:of\s+)?relevant\s+(?:experience|exp|work|industry)', t, re.IGNORECASE)
    if m:
        result["relevantExperience"] = m.group(1) + " years"
    elif not result["totalExperienceYears"]:
        result["relevantExperience"] = ""

    # Education
    edu_patterns = [
        r'((?:Bachelor|Master|B\.?S\.?|M\.?S\.?|B\.?Tech|M\.?Tech|B\.?E\.?|M\.?E\.?|MBA|Ph\.?D)[^,\n]{0,80})',
        r'((?:B\.?Sc|M\.?Sc|B\.?A|M\.?A|B\.?Com|M\.?Com)[^,\n]{0,60})',
    ]
    for pat in edu_patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            result["education"] = m.group(1).strip()[:100]
            break

    # Skills: look for skills section (own line) or inline "Skills: ..."
    skills_section = ""
    for marker in ["skills", "technical skills", "core competencies", "technologies", "tech stack"]:
        idx = re.search(rf'(?:^|\n)[\s]*{marker}[\s:]*\n', t, re.IGNORECASE)
        if idx:
            start = idx.end()
            # Take next 3-5 lines or until a blank line
            lines_after = t[start:start+500].split("\n")[:5]
            skills_section = " ".join(l.strip() for l in lines_after if l.strip())
            break
    if not skills_section:
        m = re.search(r'(?:^|\n)\s*skills?\s*[:\-]\s*([^\n]{3,300})', t, re.IGNORECASE)
        if m:
            skills_section = m.group(1).strip()
    if not skills_section:
        m = re.search(r'skills?\s*[:\-]\s*([^\n]{3,300})', t, re.IGNORECASE)
        if m:
            skills_section = m.group(1).strip()
    if skills_section:
        # Trim trailing sentences that are not part of the skill list
        # (e.g. "System Design. M.Tech ..." -> keep only "System Design").
        cut = re.search(r'\.\s*[A-Z]', skills_section)
        if cut:
            skills_section = skills_section[:cut.start()]
        # Also drop the resume tail if the list was followed by a new section.
        tail = re.split(r'\s+(?:education|experience|projects|summary|objective|profile)\s*[:\-]', skills_section, maxsplit=1, flags=re.IGNORECASE)
        skills_section = tail[0]
    if skills_section:
        # Split on commas, bullets, pipes, or newlines
        skills = re.split(r'[,|•\-\n]+', skills_section)
        result["skills"] = [s.strip() for s in skills if s.strip() and len(s.strip()) < 50][:20]
    else:
        # Fallback: look for common tech keywords
        common = ["Python", "Java", "JavaScript", "TypeScript", "React", "Angular", "Vue", "Node",
                   "AWS", "Azure", "GCP", "Docker", "Kubernetes", "SQL", "PostgreSQL", "MongoDB",
                   "Git", "REST", "API", "HTML", "CSS", "Spring", "Django", "Flask", "FastAPI",
                   "Machine Learning", "AI", "Deep Learning", "NLP", "TensorFlow", "PyTorch"]
        found = [kw for kw in common if re.search(rf'\b{re.escape(kw)}\b', t, re.IGNORECASE)]
        result["skills"] = found[:15]

    # Certifications
    cert_m = re.findall(r'(?:Certified?|Certification)[^\n]{5,80}', t, re.IGNORECASE)
    result["certifications"] = [c.strip()[:80] for c in cert_m][:10]

    return result


async def ai_parse_resume(resume_text: str):
    """Parse resume using fast regex. Always instant — no AI call needed for parsing."""
    return regex_parse_resume(resume_text)


def _job_field(job, name, default):
    if job is None:
        return default
    if isinstance(job, dict):
        return job.get(name, default)
    return getattr(job, name, default)


MATCH_WEIGHTS = {
    "mandatory_skills": 0.30,
    "preferred_skills": 0.05,
    "experience": 0.15,
    "role_fit": 0.15,
    "responsibilities": 0.10,
    "education": 0.10,
    "domain": 0.05,
    "location": 0.05,
    "certifications": 0.05,
}


def _jd_match_system(job, rag_context: str = ""):
    """System prompt for accurate, evidence-based Resume vs JD matching.

    The single AI metric produced here is the JD Match Score: how well the
    candidate's resume matches the selected job description. It is NOT a
    resume-quality / ATS score. Criteria and weights:

        Mandatory Skills 30% | Role Fit 15% | Experience 15% |
        JD Responsibilities 10% | Education 10% | Domain 5% |
        Location 5% | Certifications 5% | Preferred Skills 5%

    Every criterion carries a short ``evidence`` string quoting the exact
    JD requirement and the resume line/skill that satisfies (or fails) it, so
    the final score is fully explainable. When `rag_context` is provided
    (JD-scoped chunks retrieved from the vector store) it is appended as
    grounding context so long job descriptions are represented faithfully."""
    title = _job_field(job, "title", "")
    dept = _job_field(job, "dept", "")
    exp = _job_field(job, "exp", "")
    skills = _job_field(job, "skills", []) or []
    description = _job_field(job, "description", "") or ""
    location = _job_field(job, "location", "") or ""
    jd_parts = []
    if title:
        jd_parts.append(f"Job Title: {title}")
    if dept:
        jd_parts.append(f"Department: {dept}")
    if exp:
        jd_parts.append(f"Experience Required: {exp}")
    if location:
        jd_parts.append(f"Work Location: {location}")
    if skills:
        jd_parts.append(f"Required Skills: {', '.join(skills)}")
    if description:
        jd_parts.append(f"Description: {description}")
    jd = "\n".join(jd_parts) or "Job Title: Unknown"
    prompt = (
        "You are an Enterprise JD Match Engine and Senior Technical Recruiter.\n\n"
        "Your task is to compare the candidate resume ONLY against the provided Job Description.\n\n"
        "CRITICAL RULES:\n"
        "1. Do NOT give scores based on resume quality alone. This is a JD vs Resume Match, never an ATS/generic quality score.\n"
        "2. Every score must be derived from the Job Description requirements.\n"
        "3. Do NOT assume skills, roles, location or experience not explicitly mentioned in the resume.\n"
        "4. Missing mandatory skills must heavily reduce the score.\n"
        "5. If required experience is not met, Experience Match Score = 0.\n"
        "6. If experience is not mentioned in the resume, Experience Match Score = 0.\n"
        "7. If less than 50% of mandatory skills are matched, Overall Score cannot exceed 50.\n"
        "8. If less than 30% of mandatory skills are matched, Overall Score cannot exceed 35.\n"
        "9. Overall Score below 40 means the AI recommends reject pending HR review — never send an email.\n"
        "10. Do not inflate scores for education, formatting, or generic soft skills.\n\n"
        "STEP 1: Extract JD Requirements internally: Mandatory Skills, Preferred Skills, "
        "Required Experience, Required Education, Job Responsibilities, Job Location, "
        "Target Role title, Domain.\n\n"
        "STEP 2: Compare Resume Against JD, scoring each criterion 0-100 and writing a "
        "one-line evidence string that quotes the exact JD requirement and the matching "
        "resume proof (or states why no proof exists):\n"
        "Mandatory Skills (30%): score = (matched_mandatory_skills / total_mandatory_skills) x 100.\n"
        "Preferred Skills (5%): bonus, optional JD skills. No preferred list in JD = 70 (neutral).\n"
        "Role Fit (15%): does the candidate's current/past designation and experience match "
        "the target role? Exact seniority/domain overlap = 100; related = 50; unrelated = 0.\n"
        "Experience (15%): Meets or exceeds requirement = 100; Partially meets = 50; "
        "Below requirement = 0; Not mentioned = 0.\n"
        "JD Responsibilities (10%): Compare JD responsibilities with actual resume experience. "
        "Score only based on evidence.\n"
        "Education (10%): Exact match = 100; Related degree = 70; Not matching = 0.\n"
        "Domain (5%): Same industry/domain (fintech, healthcare, saas, e-commerce, etc.) = 100; "
        "JD has no domain emphasis = 70 (neutral); different domain = 0.\n"
        "Location (5%): Resume location matches JD location or 'Remote' = 100; not mentioned = 0.\n"
        "Certifications (5%): Relevant certifications only.\n\n"
        "STEP 3: Generate Final Result. Return ONLY valid JSON matching this exact schema "
        "(no extra keys, no markdown):\n"
        '{"overall_score":0,"hiring_probability":0,'
        '"recommendation":"Strong Hire | Hire | Consider | AI Recommended Reject",'
        '"mandatory_skills":[],"matched_skills":[],"missing_skills":[],'
        '"preferred_skills":[],"matched_preferred_skills":[],"missing_preferred_skills":[],'
        '"required_role":"","candidate_role":"","role_fit_score":0,"role_fit_evidence":"",'
        '"required_experience":"","candidate_experience":"","experience_match_score":0,'
        '"required_education":"","candidate_education":"","education_match_score":0,'
        '"domain_match_score":0,"domain_evidence":"",'
        '"required_location":"","candidate_location":"","location_match_score":0,'
        '"skills_match_score":0,"responsibility_match_score":0,"responsibility_evidence":"",'
        '"project_match_score":0,"certification_match_score":0,'
        '"criteria":[{"criterion":"Mandatory Skills","score":0,"evidence":""}],'
        '"strengths":[],"gaps":[],"rejection_reasons":[],"summary":""}\n\n"'
        "The criteria array must repeat every criterion above with its score and evidence.\n"
        "STRICT HIRING RULES:\n"
        "* Missing 3 or more mandatory skills -> Recommendation = AI Recommended Reject.\n"
        "* Experience below requirement -> Recommendation cannot be Strong Hire.\n"
        "* No relevant experience -> Hiring Probability <= 25.\n"
        "* Missing mandatory skill list must come ONLY from the JD.\n"
        "* Never suggest Docker, AWS, Kubernetes, CI/CD, etc. unless they actually appear in the JD.\n"
        "* Never generate generic missing skills.\n"
        "* Every missing skill must be traceable to the Job Description.\n\n"
        "JOB DESCRIPTION:\n"
        + jd
    )
    ctx = (rag_context or "").strip()
    if ctx:
        prompt += (
            "\n\nRELEVANT CONTEXT (JD excerpts retrieved via semantic search):\n"
            + ctx[:2400]
            + "\nUse this context to ground mandatory skills, responsibilities and requirements; "
              "it supplements but never overrides the JOB DESCRIPTION above."
        )
    return prompt


def _clamp_int(value, default=0):
    try:
        return max(0, min(100, int(round(float(value or default)))))
    except (TypeError, ValueError):
        return default


def _norm_list(value):
    if isinstance(value, list):
        return [str(x) for x in value if x]
    return []


def _criteria_evidence(data, label):
    """Pull the LLM-supplied evidence string for a criterion, if present."""
    for c in (data.get("criteria") if isinstance(data, dict) else None) or []:
        if isinstance(c, dict) and str(c.get("criterion", "")).strip().lower() == label.lower():
            return str(c.get("evidence") or "").strip()
    key = label.lower().replace(" ", "_")
    return str(data.get(f"{key}_evidence") or "").strip()


def _normalize_jd_match(data, job=None, resume_text=None):
    """Normalize JD match output into the product schema.

    Computes an explainable JD vs Resume Match Score from weighted criteria
    (mandatory skills, role fit, experience, JD responsibilities, education,
    domain, location, certifications, preferred skills). Every criterion gets a
    score, an evidence line, and the matched/missing detail, so HR can see
    exactly why the score is what it is. Returns the legacy keys used by the
    enrichment pipelines plus a ``match_breakdown`` document.
    """
    ref = _regex_detailed_match(resume_text, job) if resume_text else {}
    if not isinstance(ref, dict):
        ref = {}

    def _ref(key, default=None):
        v = ref.get(key)
        return default if v is None else v

    # Skill lists: deterministic (JD-derived), never generic.
    mandatory = _norm_list(_ref("mandatory_skills"))
    matched = _norm_list(_ref("matched_skills"))
    missing = _norm_list(_ref("missing_skills"))
    if not mandatory:
        mandatory = _norm_list(data.get("mandatory_skills"))
    if not matched:
        matched = _norm_list(data.get("matched_skills") or data.get("matchedSkills"))
    if not missing:
        missing = _norm_list(data.get("missing_skills") or data.get("missingSkills"))

    preferred = _norm_list(data.get("preferred_skills") or _ref("preferred_skills"))
    matched_pref = _norm_list(data.get("matched_preferred_skills") or _ref("matched_preferred_skills"))
    missing_pref = _norm_list(data.get("missing_preferred_skills") or _ref("missing_preferred_skills"))

    # Per-criterion scores: LLM value when present, else deterministic fallback.
    skills_score = _clamp_int(data.get("skills_match_score") if _has(data, "skills_match_score") else _ref("skills_match_score"))
    pref_score = _clamp_int(data.get("preferred_skills_match_score") if _has(data, "preferred_skills_match_score") else _ref("preferred_skills_match_score"), 70)
    exp_score = _clamp_int(data.get("experience_match_score") if _has(data, "experience_match_score") else _ref("experience_match_score"))
    role_score = _clamp_int(data.get("role_fit_score") if _has(data, "role_fit_score") else _ref("role_fit_score"))
    resp_score = _clamp_int(data.get("responsibility_match_score") if _has(data, "responsibility_match_score") else _ref("responsibility_match_score"))
    edu_score = _clamp_int(data.get("education_match_score") if _has(data, "education_match_score") else _ref("education_match_score"))
    domain_score = _clamp_int(data.get("domain_match_score") if _has(data, "domain_match_score") else _ref("domain_match_score"))
    loc_score = _clamp_int(data.get("location_match_score") if _has(data, "location_match_score") else _ref("location_match_score"))
    cert_score = _clamp_int(data.get("certification_match_score") if _has(data, "certification_match_score") else _ref("certification_match_score"))

    # Deterministic caps from the mandatory-skill ratio (JD match rules).
    if mandatory:
        mandatory_lower = [m.lower() for m in mandatory]
        ratio = len([s for s in matched if s.lower() in mandatory_lower]) / len(mandatory)
        if ratio < 0.30:
            skills_score = min(skills_score, 25)
        elif ratio < 0.50:
            skills_score = min(skills_score, 50)

    scores = {
        "mandatory_skills": skills_score,
        "preferred_skills": pref_score,
        "experience": exp_score,
        "role_fit": role_score,
        "responsibilities": resp_score,
        "education": edu_score,
        "domain": domain_score,
        "location": loc_score,
        "certifications": cert_score,
    }
    overall = round(sum(scores[k] * MATCH_WEIGHTS[k] for k in MATCH_WEIGHTS))
    if mandatory:
        mandatory_lower = [m.lower() for m in mandatory]
        ratio = len([s for s in matched if s.lower() in mandatory_lower]) / len(mandatory)
        if ratio < 0.30:
            overall = min(overall, 35)
        elif ratio < 0.50:
            overall = min(overall, 50)

    jd_match_score = overall

    required_experience = str(data.get("required_experience") or "").strip() or str(_ref("required_experience", "") or "").strip()
    candidate_experience = str(data.get("candidate_experience") or "").strip() or str(_ref("candidate_experience", "") or "").strip()
    required_education = str(data.get("required_education") or "").strip() or str(_ref("required_education", "") or "").strip()
    candidate_education = str(data.get("candidate_education") or "").strip() or str(_ref("candidate_education", "") or "").strip()
    required_location = str(data.get("required_location") or "").strip() or str(_ref("required_location", "") or "").strip()
    candidate_location = str(data.get("candidate_location") or "").strip() or str(_ref("candidate_location", "") or "").strip()
    required_role = str(data.get("required_role") or "").strip() or str(_ref("required_role", "") or "").strip()
    candidate_role = str(data.get("candidate_role") or "").strip() or str(_ref("candidate_role", "") or "").strip()

    strengths = _norm_list(data.get("strengths")) or _norm_list(_ref("strengths"))
    gaps = _norm_list(data.get("gaps") or data.get("weaknesses")) or _norm_list(_ref("gaps") or _ref("weaknesses"))

    rejection_reasons = _norm_list(data.get("rejection_reasons"))
    if not rejection_reasons:
        if len(missing) >= 3:
            rejection_reasons.append(f"Missing {len(missing)} mandatory skills from the job description")
        if required_experience and candidate_experience:
            try:
                req_years = int(re.search(r'(\d+)', required_experience).group(1))
                cand_years = int(re.search(r'(\d+)', candidate_experience).group(1))
                if cand_years < req_years:
                    rejection_reasons.append(f"Experience below requirement ({cand_years} < {req_years} years)")
            except (ValueError, AttributeError):
                pass
        if not candidate_experience:
            rejection_reasons.append("Experience level not mentioned in resume")
        if not rejection_reasons and jd_match_score < 40:
            rejection_reasons.append(f"JD vs Resume Match {jd_match_score}% is below the 40% threshold")

    recommendation = (
        "Strong Hire" if overall >= 80
        else "Hire" if overall >= 60
        else "Consider" if overall >= 40
        else "AI Recommended Reject"
    )
    # Strict hiring rules drive the AI *recommendation* only — HR always decides.
    if len(missing) >= 3:
        recommendation = "AI Recommended Reject"
    if not candidate_experience:
        recommendation = "AI Recommended Reject"

    summary = str(data.get("summary") or "").strip() or str(_ref("summary", "") or "").strip()
    if not summary:
        parts = list(rejection_reasons) or gaps
        if parts:
            summary = " ".join(parts)
        elif required_location and candidate_location and required_location.lower() not in ("remote", "") and \
                required_location.lower() != candidate_location.lower():
            summary = f"JD vs Resume Match: {jd_match_score}% — location mismatch ({candidate_location} vs {required_location})."
        else:
            summary = f"JD vs Resume Match: {jd_match_score}% match."

    # --- Explainable criteria breakdown -------------------------------------
    evidence = {
        "Mandatory Skills": _criteria_evidence(data, "Mandatory Skills"),
        "Preferred Skills": _criteria_evidence(data, "Preferred Skills"),
        "Role Fit": _criteria_evidence(data, "Role Fit") or str(_ref("role_fit_evidence", "") or ""),
        "Experience": _criteria_evidence(data, "Experience"),
        "JD Responsibilities": _criteria_evidence(data, "JD Responsibilities") or str(_ref("responsibility_evidence", "") or "") or str(_ref("responsibilities_evidence", "") or ""),
        "Education": _criteria_evidence(data, "Education"),
        "Domain": _criteria_evidence(data, "Domain") or str(_ref("domain_evidence", "") or ""),
        "Location": _criteria_evidence(data, "Location"),
        "Certifications": _criteria_evidence(data, "Certifications"),
    }
    criteria = [
        {"key": "mandatory_skills", "label": "Mandatory Skills", "score": scores["mandatory_skills"],
         "weight": MATCH_WEIGHTS["mandatory_skills"], "evidence": evidence["Mandatory Skills"],
         "matched": matched, "missing": missing},
        {"key": "preferred_skills", "label": "Preferred Skills", "score": scores["preferred_skills"],
         "weight": MATCH_WEIGHTS["preferred_skills"], "evidence": evidence["Preferred Skills"],
         "matched": matched_pref, "missing": missing_pref},
        {"key": "role_fit", "label": "Role Fit", "score": scores["role_fit"],
         "weight": MATCH_WEIGHTS["role_fit"], "evidence": evidence["Role Fit"],
         "required": required_role, "candidate": candidate_role},
        {"key": "experience", "label": "Experience", "score": scores["experience"],
         "weight": MATCH_WEIGHTS["experience"], "evidence": evidence["Experience"],
         "required": required_experience, "candidate": candidate_experience},
        {"key": "responsibilities", "label": "JD Responsibilities", "score": scores["responsibilities"],
         "weight": MATCH_WEIGHTS["responsibilities"], "evidence": evidence["JD Responsibilities"]},
        {"key": "education", "label": "Education", "score": scores["education"],
         "weight": MATCH_WEIGHTS["education"], "evidence": evidence["Education"],
         "required": required_education, "candidate": candidate_education},
        {"key": "domain", "label": "Domain", "score": scores["domain"],
         "weight": MATCH_WEIGHTS["domain"], "evidence": evidence["Domain"]},
        {"key": "location", "label": "Location", "score": scores["location"],
         "weight": MATCH_WEIGHTS["location"], "evidence": evidence["Location"],
         "required": required_location, "candidate": candidate_location},
        {"key": "certifications", "label": "Certifications", "score": scores["certifications"],
         "weight": MATCH_WEIGHTS["certifications"], "evidence": evidence["Certifications"],
         "matched": _norm_list(_ref("certificationMatch", {}).get("matched") or data.get("certificationMatch", {}).get("matched")),
         "missing": _norm_list(_ref("certificationMatch", {}).get("missing") or data.get("certificationMatch", {}).get("missing"))},
    ]
    match_breakdown = {
        "overall": jd_match_score,
        "criteria": criteria,
        "weights": MATCH_WEIGHTS,
        "requiredRole": required_role,
        "candidateRole": candidate_role,
        "requiredLocation": required_location,
        "candidateLocation": candidate_location,
        "scoreExplanation": (
            f"JD vs Resume Match is a weighted average of Mandatory Skills ({MATCH_WEIGHTS['mandatory_skills']*100:.0f}%), "
            f"Role Fit ({MATCH_WEIGHTS['role_fit']*100:.0f}%), Experience ({MATCH_WEIGHTS['experience']*100:.0f}%), "
            f"JD Responsibilities ({MATCH_WEIGHTS['responsibilities']*100:.0f}%), Education ({MATCH_WEIGHTS['education']*100:.0f}%), "
            f"Domain ({MATCH_WEIGHTS['domain']*100:.0f}%), Location ({MATCH_WEIGHTS['location']*100:.0f}%), "
            f"Certifications ({MATCH_WEIGHTS['certifications']*100:.0f}%) and Preferred Skills ({MATCH_WEIGHTS['preferred_skills']*100:.0f}%). "
            f"Scores under 40% produce an 'AI Recommended Reject' — a recommendation that only HR can confirm."
        ),
    }

    result = {
        # JD Match headline metric
        "jd_vs_resume_match": jd_match_score,
        "overallMatch": jd_match_score,
        "overall_score": jd_match_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "match_breakdown": match_breakdown,
        "criteria": criteria,
        "preferred_skills": preferred,
        "matched_preferred_skills": matched_pref,
        "missing_preferred_skills": missing_pref,
        "strengths": strengths,
        "gaps": gaps,
        "summary": summary,
        "recommendation": recommendation,
        "role_fit_score": role_score,
        "location_match_score": loc_score,
        "domain_match_score": domain_score,
        "responsibility_match_score": resp_score,
        "preferred_skills_match_score": pref_score,
        "required_role": required_role,
        "candidate_role": candidate_role,
        "required_location": required_location,
        "candidate_location": candidate_location,
        # Core comparison data (traceable, no scoring labels)
        "required_education": required_education,
        "candidate_education": candidate_education,
        "required_experience": required_experience,
        "candidate_experience": candidate_experience,
        "rejection_reasons": rejection_reasons,
    }
    if job is not None:
        req = _job_field(job, "exp", "N/A") or "N/A"
        result["skillsMatchDetail"] = {"score": skills_score, "matched": matched, "missing": missing}
        result["experienceMatchDetail"] = {"score": exp_score, "required": req, "candidate": candidate_experience}
        result["educationMatchDetail"] = {"score": edu_score, "required": req, "candidate": candidate_education}
        result["roleFitDetail"] = {"score": role_score, "required": required_role or _job_field(job, "title", ""), "candidate": candidate_role}
        result["locationDetail"] = {"score": loc_score, "required": required_location or _job_field(job, "location", ""), "candidate": candidate_location}
        result["domainMatchDetail"] = {"score": domain_score}
        result["certificationMatchDetail"] = {"score": cert_score, "matched": criteria[8]["matched"], "missing": criteria[8]["missing"]}
        result["responsibilitiesMatchDetail"] = {"score": resp_score}
    return result


def _has(data, key):
    return isinstance(data, dict) and key in data and data[key] is not None


async def ai_match_job(resume_text: str, job, rag_context: str = ""):
    """Accurate Resume vs JD scoring using the weighted criteria spec.

    Returns the JD-relevant schema (jd_vs_resume_match, matched/missing skills,
    strengths/gaps, summary) with no candidate-facing scoring labels.
    Falls back to regex scoring when the AI is unavailable. `rag_context`
    (optional) grounds the prompt with JD chunks retrieved from the vector
    store via rag_service.jd_context()."""
    raw = await safe_ai_call(_jd_match_system(job, rag_context), resume_text, max_tokens=1600)
    data = extract_json(raw)
    if data:
        return _normalize_jd_match(data, job, resume_text)
    return _normalize_jd_match(_regex_detailed_match(resume_text, job), job, resume_text)


def _regex_summary(resume_text: str):
    """Heuristic summary from resume text — no AI needed."""
    if not resume_text or len(resume_text.strip()) < 20:
        return None
    r = regex_parse_resume(resume_text)
    t = resume_text.strip().lower()

    years = r.get("totalExperienceYears", 0)
    if not years:
        m = re.search(r'(\d{1,2})\+?\s*(?:years?|yrs?)', t)
        if m:
            years = int(m.group(1))
    skills = r.get("skills", [])
    certs = r.get("certifications", [])
    edu = r.get("education", "")
    name = r.get("name", "the candidate")
    company = r.get("currentCompany", "")

    summary_parts = [f"{name} is a professional"]
    if company:
        summary_parts[0] += f" currently at {company}"
    if years:
        summary_parts[0] += f" with {years} years of experience"
    summary_parts[0] += "."
    if skills:
        summary_parts.append(f"Key technical skills include {', '.join(skills[:6])}.")
    if edu:
        summary_parts.append(f"Education: {edu}.")
    if certs:
        summary_parts.append(f"Holds certifications in {', '.join(certs[:3])}.")

    soft_skills = []
    for sk in ["leadership", "communication", "teamwork", "mentoring", "agile", "scrum", "project management"]:
        if sk in t:
            soft_skills.append(sk.title())
    if soft_skills:
        summary_parts.append(f"Soft skills: {', '.join(soft_skills)}.")

    domains = []
    for d in ["fintech", "healthcare", "e-commerce", "saas", "banking", "telecom", "gaming", "edtech", "logistics", "manufacturing"]:
        if d in t:
            domains.append(d.title())
    if domains:
        summary_parts.append(f"Domain expertise: {', '.join(domains)}.")

    rec_role = ""
    if any(kw in t for kw in ["machine learning", "deep learning", "nlp", "data scien"]):
        rec_role = "ML / Data Scientist"
    elif any(kw in t for kw in ["react", "angular", "vue", "frontend", "front-end"]):
        rec_role = "Frontend Engineer"
    elif any(kw in t for kw in ["backend", "api", "microservice", "spring", "django", "fastapi", "node"]):
        rec_role = "Backend Engineer"
    elif any(kw in t for kw in ["full stack", "fullstack", "mern", "mean"]):
        rec_role = "Full Stack Engineer"
    elif any(kw in t for kw in ["devops", "ci/cd", "docker", "kubernetes", "terraform"]):
        rec_role = "DevOps Engineer"
    elif any(kw in t for kw in ["cloud", "aws", "azure", "gcp"]):
        rec_role = "Cloud Engineer"
    elif any(kw in t for kw in ["product", "roadmap", "stakeholder"]):
        rec_role = "Product Manager"
    elif any(kw in t for kw in ["manager", "director", "head", "lead"]):
        rec_role = "Engineering Manager"
    else:
        rec_role = "Software Engineer"

    strength_count = len(skills) + (1 if years and years >= 3 else 0) + (1 if edu else 0) + len(certs)
    if strength_count >= 5:
        hire = "Strong Hire"
    elif strength_count >= 3:
        hire = "Hire"
    elif strength_count >= 1:
        hire = "Maybe"
    else:
        hire = "Maybe"

    strengths = []
    if skills:
        strengths.append(f"Strong technical skill set ({len(skills)} skills listed)")
    if years and years >= 3:
        strengths.append(f"{years} years of relevant experience")
    if edu:
        strengths.append(f"Relevant educational background")
    if certs:
        strengths.append(f"Professional certifications ({len(certs)})")
    if not strengths:
        strengths = ["Resume submitted for review"]

    weaknesses = []
    if not certs:
        weaknesses.append("No certifications listed")
    if len(skills) < 3:
        weaknesses.append("Limited skills listed in resume")
    if not years:
        weaknesses.append("Experience level not clearly stated")
    if len(weaknesses) < 2:
        weaknesses.append("Resume could benefit from more quantified achievements")

    return {
        "professionalSummary": " ".join(summary_parts),
        "yearsOfExperience": years or 0,
        "technicalSkills": skills,
        "softSkills": soft_skills,
        "domainExpertise": domains,
        "educationSummary": edu,
        "certifications": certs,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendedPosition": rec_role,
    }


async def ai_summary(resume_text: str):
    system = (
        "You are MuraAI's AI candidate-summary engine. Read the resume text carefully and produce "
        "a comprehensive professional candidate profile. Return ONLY valid JSON:\n"
        '{"professionalSummary":string,"yearsOfExperience":number,"technicalSkills":string[],'
        '"softSkills":string[],"domainExpertise":string[],"educationSummary":string,'
        '"certifications":string[],"strengths":string[],"weaknesses":string[],'
        '"recommendedPosition":string,"summary":string}\n'
        "- professionalSummary: 3-5 sentences profiling the candidate\n"
        "- yearsOfExperience: total years estimated from resume\n"
        "- technicalSkills: key technical skills extracted\n"
        "- softSkills: communication, leadership, teamwork, etc.\n"
        "- domainExpertise: industries/domains they have worked in\n"
        "- educationSummary: highest degree and institution\n"
        "- certifications: any professional certifications\n"
        "- strengths: top 3-5 strengths\n"
        "- weaknesses: 2-3 areas for improvement\n"
        "- recommendedPosition: best-fit role title\n"
        "- summary: qualitative description of candidate fit for role\n"
        "Never invent data not present in the resume. If a field can't be determined, use empty string/number/[]/null."
    )
    raw = await safe_ai_call(system, resume_text, max_tokens=1200)
    result = extract_json(raw)
    if result:
        return result
    return _regex_summary(resume_text)


async def ai_fraud_check(resume_text: str):
    system = (
        "You are the AI fraud-detection engine inside MuraAI Refer. Look for signs of exaggerated experience, "
        "inconsistent dates/timelines, generic AI-generated resume phrasing, or implausible claims. Return "
        'ONLY valid JSON:\n{"riskLevel":"low"|"medium"|"high","flags":string[],"aiGeneratedProbability":number}\n'
        "aiGeneratedProbability is 0-100. Be conservative — only flag real, specific concerns; an empty flags "
        "array with riskLevel \"low\" is a normal, expected result."
    )
    raw = await safe_ai_call(system, resume_text, max_tokens=400)
    return extract_json(raw)


async def ai_interview_prediction(resume_text: str, job):
    system = (
        "You are the AI interview-prediction engine inside MuraAI Refer. Estimate the candidate's likelihood "
        "of clearing interviews for the role below, based only on resume signal. Return ONLY valid JSON:\n"
        '{"chance":number,"reasons":string[]}\nchance is 0-100. reasons has 2-4 short bullet points.\n'
        f"JOB: {job.title} | Required skills: {', '.join(job.skills or [])} | Experience needed: {job.exp}"
    )
    raw = await safe_ai_call(system, resume_text, max_tokens=400)
    return extract_json(raw)


async def ai_auto_tags(resume_text: str):
    system = (
        'Extract the top 6-10 most relevant skill/technology tags from this resume text. Return ONLY valid '
        'JSON: {"tags":string[]}. Use short canonical names (e.g. "React", "AWS", "Python").'
    )
    raw = await safe_ai_call(system, resume_text, max_tokens=200)
    j = extract_json(raw)
    return j.get("tags", []) if j else []


async def ai_compare_candidates(ref_a, ref_b, job):
    resume_a = ref_a.resume_text or ""
    resume_b = ref_b.resume_text or ""
    if not resume_a.strip() and not resume_b.strip():
        return {
            "strongerCandidate": "A",
            "verdict": "Both candidates lack resume data for comparison.",
            "candidateAStrengths": [],
            "candidateBStrengths": [],
        }
    system = (
        "You are the AI candidate-comparison engine inside MuraAI Refer, comparing two referrals for the "
        'same role. Return ONLY valid JSON:\n{"strongerCandidate":"A"|"B","verdict":string,'
        '"candidateAStrengths":string[],"candidateBStrengths":string[]}\n'
        f"JOB: {job.title if job else 'the role'}, required skills: {', '.join(job.skills) if job else 'n/a'}."
    )
    user = (
        f"CANDIDATE A ({ref_a.candidate_name}): {resume_a[:3000]}\n\n"
        f"CANDIDATE B ({ref_b.candidate_name}): {resume_b[:3000]}"
    )
    raw = await safe_ai_call(system, user, max_tokens=600)
    result = extract_json(raw)
    if not result:
        return {
            "strongerCandidate": "A",
            "verdict": "AI comparison could not be completed. Both candidates are under review.",
            "candidateAStrengths": [f"{ref_a.candidate_name}: has submitted a referral"],
            "candidateBStrengths": [f"{ref_b.candidate_name}: has submitted a referral"],
        }
    return result


async def ai_generate_email(referral, job):
    system = (
        "Write a warm, professional referral introduction email an employee can send to their HR/recruiting "
        "team, introducing a candidate they're referring. Keep it under 130 words, plain text, no markdown, "
        'no subject line prefix like "Subject:" beyond a first line labeled Subject.'
    )
    user = (
        f"Candidate: {referral.candidate_name}, applying for {job.title if job else 'an open role'} at MuraAI. "
        f"Candidate background: {referral.resume_text[:2000] if referral.resume_text else 'N/A'}. "
        f"Referrer relationship to candidate: {referral.relationship_to_referrer or 'colleague'}."
    )
    raw = await safe_ai_call(system, user, max_tokens=350)
    return raw or f"Subject: Referral for {referral.candidate_name}\n\nHi Team,\n\nI'd like to refer {referral.candidate_name} for the {job.title if job else 'open'} role. They come with relevant experience and I believe they'd be a strong fit.\n\nPlease let me know if you need any additional details.\n\nBest regards"


async def ai_generate_jd(brief: str):
    system = (
        "You are the AI job-description generator inside MuraAI Refer's HR panel. Given a short brief from HR, "
        "write a complete, well-structured job description with sections: Role Summary, Responsibilities, "
        'Requirements, Nice to Have. Use plain text with clear line breaks and short bullet-style lines '
        'starting with "- ". No markdown headers (##), just capitalized section titles on their own line. '
        "Keep it concise and specific to the brief."
    )
    raw = await safe_ai_call(system, brief, max_tokens=700)
    return raw or f"Role Summary\n{brief}\n\nResponsibilities\n- To be discussed\n\nRequirements\n- Relevant experience required"


def _chat_system(context: str) -> str:
    return (
        "You are the MuraAI Refer AI Assistant, embedded in an employee referral platform. Answer the "
        "employee's question helpfully and briefly (2-5 sentences unless a list is clearer). Use the CONTEXT "
        "below (their real referral data, open jobs, and policy) to answer specifically — never invent data "
        "not present in context. If asked something unrelated to referrals/hiring/MuraAI, answer briefly then "
        f"gently steer back.\nCONTEXT:\n{context}"
    )


async def ai_chat(user_message: str, history: list, context: str, timeout: float = None):
    timeout = timeout or settings_ai_timeout()
    raw = await safe_ai_call(_chat_system(context), user_message, max_tokens=500, history=history,
                             timeout=timeout, raise_on_timeout=True)
    return raw or "I'm sorry, I couldn't process that right now. Please try again in a moment."


async def ai_chat_stream(user_message: str, history: list, context: str, timeout: float = None):
    """Streaming variant of ai_chat. Falls back to a single yield for
    non-Ollama providers (streaming unsupported there for now)."""
    timeout = timeout or settings_ai_timeout()
    ps = _get_provider_settings()
    if ps.get("provider") != "ollama":
        text = await ai_chat(user_message, history, context, timeout=timeout)
        yield text
        return
    async for chunk in call_ollama_stream(_chat_system(context), user_message, max_tokens=500,
                                          history=history, timeout=timeout):
        yield chunk


MATCH_STOP = {
    "and", "the", "for", "with", "have", "has", "had", "will", "should", "would",
    "must", "can", "able", "ability", "prior", "working", "work", "experience",
    "using", "knowledge", "required", "candidate", "candidates", "role", "skills",
    "skill", "nice", "good", "plus", "points", "preferred", "such", "etc", "strong",
    "excellent", "including", "related", "across", "within", "our", "you", "your",
    "shall", "may", "also", "from", "this", "that", "those", "these", "into", "upon",
    "over", "under", "about", "their", "her", "his", "them",
}

_KNOWN_LOCATIONS = {
    "bengaluru", "bangalore", "hyderabad", "chennai", "mumbai",
    "pune", "new delhi", "delhi", "gurgaon", "gurugram", "noida", "kolkata",
    "remote", "coimbatore", "thiruvananthapuram", "kochi", "ahmedabad",
    "jaipur", "chandigarh", "lucknow", "indore", "bhopal", "visakhapatnam",
    "new york", "san francisco", "san jose", "seattle", "austin", "chicago",
    "boston", "london", "berlin", "toronto", "singapore", "dubai",
}


def _role_fit_score(job_title: str, candidate_designation: str, resume_lower: str):
    """Deterministic role-fit score: does the resume's role match the JD title?"""
    title_tokens = {tk for tk in re.findall(r"[a-z0-9+#.]+", job_title.lower()) if tk not in MATCH_STOP and len(tk) > 2}
    if not title_tokens:
        return 70, "JD title too generic to score role fit."
    designation_tokens = {tk for tk in re.findall(r"[a-z0-9+#.]+", candidate_designation.lower())}
    overlap = title_tokens & designation_tokens
    text_hits = [tk for tk in title_tokens if re.search(rf"\b{re.escape(tk)}\b", resume_lower)]
    hit_ratio = len(text_hits) / len(title_tokens)

    if overlap and hit_ratio >= 0.4:
        return 100, (f"Target role tokens {', '.join(sorted(overlap))} appear in the candidate's designation.")
    if text_hits and hit_ratio >= 0.4:
        return 100, f"Target role terms ({', '.join(text_hits[:4])}) appear in the resume."
    if text_hits and hit_ratio >= 0.2:
        return 50, f"Partial role overlap — only {', '.join(text_hits[:3])} found in the resume."
    if candidate_designation:
        return 30, f"Candidate designation '{candidate_designation}' does not match target role '{job_title}'."
    return 0, "Candidate role/designation is not stated in the resume."


def _location_score(required_location: str, candidate_location: str, resume_lower: str):
    """Deterministic location match. Remote/no constraint is always a pass."""
    req = (required_location or "").strip().lower()
    if not req or req in ("remote", "anywhere", "any", "hybrid", "on-site"):
        return 100, "No fixed location constraint in the JD."
    cand = (candidate_location or "").strip().lower()
    if not cand:
        cand = next((loc for loc in _KNOWN_LOCATIONS if loc in resume_lower), "")
    if cand and (req in cand or cand in req):
        return 100, f"Candidate location '{cand}' matches the JD location '{req}'."
    if not cand and req:
        return 0, f"JD requires {req} but the candidate's location is not stated in the resume."
    return 0, f"Location mismatch — JD requires {req}, resume shows {cand or 'N/A'}."


def _regex_detailed_match(resume_text: str, job):
    """Regex-based detailed match — no AI needed.

    Deterministic JD vs Resume scoring over the same criteria as the LLM path
    (mandatory/preferred skills, experience, role fit, JD responsibilities,
    education, domain, location, certifications) with per-criterion evidence so
    the fallback score is just as explainable as the AI score."""
    if not resume_text or len(resume_text.strip()) < 20:
        job_skills = [str(s) for s in (_job_field(job, "skills", []) or [])]
        job_exp = _job_field(job, "exp", "N/A") or "N/A"
        job_location = _job_field(job, "location", "") or ""
        return {
            "overallMatch": 0,
            "overall_score": 0,
            "hiring_probability": 0,
            "mandatory_skills": list(job_skills),
            "required_role": _job_field(job, "title", "") or "",
            "candidate_role": "N/A",
            "required_location": job_location,
            "candidate_location": "N/A",
            "skillsMatch": {"score": 0, "matched": [], "missing": list(job_skills)},
            "skills_match_score": 0,
            "preferred_skills": [],
            "matched_preferred_skills": [],
            "missing_preferred_skills": [],
            "preferred_skills_match_score": 0,
            "role_fit_score": 0,
            "role_fit_evidence": "No resume text to compare against the target role.",
            "experienceMatch": {"score": 0, "required": job_exp, "candidate": "N/A"},
            "experience_match_score": 0,
            "required_experience": job_exp,
            "candidate_experience": "N/A",
            "educationMatch": {"score": 0, "required": "N/A", "candidate": "N/A"},
            "education_match_score": 0,
            "required_education": "N/A",
            "candidate_education": "N/A",
            "certificationMatch": {"score": 0, "matched": [], "missing": []},
            "certification_match_score": 0,
            "domainMatch": {"score": 0},
            "domain_match_score": 0,
            "domain_evidence": "No resume text to evaluate the domain.",
            "location_match_score": 0,
            "responsibilities_match_score": 0,
            "responsibility_match_score": 0,
            "responsibility_evidence": "No resume text to evaluate JD responsibilities.",
            "project_match_score": 0,
            "keywordMatch": {"score": 0, "matched": [], "missing": []},
            "strengths": [],
            "gaps": ["No resume text provided"],
            "weaknesses": ["No resume text provided"],
            "rejection_reasons": ["No resume text provided"],
            "matched_skills": [],
            "missing_skills": list(job_skills),
            "recommendation": "AI Recommended Reject",
            "summary": "Unable to analyze — no resume text available.",
            "detailedAnalysis": "Unable to analyze — no resume text available.",
            "hiring_recommendation": "Insufficient data to evaluate the candidate.",
        }

    r = regex_parse_resume(resume_text)
    t = resume_text.strip().lower()
    job_skills = [s.lower() for s in (_job_field(job, "skills", []) or [])]
    job_exp = _job_field(job, "exp", "N/A") or "N/A"
    job_title = _job_field(job, "title", "") or ""
    job_location = _job_field(job, "location", "") or ""
    job_description = _job_field(job, "description", "") or ""
    jd_text = " ".join([job_title, job_exp, job_location, " ".join(job_skills), job_description]).lower()

    # --- Mandatory skills match ---
    candidate_skills = [s.lower() for s in r.get("skills", [])]
    matched_skills = []
    missing_skills = []
    for js in job_skills:
        found = any(js in cs or cs in js for cs in candidate_skills)
        if found:
            matched_skills.append(js.title())
        else:
            missing_skills.append(js.title())
    skills_score = round(len(matched_skills) / max(len(job_skills), 1) * 100) if job_skills else 50
    skills_evidence = f"Resume lists {len(matched_skills)}/{len(job_skills)} mandatory skills: {', '.join(matched_skills[:4])}." if job_skills else "JD lists no mandatory skills."
    if missing_skills:
        skills_evidence += f" Missing: {', '.join(missing_skills[:4])}."

    # --- Preferred skills (JD 'nice to have' section) ---
    pref_section = ""
    for marker in ("nice to have", "nice-to-have", "good to have", "preferred", "plus"):
        idx = job_description.lower().find(marker)
        if idx != -1:
            pref_section = job_description[idx:idx + 280]
            break
    # Cut the section at the first sentence boundary / requirement clause so
    # only the actual 'nice to have' phrase is parsed as preferred skills.
    _low_pref = pref_section.lower()
    _bnds = []
    for _stop in ("\n", ". ", "required.", "required,", "years experience",
                  "experience required", "must have", "minimum experience"):
        _pos = _low_pref.find(_stop)
        if _pos != -1:
            _bnds.append(_pos)
    if _bnds:
        pref_section = pref_section[:min(_bnds)]
    preferred_skills = []
    if pref_section:
        for tk in re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{2,28}", pref_section):
            tk_clean = tk.strip(".-").lower()
            if tk_clean in MATCH_STOP or len(tk_clean) < 3:
                continue
            if tk_clean not in [p.lower() for p in preferred_skills]:
                preferred_skills.append(tk_clean.title())
        preferred_skills = preferred_skills[:8]
    matched_pref = [p for p in preferred_skills if p.lower() in t]
    missing_pref = [p for p in preferred_skills if p.lower() not in t]
    pref_score = round(len(matched_pref) / max(len(preferred_skills), 1) * 100) if preferred_skills else 70
    if matched_pref:
        pref_evidence = f"JD preferred skills present in resume: {', '.join(matched_pref[:4])}."
    elif preferred_skills:
        pref_evidence = f"JD lists preferred skills ({', '.join(preferred_skills[:5])}) but the resume does not show them."
    else:
        pref_evidence = "JD states no preferred skills — treated as neutral."

    # --- Experience match (JD match rules) ---
    candidate_exp = r.get("totalExperienceYears", 0)
    exp_match = re.search(r'(\d+)', job_exp or "")
    required_exp = int(exp_match.group(1)) if exp_match else 0
    if not candidate_exp:
        exp_score = 0  # not mentioned in resume
        exp_evidence = "Resume does not state total years of experience."
    elif required_exp > 0 and candidate_exp >= required_exp:
        exp_score = 100
        exp_evidence = f"Candidate experience ({candidate_exp} yrs) meets the {required_exp}+ yr requirement."
    elif required_exp > 0:
        exp_score = 0
        exp_evidence = f"Candidate experience ({candidate_exp} yrs) is below the {required_exp}+ yr requirement."
    else:
        exp_score = 100
        exp_evidence = f"Candidate declares {candidate_exp} years of experience; JD sets no numeric bar."

    # --- Role fit ---
    cand_designation = r.get("currentDesignation", "") or ""
    role_score, role_evidence = _role_fit_score(job_title, cand_designation, t)
    required_role = job_title
    candidate_role = cand_designation or "N/A"

    # --- Education match ---
    edu = r.get("education", "")
    edu_score = 50
    if edu:
        edu_score = 80
        if any(kw in edu.lower() for kw in ["b.tech", "bachelor", "master", "mba", "ph.d", "m.tech", "b.e", "m.e"]):
            edu_score = 100
    edu_evidence = f"Resume education: {edu or 'not stated'}. Required education from JD: {required_education_from_jd(job_description)}."
    required_education = required_education_from_jd(job_description)

    # --- Certification match ---
    certs = [c.lower() for c in r.get("certifications", [])]
    cert_matched = []
    cert_missing = []
    job_cert_keywords = ["aws", "azure", "gcp", "scrum", "pmp", "cissp", "ceh", "kubernetes", "docker"]
    for ck in job_cert_keywords:
        if any(ck in c for c in certs):
            cert_matched.append(ck.upper())
        else:
            cert_missing.append(ck.upper())
    cert_score = round(len(cert_matched) / max(len(job_cert_keywords), 1) * 100) if job_cert_keywords else 50
    cert_evidence = f"Resume lists certifications: {', '.join(certs[:3]) or 'none'}. Security/cloud certs checked: {', '.join(cert_matched) or 'none matched'}."

    # --- Domain match (JD-derived) ---
    domain_keywords = ["fintech", "banking", "payments", "healthcare", "health", "insurance",
                       "e-commerce", "retail", "saas", "cloud", "telecom", "gaming", "edtech",
                       "logistics", "manufacturing"]
    jd_domains = [d for d in domain_keywords if d in jd_text]
    res_domains = [d for d in jd_domains if d in t]
    if not jd_domains:
        domain_score = 70
        domain_evidence = "JD places no emphasis on a specific domain."
    elif res_domains:
        domain_score = 100 if len(res_domains) == len(jd_domains) else 60
        domain_evidence = f"Both JD and resume reference domain(s): {', '.join(res_domains)}."
    else:
        domain_score = 0
        domain_evidence = f"JD emphasises domain(s) {', '.join(jd_domains)} but the resume shows no domain overlap."

    # --- Location match ---
    cand_location = r.get("location", "") or ""
    loc_score, loc_evidence = _location_score(job_location, cand_location, t)
    required_location = job_location or ""
    candidate_location = cand_location or "N/A"

    # --- JD responsibilities match ---
    resp_section = ""
    for marker in ("responsibilities", "what you'll do", "what you will do", "duties", "accountabilities"):
        idx = job_description.lower().find(marker)
        if idx != -1:
            resp_section = job_description[idx:idx + 500]
            break
    resp_tokens = []
    if resp_section:
        seen = set()
        for tk in re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{3,28}", resp_section.lower()):
            tk_clean = tk.strip(".-")
            if tk_clean in MATCH_STOP or len(tk_clean) < 4 or tk_clean.isdigit() or tk_clean in seen:
                continue
            seen.add(tk_clean)
            resp_tokens.append(tk_clean)
        resp_tokens = resp_tokens[:14]
    resp_matched = [tk for tk in resp_tokens if re.search(rf"\b{re.escape(tk)}\b", t)]
    if resp_tokens:
        resp_score = round(len(resp_matched) / len(resp_tokens) * 100) if resp_tokens else 0
        resp_evidence = f"Resume covers {len(resp_matched)}/{len(resp_tokens)} JD responsibility terms: {', '.join(resp_matched[:4])}."
    else:
        resp_score = 0
        resp_evidence = "JD description lists no explicit responsibilities section."

    # --- Keyword match (legacy, informational) ---
    keyword_matched = []
    keyword_missing = []
    keyword_list = ["microservices", "rest api", "graphql", "ci/cd", "agile", "scrum",
                    "system design", "scalable", "distributed", "cloud", "serverless"]
    for kw in keyword_list:
        if kw in t:
            keyword_matched.append(kw.title())
        else:
            keyword_missing.append(kw.title())
    keyword_score = round(len(keyword_matched) / max(len(keyword_list), 1) * 100)

    # --- Overall weighted (JD match weights, shared with the LLM path) ---
    scores = {
        "mandatory_skills": skills_score,
        "preferred_skills": pref_score,
        "experience": exp_score,
        "role_fit": role_score,
        "responsibilities": resp_score,
        "education": edu_score,
        "domain": domain_score,
        "location": loc_score,
        "certifications": cert_score,
    }
    overall = round(sum(scores[k] * MATCH_WEIGHTS[k] for k in MATCH_WEIGHTS))
    if job_skills:
        mandatory_ratio = len(matched_skills) / max(len(job_skills), 1)
        if mandatory_ratio < 0.30:
            overall = min(overall, 35)
        elif mandatory_ratio < 0.50:
            overall = min(overall, 50)

    # --- Strengths / Weaknesses ---
    strengths = []
    if matched_skills:
        strengths.append(f"Strong skill alignment: {', '.join(matched_skills[:4])}")
    if candidate_exp and candidate_exp >= (required_exp or 3):
        strengths.append(f"Sufficient experience ({candidate_exp} years)")
    if role_score >= 80:
        strengths.append(f"Role fit: {candidate_role or 'matches the target role'}")
    if edu:
        strengths.append(f"Relevant education: {edu}")
    if cert_matched:
        strengths.append(f"Holds relevant certifications: {', '.join(cert_matched[:3])}")
    if matched_pref:
        strengths.append(f"Preferred skills matched: {', '.join(matched_pref[:3])}")
    if keyword_matched:
        strengths.append(f"Covers key JD keywords: {', '.join(keyword_matched[:3])}")
    if not strengths:
        strengths = ["Resume submitted for review"]

    weaknesses = []
    if missing_skills:
        weaknesses.append(f"Missing required skills: {', '.join(missing_skills[:3])}")
    if role_score < 40:
        weaknesses.append(f"Resume does not closely match the target role '{job_title or 'in the JD'}'")
    if not candidate_exp:
        weaknesses.append("Experience level not clearly stated")
    if candidate_exp and required_exp and candidate_exp < required_exp:
        weaknesses.append(f"Below required experience ({candidate_exp} < {required_exp} years)")
    if cert_missing:
        weaknesses.append("No matching certifications found")
    if resp_matched and len(resp_matched) < max(1, len(resp_tokens) // 2):
        weaknesses.append("Limited evidence of the JD's core responsibilities")
    if len(weaknesses) < 2:
        weaknesses.append("Resume could benefit from more quantified achievements")

    recommendation = "AI Recommended Reject"
    if overall >= 80:
        recommendation = "Strong Hire"
    elif overall >= 60:
        recommendation = "Hire"
    elif overall >= 40:
        recommendation = "Consider"

    rejection_reasons = []
    if len(missing_skills) >= 3:
        rejection_reasons.append(f"Missing {len(missing_skills)} mandatory skills from the job description")
    if required_exp and candidate_exp and candidate_exp < required_exp:
        rejection_reasons.append(f"Experience below requirement ({candidate_exp} < {required_exp} years)")
    if not candidate_exp:
        rejection_reasons.append("Experience level not mentioned in resume")
    if role_score < 40:
        rejection_reasons.append("Resume does not align with the target role")

    analysis_parts = []
    if matched_skills:
        analysis_parts.append(f"The candidate matches {len(matched_skills)}/{len(job_skills)} required skills")
    if candidate_exp:
        analysis_parts.append(f"with {candidate_exp} years of experience")
    if missing_skills:
        analysis_parts.append(f"but is missing {', '.join(missing_skills[:2])}")
    analysis_parts.append(f"Overall suitability: {recommendation} ({overall}% match).")

    return {
        "overallMatch": overall,
        "overall_score": overall,
        "hiring_probability": overall,
        "mandatory_skills": [s.title() for s in job_skills],
        "required_role": required_role,
        "candidate_role": candidate_role,
        "required_location": required_location,
        "candidate_location": candidate_location,
        "skillsMatch": {"score": skills_score, "matched": matched_skills, "missing": missing_skills},
        "skills_match_score": skills_score,
        "skills_evidence": skills_evidence,
        "preferred_skills": preferred_skills,
        "matched_preferred_skills": matched_pref,
        "missing_preferred_skills": missing_pref,
        "preferred_skills_match_score": pref_score,
        "preferred_skills_evidence": pref_evidence,
        "role_fit_score": role_score,
        "role_fit_evidence": role_evidence,
        "experienceMatch": {"score": exp_score, "required": job_exp, "candidate": f"{candidate_exp} years" if candidate_exp else "N/A"},
        "experience_match_score": exp_score,
        "experience_evidence": exp_evidence,
        "required_experience": job_exp,
        "candidate_experience": f"{candidate_exp} years" if candidate_exp else "N/A",
        "educationMatch": {"score": edu_score, "required": required_education or "N/A", "candidate": edu or "N/A"},
        "education_match_score": edu_score,
        "education_evidence": edu_evidence,
        "required_education": required_education or "N/A",
        "candidate_education": edu or "N/A",
        "certificationMatch": {"score": cert_score, "matched": cert_matched, "missing": cert_missing},
        "certification_match_score": cert_score,
        "certification_evidence": cert_evidence,
        "domainMatch": {"score": domain_score},
        "domain_match_score": domain_score,
        "domain_evidence": domain_evidence,
        "location_match_score": loc_score,
        "location_evidence": loc_evidence,
        "responsibilities_match_score": resp_score,
        "responsibility_match_score": resp_score,
        "responsibility_evidence": resp_evidence,
        "project_match_score": keyword_score,
        "keywordMatch": {"score": keyword_score, "matched": keyword_matched, "missing": keyword_missing},
        "strengths": strengths,
        "weaknesses": weaknesses,
        "gaps": weaknesses,
        "rejection_reasons": rejection_reasons,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "recommendation": recommendation,
        "summary": " ".join(analysis_parts),
        "hiring_recommendation": recommendation,
        "detailedAnalysis": " ".join(analysis_parts),
    }


def required_education_from_jd(job_description: str) -> str:
    """Best-effort extraction of the education requirement from a JD description."""
    low = (job_description or "").lower()
    for kw in ["b.tech", "bachelor", "master", "m.tech", "mba", "b.sc", "m.sc", "ph.d", "b.e.", "m.e.", "degree"]:
        idx = low.find(kw)
        if idx != -1:
            snippet = job_description[max(0, idx - 30): idx + 60].replace("\n", " ").strip()
            return snippet[:110] or kw.title()
    return ""


async def ai_detailed_match(resume_text: str, job):
    """Detailed Resume vs JD match using the weighted criteria spec. Returns the
    detailed schema plus legacy aliases. Falls back to regex scoring."""
    raw = await safe_ai_call(_jd_match_system(job), resume_text, max_tokens=1600)
    data = extract_json(raw)
    if data:
        return _normalize_jd_match(data, job, resume_text)
    return _normalize_jd_match(_regex_detailed_match(resume_text, job), job, resume_text)
