"""AI shortlisting rules.

Product decision (HR keeps control of the mid band so strong candidates who
just miss keywords are not lost, and HR always confirms any rejection):

    score 95-100 -> Auto Interview           -> move automatically to interview
    score 80-94  -> HR Review Required       -> HR manually evaluates
    score 40-79  -> Manual Evaluation        -> HR evaluates candidate on merit
    score <  40  -> AI Recommended Reject    -> marked 'Auto-Reject Recommended',
                                               pending HR review (NO rejection
                                               email is sent until HR confirms)

These constants drive the shortlist endpoint, referral decisioning during AI
enrichment, and the frontend recommendation badges so the rules live in one
place.

The status string used across the app for the < 40 band is
"Auto-Reject Recommended" (kept stable for UI/test compatibility), while the
verdict here is "ai_recommended_reject" so callers can distinguish the
AI-recommendation state from a confirmed rejection.
"""
from typing import Dict

AI_RECOMMENDED_REJECT = "Auto-Reject Recommended"
HR_REVIEW_PENDING = "HR_REVIEW_PENDING"

AUTO_INTERVIEW_MIN = 95
HR_REVIEW_MIN = 80
MANUAL_EVALUATION_MIN = 40

# Backward-compatible aliases
HIGHLY_RECOMMENDED_MIN = AUTO_INTERVIEW_MIN
SHORTLIST_RECOMMENDED_MIN = HR_REVIEW_MIN
SHORTLIST_HR_REVIEW_MIN = MANUAL_EVALUATION_MIN


def shortlist_for_score(score: float) -> Dict:
    """Map a 0-100 match score to a shortlisting decision."""
    score = max(0, min(100, float(score or 0)))
    if score >= AUTO_INTERVIEW_MIN:
        return {
            "score": score,
            "category": "Auto Interview",
            "action": "Move automatically to Interview Stage (95–100)",
            "verdict": "auto_interview",
            "autoInterview": True,
            "autoReject": False,
        }
    if score >= HR_REVIEW_MIN:
        return {
            "score": score,
            "category": "HR Review Required",
            "action": "Manual review by HR (80–94)",
            "verdict": "hr_review",
            "autoInterview": False,
            "autoReject": False,
        }
    if score >= MANUAL_EVALUATION_MIN:
        return {
            "score": score,
            "category": "Manual Evaluation",
            "action": "Manual evaluation by HR (40–79)",
            "verdict": "manual_evaluation",
            "autoInterview": False,
            "autoReject": False,
        }
    return {
        "score": score,
        "category": "AI Recommended Reject",
        "action": "AI recommends rejection — pending HR review (under 40)",
        "verdict": "ai_recommended_reject",
        "status": AI_RECOMMENDED_REJECT,
        "reviewStatus": HR_REVIEW_PENDING,
        "autoInterview": False,
        "autoReject": False,
    }


def rank_label_for_score(score: float) -> str:
    decision = shortlist_for_score(score)
    if decision["verdict"] == "auto_interview":
        return "Exceptional"
    if decision["verdict"] == "hr_review":
        return "Strong"
    if decision["verdict"] == "manual_evaluation":
        return "Medium"
    return "Low"
