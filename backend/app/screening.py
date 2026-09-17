"""Advanced AI screening heuristics for the candidate passport.

Pure-Python checks that run fast and need no LLM round-trip:
  1. Employment-gap detection   — derived from date ranges in the resume.
  2. Date-integrity / fake-experience checks — overlapping jobs, negative
     spans, more claimed years than the candidate's career span can allow.
  3. Duplicate detection        — same email / phone / name, or a near-duplicate
     resume already in the pipeline (Jaccard similarity on normalized text).

The AI assistant still adds a narrative (fake-experience risk summary) via the
deep-screen API endpoint, but all the *flags* come from these deterministic
heuristics so HR gets an honest, reproducible passport.
"""
import re
from datetime import datetime
from difflib import SequenceMatcher

from . import models

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# "Jan 2020 - Dec 2022" / "01/2020 – 12/2022" / "2020-2022" / "Jan 2020 to Present"
_RANGE_RE = re.compile(
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[\s/]+)?"
    r"(\d{4}|[01]?\d[/-]\d{4})"
    r"[\s\u2013\u2014-]*(?:to|till|–|—|–|\.\.|-)"
    r"[\s]*((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[\s/]+)?"
    r"((?:\d{4}|[01]?\d[/-]\d{4})|present|current|now|ongoing)?",
    re.I,
)


def _parse_point(value: str, month_prefix: str = ""):
    """Parse '2020' or '01/2020' or 'Jan 2020' -> (year, month). None if invalid."""
    if not value:
        return None
    v = value.strip().lower()
    if v in ("present", "current", "now", "ongoing"):
        return None
    m = re.search(r"(\d{4})", v)
    if not m:
        return None
    year = int(m.group(1))
    month = 12 if not month_prefix else None
    if month_prefix:
        mp = month_prefix.strip().rstrip(".").lower()
        month = _MONTHS.get(mp[:3], 1)
    else:
        mm = re.match(r"(\d{1,2})[/-](\d{4})", v)
        if mm:
            month = int(mm.group(1))
        else:
            month = 1
    if year < 1950 or year > 2100:
        return None
    return (year, min(month or 1, 12))


def extract_positions(resume_text: str) -> list:
    """Find experience date ranges in resume text. Returns list of
    {'start': (y,m)|None, 'end': (y,m)|None, 'raw': str} sorted by start."""
    positions = []
    for m in _RANGE_RE.finditer(resume_text or ""):
        start = _parse_point(m.group(2), m.group(1))
        end = _parse_point(m.group(4), m.group(3))
        raw = m.group(0).strip()
        if start or end:
            positions.append({"start": start, "end": end, "raw": raw[:80]})
    positions.sort(key=lambda p: p["start"] or (9999, 12))
    return positions


def _months_since(date_tuple, ref=None):
    ref = ref or (datetime.now().year, datetime.now().month)
    return (ref[0] - date_tuple[0]) * 12 + (ref[1] - date_tuple[1])


def detect_employment_gaps(positions: list, ref=None) -> list:
    """Find gaps > 3 months between consecutive (non-overlapping) roles."""
    gaps = []
    last_end = None
    for p in positions:
        if not p["start"]:
            continue
        if last_end is None:
            last_end = p["end"]
            continue
        if last_end and p["start"] > last_end:
            gap_months = _months_since(last_end, p["start"])
            if gap_months > 3:
                gaps.append({
                    "from": last_end, "to": p["start"],
                    "months": gap_months,
                    "note": f"{gap_months}-month gap between roles",
                })
        last_end = p["end"] or last_end
    return sorted(gaps, key=lambda g: -g["months"])


def detect_date_conflicts(positions: list) -> list:
    """Overlapping roles and negative spans (signs of fabricated experience)."""
    flags = []
    valid = [p for p in positions if p["start"] and p["end"]]
    for i, a in enumerate(valid):
        if a["end"] < a["start"]:
            flags.append({"type": "negative_span", "raw": a["raw"],
                          "note": "End date is before the start date — impossible timeline."})
            continue
        for b in valid[i + 1:]:
            if b["start"] < a["end"]:
                flags.append({"type": "overlap", "a": a["raw"], "b": b["raw"],
                              "note": "Two roles overlap — possible inflated timeline."})
    return flags


def credibility_check(positions: list, claimed_years: str = "", ref=None) -> list:
    """Cross-check the claimed experience against the timeline the resume shows."""
    flags = []
    if not positions:
        return flags

    starts = [p["start"] for p in positions if p["start"]]
    if not starts:
        return flags
    earliest = min(starts)
    career_months = _months_since(earliest, ref)
    career_years = career_months / 12

    if career_years < 0.5:
        return flags  # not enough timeline to judge

    claimed = None
    try:
        claimed = float(re.sub(r"[^\d.]+", "", claimed_years or ""))
    except Exception:
        claimed = None

    if claimed and claimed > career_years + 1:
        flags.append({
            "type": "exaggerated_experience",
            "claimed": claimed,
            "careerSpan": round(career_years, 1),
            "note": f"{claimed} years claimed but the earliest role is only ~{round(career_years, 1)} years back.",
        })

    # 5+ simultaneous jobs is a strong red flag for fabricated resumes
    timeline = {}
    for p in positions:
        if not p["start"]:
            continue
        s = p["start"]
        e = p["end"] or ref or (datetime.now().year, datetime.now().month)
        for y in range(s[0], e[0] + 1):
            timeline[y] = timeline.get(y, 0) + 1
    heavy = {y: c for y, c in timeline.items() if c >= 5}
    if heavy:
        flags.append({"type": "too_many_simultaneous_roles",
                      "years": {k: v for k, v in list(heavy.items())[:4]},
                      "note": "5+ concurrent roles in one year — extremely unusual for a genuine resume."})
    return flags


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())


def resume_similarity(a: str, b: str) -> float:
    ta, tb = _normalize(a), _normalize(b)
    if len(ta) < 40 or len(tb) < 40:
        return 0.0
    return SequenceMatcher(None, ta, tb).ratio()


def detect_duplicates(db, referral) -> dict:
    """Look for an existing active referral that matches email / phone / name,
    or whose resume text is near-identical (>= 0.92 similarity)."""
    matches = []
    others = db.query(models.Referral).filter(
        models.Referral.id != referral.id,
        models.Referral.is_deleted.is_(False),
    ).all()

    norm_email = (referral.email or "").strip().lower()
    norm_phone = re.sub(r"[^\d]", "", referral.phone or "")
    norm_name = (referral.candidate_name or "").strip().lower()

    for o in others:
        reasons = []
        if norm_email and o.email and norm_email == o.email.strip().lower():
            reasons.append("email")
        if norm_phone and o.phone and norm_phone == re.sub(r"[^\d]", "", o.phone):
            reasons.append("phone")
        if norm_name and o.candidate_name and norm_name == o.candidate_name.strip().lower():
            reasons.append("name")
        if not reasons and referral.resume_text and o.resume_text:
            sim = resume_similarity(referral.resume_text, o.resume_text)
            if sim >= 0.92:
                reasons.append(f"resume ({(sim * 100):.0f}% similar)")
        if reasons:
            matches.append({"candidateName": o.candidate_name, "status": o.status,
                            "reasons": reasons, "referralId": o.id})
    return {"duplicate": bool(matches), "matches": matches}


def find_duplicates(db, email="", phone="", name="", resume_text="") -> dict:
    """Duplicate pre-check for bulk import — plain values, no persisted referral."""
    matches = []
    others = db.query(models.Referral).filter(
        models.Referral.is_deleted.is_(False),
    ).all()

    norm_email = (email or "").strip().lower()
    norm_phone = re.sub(r"[^\d]", "", phone or "")
    norm_name = (name or "").strip().lower()

    for o in others:
        reasons = []
        if norm_email and o.email and norm_email == o.email.strip().lower():
            reasons.append("email")
        if norm_phone and o.phone and norm_phone == re.sub(r"[^\d]", "", o.phone):
            reasons.append("phone")
        if norm_name and o.candidate_name and norm_name == o.candidate_name.strip().lower():
            reasons.append("name")
        if not reasons and resume_text and o.resume_text:
            sim = resume_similarity(resume_text, o.resume_text)
            if sim >= 0.92:
                reasons.append(f"resume ({(sim * 100):.0f}% similar)")
        if reasons:
            matches.append({"candidateName": o.candidate_name, "status": o.status,
                            "reasons": reasons, "referralId": o.id})
    return {"duplicate": bool(matches), "matches": matches}


def deep_screen(db, referral) -> dict:
    """Assemble the full candidate passport for a referral."""
    positions = extract_positions(referral.resume_text or "")
    gaps = detect_employment_gaps(positions)
    conflicts = detect_date_conflicts(positions)
    credibility = credibility_check(positions, referral.total_experience)
    dup = detect_duplicates(db, referral)

    red_flags = []
    for c in conflicts:
        red_flags.append(c["note"])
    for cr in credibility:
        red_flags.append(cr["note"])
    for g in gaps:
        red_flags.append(g["note"])
    if dup["duplicate"]:
        red_flags.append(f"Likely duplicate of {dup['matches'][0]['candidateName']} ({', '.join(dup['matches'][0]['reasons'])}).")
    for f in (referral.fraud_flags or []):
        red_flags.append(f)

    # Risk score 0-100: weight each red flag, cap at 100.
    risk = min(100, len(red_flags) * 20 + (len(conflicts) + len(credibility)) * 15)
    if risk == 0 and (referral.match_percent or 0) < 40:
        risk = 20

    return {
        "riskScore": risk,
        "riskLevel": "High" if risk >= 60 else "Medium" if risk >= 30 else "Low",
        "duplicate": dup,
        "employmentGaps": [{"from": f"{g['from'][0]}-{g['from'][1]}", "to": f"{g['to'][0]}-{g['to'][1]}",
                            "months": g["months"], "note": g["note"]} for g in gaps[:5]],
        "dateConflicts": [{"type": c["type"], "note": c["note"], "raw": c.get("raw") or c.get("a")} for c in conflicts[:6]],
        "credibilityFlags": credibility[:6],
        "redFlags": list(dict.fromkeys(red_flags)),
        "positionsDetected": len(positions),
        "checkedAt": datetime.utcnow().isoformat(),
    }
