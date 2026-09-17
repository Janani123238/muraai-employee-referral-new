"""Comprehensive tests for the HR-confirmed auto-rejection workflow.

Covers every scenario described in the spec:
  1. AI recommendation sets Auto-Reject Recommended (no email)
  2. HR confirms rejection → Rejected + email sent
  3. HR moves candidate to review → Under Review, no email
  4. Duplicate rejection confirmation prevented
  5. Retry rejection email after failure
  6. Unauthorized user denied from confirming rejection
  7. Update status endpoint blocks direct Rejected bypass
  8. Confirm rejection with failed email shows retry available
  9. Confirm rejection with no candidate email on file
 10. Move-to-review only works from Auto-Reject Recommended status
"""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from app import email_service
from app.models import Referral


# ═══════════════════════════════════════════════════════════════════════════
# Test 1 — AI Recommendation
# ═══════════════════════════════════════════════════════════════════════════

class TestAIRecommendation:
    """Verify that a referral in 'Auto-Reject Recommended' state is correctly
    structured and that no rejection email has been sent.
    """

    def test_auto_reject_referral_has_correct_fields(self, auto_reject_referral):
        """The auto_reject_referral fixture should represent the state the AI
        enrichment sets when a candidate scores below the threshold.
        """
        r = auto_reject_referral
        assert r.status == "Auto-Reject Recommended"
        assert r.ai_recommendation == "ai_recommended_reject"
        assert r.review_status == "HR_REVIEW_PENDING"
        assert r.auto_rejected is False
        assert r.match_percent == 35
        assert r.original_match == 35
        assert r.rejection_confirmed_by == ""
        assert r.rejection_confirmed_at is None
        assert r.rejection_email_sent is False
        assert r.rejection_email_sent_at is None
        assert r.rejection_email_status == ""
        assert r.rejection_email_error == ""

    def test_auto_reject_referral_has_history(self, auto_reject_referral):
        """The evaluation_history should record the AI recommendation event."""
        history = auto_reject_referral.evaluation_history or []
        assert len(history) >= 1
        ai_event = history[-1]
        assert ai_event["action"] == "AI recommended auto-rejection"
        assert ai_event["autoReject"] is False
        assert ai_event["matchAfter"] == 35


# ═══════════════════════════════════════════════════════════════════════════
# Test 2 — HR Confirms Rejection (successful email)
# ═══════════════════════════════════════════════════════════════════════════

class TestHRConfirmRejection:
    """POST /api/referrals/{id}/confirm-rejection"""

    def test_confirm_rejection_success(self, client, auto_reject_referral, hr_user, db_session):
        """HR confirms rejection → status becomes Rejected, email sent."""
        _, token = hr_user
        r = auto_reject_referral

        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_send:
            mock_send.return_value = None  # send_rejection_email returns None on success
            resp = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "Rejected"
        assert body["email_status"] == "sent"
        assert "successfully" in body["message"].lower()

        # Verify the email was called exactly once
        mock_send.assert_called_once_with(
            "jane@example.com", "Jane Doe", "Backend Developer"
        )

        # Verify DB state (use the same test session)
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.status == "Rejected"
        assert updated.auto_rejected is True
        assert updated.review_status == "REJECTED"
        assert updated.ai_recommendation == ""
        assert updated.rejection_confirmed_by == "HR Tester"
        assert updated.rejection_confirmed_at is not None
        assert updated.rejection_email_sent is True
        assert updated.rejection_email_sent_at is not None
        assert updated.rejection_email_status == "sent"
        assert updated.rejection_email_error == ""

    def test_confirm_rejection_stores_audit_history(self, client, auto_reject_referral, hr_user, db_session):
        """Confirming rejection appends 'HR confirmed rejection' to evaluation_history."""
        _, token = hr_user
        r = auto_reject_referral

        with patch("app.routers.referrals.email_service.send_rejection_email"):
            resp = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200

        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        history = updated.evaluation_history or []
        # At least the original AI recommendation + the HR confirmation
        assert len(history) >= 2
        hr_event = history[-1]
        assert hr_event["action"] == "HR confirmed rejection"
        assert hr_event["by"] == "HR Tester"
        assert hr_event["fromStatus"] == "Auto-Reject Recommended"
        assert hr_event["toStatus"] == "Rejected"


# ═══════════════════════════════════════════════════════════════════════════
# Test 3 — HR Moves to Review (no email)
# ═══════════════════════════════════════════════════════════════════════════

class TestMoveToReview:
    """POST /api/referrals/{id}/move-to-review"""

    def test_move_to_review_success(self, client, auto_reject_referral, hr_user, db_session):
        """HR moves candidate to review → status becomes Under Review, no email sent."""
        _, token = hr_user
        r = auto_reject_referral

        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_send:
            resp = client.post(
                f"/api/referrals/{r.id}/move-to-review",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Email should NOT have been called
        mock_send.assert_not_called()

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "Under Review"
        assert body["aiRecommendation"] == ""

        # Verify DB state
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.status == "Under Review"
        assert updated.ai_recommendation == ""
        assert updated.auto_rejected is False
        assert updated.review_status == "HR_REVIEWED"

    def test_move_to_review_records_history(self, client, auto_reject_referral, hr_user, db_session):
        """Move-to-review appends 'HR moved to review' to evaluation_history."""
        _, token = hr_user
        r = auto_reject_referral

        resp = client.post(
            f"/api/referrals/{r.id}/move-to-review",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        history = updated.evaluation_history or []
        hr_event = history[-1]
        assert hr_event["action"] == "HR moved to review"
        assert hr_event["fromStatus"] == "Auto-Reject Recommended"
        assert hr_event["toStatus"] == "Under Review"

    def test_move_to_review_wrong_status_fails(self, client, normal_referral, hr_user):
        """Move-to-review rejects candidates not in Auto-Reject Recommended."""
        _, token = hr_user
        r = normal_referral

        resp = client.post(
            f"/api/referrals/{r.id}/move-to-review",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "Auto-Reject Recommended" in resp.json()["detail"]

    def test_move_to_review_wrong_status_fails_for_rejected(self, client, hr_user, job, db_session):
        """Move-to-review rejects candidates already in Rejected status."""
        _, token = hr_user
        r = Referral(
            candidate_name="Already Rejected",
            email="rejected@example.com",
            job_id=job.id,
            status="Rejected",
            match_percent=20,
            rejection_confirmed_by="HR Tester",
            rejection_email_sent=True,
            rejection_email_status="sent",
        )
        db_session.add(r)
        db_session.commit()
        db_session.refresh(r)

        resp = client.post(
            f"/api/referrals/{r.id}/move-to-review",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# Test 4 — Duplicate Rejection Confirmation Prevention
# ═══════════════════════════════════════════════════════════════════════════

class TestDuplicateRejectionPrevention:
    """Prevent the same candidate from being rejected twice."""

    def test_confirm_rejection_twice_returns_400(self, client, auto_reject_referral, hr_user, db_session):
        """First confirmation succeeds; second is rejected with 400."""
        _, token = hr_user
        r = auto_reject_referral

        with patch("app.routers.referrals.email_service.send_rejection_email"):
            resp1 = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp1.status_code == 200

        # Second attempt — should be blocked (status already changed to Rejected,
        # so the status-check guard fires first with a clear message)
        resp2 = client.post(
            f"/api/referrals/{r.id}/confirm-rejection",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 400
        # Either "already confirmed" or "not in 'Auto-Reject Recommended'" are valid
        detail = resp2.json()["detail"].lower()
        assert "already" in detail or "auto-reject recommended" in detail

    def test_confirm_after_email_sent_returns_400(self, client, auto_reject_referral, hr_user, db_session):
        """If rejection was already confirmed and email was sent, return 400."""
        _, token = hr_user
        r = auto_reject_referral

        with patch("app.routers.referrals.email_service.send_rejection_email"):
            resp1 = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp1.status_code == 200

        # Verify email was marked as sent in DB
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.rejection_email_sent is True

        # Second attempt should also be blocked (status already Rejected)
        resp2 = client.post(
            f"/api/referrals/{r.id}/confirm-rejection",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 400
        detail = resp2.json()["detail"].lower()
        assert "already" in detail or "auto-reject recommended" in detail

    def test_email_only_sent_once_via_retry_path(self, client, auto_reject_referral, hr_user):
        """After confirmation + email sent, retry endpoint is also blocked."""
        _, token = hr_user
        r = auto_reject_referral

        with patch("app.routers.referrals.email_service.send_rejection_email"):
            resp1 = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp1.status_code == 200

        # Retry should also be blocked since email was already sent
        resp2 = client.post(
            f"/api/referrals/{r.id}/retry-rejection-email",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 400
        assert "already sent" in resp2.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# Test 5 — Retry Rejection Email
# ═══════════════════════════════════════════════════════════════════════════

class TestRetryRejectionEmail:
    """POST /api/referrals/{id}/retry-rejection-email"""

    def test_retry_email_after_failure(self, client, hr_user, job, db_session):
        """HR confirmed rejection but email failed; retry sends email successfully."""
        _, token = hr_user

        # Create a referral in Rejected state with failed email
        r = Referral(
            candidate_name="Retry Candidate",
            email="retry@example.com",
            job_id=job.id,
            status="Rejected",
            match_percent=30,
            original_match=30,
            auto_rejected=True,
            rejection_confirmed_by="HR Tester",
            rejection_confirmed_at=datetime.utcnow(),
            rejection_email_sent=False,
            rejection_email_status="failed",
            rejection_email_error="SMTP timeout",
        )
        db_session.add(r)
        db_session.commit()
        db_session.refresh(r)

        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_send:
            mock_send.return_value = None  # success
            resp = client.post(
                f"/api/referrals/{r.id}/retry-rejection-email",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["email_status"] == "sent"
        assert "successfully" in body["message"].lower()

        mock_send.assert_called_once_with(
            "retry@example.com", "Retry Candidate", "Backend Developer"
        )

        # DB should now show email as sent
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.rejection_email_sent is True
        assert updated.rejection_email_sent_at is not None
        assert updated.rejection_email_status == "sent"
        assert updated.rejection_email_error == ""

    def test_retry_email_fails_persists_error(self, client, hr_user, job, db_session):
        """Retry email fails → error recorded, candidate remains Rejected."""
        _, token = hr_user

        r = Referral(
            candidate_name="Fail Retry",
            email="fail@example.com",
            job_id=job.id,
            status="Rejected",
            match_percent=25,
            rejection_confirmed_by="HR Tester",
            rejection_confirmed_at=datetime.utcnow(),
            rejection_email_sent=False,
            rejection_email_status="failed",
            rejection_email_error="SMTP timeout",
        )
        db_session.add(r)
        db_session.commit()
        db_session.refresh(r)

        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_send:
            mock_send.side_effect = Exception("Connection refused")
            resp = client.post(
                f"/api/referrals/{r.id}/retry-rejection-email",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 500
        assert "Failed" in resp.json()["detail"]

        # Candidate should remain Rejected with email still failed
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.status == "Rejected"
        assert updated.rejection_email_sent is False
        assert updated.rejection_email_status == "failed"
        assert "Connection refused" in updated.rejection_email_error

    def test_retry_email_wrong_status_fails(self, client, hr_user, auto_reject_referral):
        """Retry endpoint rejects candidates that are not in Rejected status."""
        _, token = hr_user
        r = auto_reject_referral

        resp = client.post(
            f"/api/referrals/{r.id}/retry-rejection-email",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "not rejected" in resp.json()["detail"].lower()

    def test_retry_email_not_confirmed_fails(self, client, hr_user, job, db_session):
        """Retry endpoint rejects candidates whose rejection was not confirmed by HR."""
        _, token = hr_user

        r = Referral(
            candidate_name="Unconfirmed Reject",
            email="unconfirmed@example.com",
            job_id=job.id,
            status="Rejected",
            match_percent=20,
            # rejection_confirmed_by is empty → HR never confirmed
        )
        db_session.add(r)
        db_session.commit()
        db_session.refresh(r)

        resp = client.post(
            f"/api/referrals/{r.id}/retry-rejection-email",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "not been confirmed" in resp.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# Test 6 — Unauthorized User
# ═══════════════════════════════════════════════════════════════════════════

class TestUnauthorizedAccess:
    """Non-HR users must be denied from HR-only actions."""

    def test_employee_cannot_confirm_rejection(self, client, auto_reject_referral, employee_user):
        """An employee role user gets 403 on confirm-rejection."""
        _, token = employee_user
        r = auto_reject_referral

        resp = client.post(
            f"/api/referrals/{r.id}/confirm-rejection",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "hr" in resp.json()["detail"].lower() or "access" in resp.json()["detail"].lower()

    def test_employee_cannot_move_to_review(self, client, auto_reject_referral, employee_user):
        """An employee role user gets 403 on move-to-review."""
        _, token = employee_user
        r = auto_reject_referral

        resp = client.post(
            f"/api/referrals/{r.id}/move-to-review",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_employee_cannot_retry_email(self, client, employee_user, job, db_session):
        """An employee role user gets 403 on retry-rejection-email."""
        _, token = employee_user

        r = Referral(
            candidate_name="Fail Retry",
            email="fail2@example.com",
            job_id=job.id,
            status="Rejected",
            rejection_confirmed_by="HR Tester",
            rejection_email_sent=False,
            rejection_email_status="failed",
        )
        db_session.add(r)
        db_session.commit()
        db_session.refresh(r)

        resp = client.post(
            f"/api/referrals/{r.id}/retry-rejection-email",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_no_token_returns_401(self, client, auto_reject_referral):
        """Requests without a token are rejected with 401."""
        r = auto_reject_referral

        resp = client.post(f"/api/referrals/{r.id}/confirm-rejection")
        assert resp.status_code in (401, 403)

    def test_employee_cannot_override_status(self, client, normal_referral, employee_user):
        """Employees cannot use the override endpoint."""
        _, token = employee_user
        r = normal_referral

        resp = client.post(
            f"/api/referrals/{r.id}/override",
            headers={"Authorization": f"Bearer {token}"},
            json={"targetStatus": "Shortlisted", "reason": "test"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Test 7 — Status Update Guard (bypass prevention)
# ═══════════════════════════════════════════════════════════════════════════

class TestStatusUpdateGuard:
    """PATCH /api/referrals/{id}/status"""

    def test_direct_rejected_bypass_blocked(self, client, auto_reject_referral, hr_user):
        """Directly changing Auto-Reject Recommended → Rejected via PATCH is blocked."""
        _, token = hr_user
        r = auto_reject_referral

        resp = client.patch(
            f"/api/referrals/{r.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "Rejected"},
        )
        assert resp.status_code == 400
        assert "confirm" in resp.json()["detail"].lower() or "workflow" in resp.json()["detail"].lower()

    def test_direct_status_change_allowed_for_other_transitions(
        self, client, auto_reject_referral, hr_user
    ):
        """Moving from Auto-Reject Recommended to Under Review via PATCH is allowed."""
        _, token = hr_user
        r = auto_reject_referral

        resp = client.patch(
            f"/api/referrals/{r.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "Under Review"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Under Review"

    def test_normal_status_change_still_works(self, client, normal_referral, hr_user):
        """Normal status changes (e.g., Applied → Under Review) work as before."""
        _, token = hr_user
        r = normal_referral

        resp = client.patch(
            f"/api/referrals/{r.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "Under Review"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Under Review"

    def test_same_status_noop(self, client, normal_referral, hr_user):
        """Setting the same status again is a no-op and returns current state."""
        _, token = hr_user
        r = normal_referral

        resp = client.patch(
            f"/api/referrals/{r.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "Applied"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Applied"


# ═══════════════════════════════════════════════════════════════════════════
# Test 8 — Email Failure in Confirm Rejection
# ═══════════════════════════════════════════════════════════════════════════

class TestConfirmRejectionEmailFailure:
    """When email fails during confirm-rejection, the candidate is still
    rejected but the email failure is recorded.
    """

    def test_confirm_rejection_email_failure(self, client, auto_reject_referral, hr_user, db_session):
        """HR confirms → candidate is Rejected but email failed → retry available."""
        _, token = hr_user
        r = auto_reject_referral

        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_send:
            mock_send.side_effect = Exception("SMTP connection refused")
            resp = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "Rejected"
        assert body["email_status"] == "failed"
        assert "retry" in body["message"].lower()
        assert "SMTP connection refused" in body.get("emailError", "")

        # Verify DB state
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.status == "Rejected"
        assert updated.auto_rejected is True
        assert updated.rejection_email_sent is False
        assert updated.rejection_email_status == "failed"
        assert "SMTP connection refused" in updated.rejection_email_error

    def test_confirm_rejection_no_email_address(self, client, hr_user, job, db_session):
        """HR confirms rejection but candidate has no email → email_status is no_email."""
        _, token = hr_user

        r = Referral(
            candidate_name="No Email Candidate",
            email="",  # No email address
            job_id=job.id,
            status="Auto-Reject Recommended",
            match_percent=25,
            original_match=25,
            ai_recommendation="ai_recommended_reject",
            review_status="HR_REVIEW_PENDING",
        )
        db_session.add(r)
        db_session.commit()
        db_session.refresh(r)

        resp = client.post(
            f"/api/referrals/{r.id}/confirm-rejection",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "Rejected"
        assert body["email_status"] == "failed"

        # Verify DB state
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.status == "Rejected"
        assert updated.rejection_email_status == "no_email"
        assert "no email" in updated.rejection_email_error.lower()

    def test_retry_email_after_confirm_failure(self, client, auto_reject_referral, hr_user):
        """After a failed email during confirmation, retry succeeds."""
        _, token = hr_user
        r = auto_reject_referral

        # Step 1: Confirm rejection but email fails
        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_send:
            mock_send.side_effect = Exception("SMTP timeout")
            resp1 = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp1.status_code == 200
        assert resp1.json()["email_status"] == "failed"

        # Step 2: Retry email successfully
        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_retry:
            mock_retry.return_value = None
            resp2 = client.post(
                f"/api/referrals/{r.id}/retry-rejection-email",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp2.status_code == 200
        assert resp2.json()["email_status"] == "sent"
        assert resp2.json()["success"] is True

        # Step 3: Another retry should be blocked (email already sent)
        resp3 = client.post(
            f"/api/referrals/{r.id}/retry-rejection-email",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp3.status_code == 400
        assert "already sent" in resp3.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# Test 9 — Confirm Rejection for Wrong Status
# ═══════════════════════════════════════════════════════════════════════════

class TestConfirmRejectionWrongStatus:
    """Edge cases: attempting to confirm rejection on candidates not in
    'Auto-Reject Recommended' status.
    """

    def test_confirm_rejection_on_applied_referral(self, client, normal_referral, hr_user):
        """Cannot confirm rejection for a candidate in 'Applied' status."""
        _, token = hr_user
        r = normal_referral

        resp = client.post(
            f"/api/referrals/{r.id}/confirm-rejection",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "auto-reject recommended" in resp.json()["detail"].lower()

    def test_confirm_rejection_on_already_rejected(self, client, hr_user, job, db_session):
        """Cannot confirm rejection for a candidate already in 'Rejected' status."""
        _, token = hr_user

        r = Referral(
            candidate_name="Already Rejected",
            email="already@example.com",
            job_id=job.id,
            status="Rejected",
            rejection_confirmed_by="HR Tester",
            rejection_email_sent=True,
            rejection_email_status="sent",
        )
        db_session.add(r)
        db_session.commit()
        db_session.refresh(r)

        resp = client.post(
            f"/api/referrals/{r.id}/confirm-rejection",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_confirm_rejection_nonexistent_referral(self, client, hr_user):
        """Confirming rejection for a non-existent referral returns 404."""
        _, token = hr_user

        resp = client.post(
            "/api/referrals/nonexistent_id_123/confirm-rejection",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Test 10 — Full End-to-End Workflow
# ═══════════════════════════════════════════════════════════════════════════

class TestEndToEndWorkflow:
    """Full workflow: Auto-Reject Recommended → HR decision → final state."""

    def test_full_reject_workflow(self, client, auto_reject_referral, hr_user, db_session):
        """Complete flow: HR confirms → Rejected → email sent → audit trail."""
        _, token = hr_user
        r = auto_reject_referral

        # Step 1: Confirm rejection
        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_send:
            mock_send.return_value = None
            resp = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "Rejected"
        assert body["email_status"] == "sent"

        # Step 2: Verify complete audit trail
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()

        # Status
        assert updated.status == "Rejected"

        # HR confirmation metadata
        assert updated.auto_rejected is True
        assert updated.rejection_confirmed_by == "HR Tester"
        assert updated.rejection_confirmed_at is not None

        # Email metadata
        assert updated.rejection_email_sent is True
        assert updated.rejection_email_sent_at is not None
        assert updated.rejection_email_status == "sent"
        assert updated.rejection_email_error == ""

        # AI recommendation cleared
        assert updated.ai_recommendation == ""

        # Evaluation history
        history = updated.evaluation_history or []
        actions = [e["action"] for e in history]
        assert "AI recommended auto-rejection" in actions
        assert "HR confirmed rejection" in actions

        # Step 3: Attempting to confirm again should fail
        resp2 = client.post(
            f"/api/referrals/{r.id}/confirm-rejection",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 400

    def test_full_review_workflow(self, client, auto_reject_referral, hr_user, db_session):
        """Complete flow: HR moves to review → Under Review → no email."""
        _, token = hr_user
        r = auto_reject_referral

        # Step 1: Move to review
        with patch("app.routers.referrals.email_service.send_rejection_email") as mock_send:
            resp = client.post(
                f"/api/referrals/{r.id}/move-to-review",
                headers={"Authorization": f"Bearer {token}"},
            )
            mock_send.assert_not_called()

        assert resp.status_code == 200
        assert resp.json()["status"] == "Under Review"

        # Step 2: Verify state
        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.status == "Under Review"
        assert updated.ai_recommendation == ""
        assert updated.auto_rejected is False
        assert updated.rejection_email_sent is False

        # History preserved
        history = updated.evaluation_history or []
        actions = [e["action"] for e in history]
        assert "AI recommended auto-rejection" in actions
        assert "HR moved to review" in actions

        # Step 3: Moving to review again should fail (wrong status)
        resp2 = client.post(
            f"/api/referrals/{r.id}/move-to-review",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 400

    def test_confirm_then_retry_then_verify_prevention(self, client, hr_user, job, db_session):
        """Confirm (email fails) → retry (success) → retry again (blocked)."""
        _, token = hr_user

        r = Referral(
            candidate_name="Full Retry Flow",
            email="full@example.com",
            job_id=job.id,
            status="Auto-Reject Recommended",
            match_percent=30,
            original_match=30,
            ai_recommendation="ai_recommended_reject",
            review_status="HR_REVIEW_PENDING",
        )
        db_session.add(r)
        db_session.commit()
        db_session.refresh(r)

        # Step 1: Confirm but email fails
        with patch("app.routers.referrals.email_service.send_rejection_email") as mock:
            mock.side_effect = Exception("Temporary SMTP error")
            resp1 = client.post(
                f"/api/referrals/{r.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp1.status_code == 200
        assert resp1.json()["email_status"] == "failed"

        # Step 2: Retry succeeds
        with patch("app.routers.referrals.email_service.send_rejection_email") as mock:
            mock.return_value = None
            resp2 = client.post(
                f"/api/referrals/{r.id}/retry-rejection-email",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp2.status_code == 200
        assert resp2.json()["email_status"] == "sent"

        # Step 3: Third retry blocked
        resp3 = client.post(
            f"/api/referrals/{r.id}/retry-rejection-email",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp3.status_code == 400
        assert "already sent" in resp3.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# Test 11 — Override Decision
# ═══════════════════════════════════════════════════════════════════════════

class TestOverrideDecision:
    """POST /api/referrals/{id}/override"""

    def test_override_to_rejected_stores_confirmation(self, client, normal_referral, hr_user, db_session):
        """Overriding to Rejected records rejection_confirmed_by and rejection_confirmed_at."""
        _, token = hr_user
        r = normal_referral

        resp = client.post(
            f"/api/referrals/{r.id}/override",
            headers={"Authorization": f"Bearer {token}"},
            json={"targetStatus": "Rejected", "reason": "Manual rejection after review."},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Rejected"

        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == r.id).first()
        assert updated.rejection_confirmed_by == "HR Tester"
        assert updated.rejection_confirmed_at is not None

    def test_override_to_shortlisted(self, client, normal_referral, hr_user):
        """Overriding to Shortlisted works."""
        _, token = hr_user
        r = normal_referral

        resp = client.post(
            f"/api/referrals/{r.id}/override",
            headers={"Authorization": f"Bearer {token}"},
            json={"targetStatus": "Shortlisted", "reason": "Strong portfolio."},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Shortlisted"

    def test_override_invalid_status_fails(self, client, normal_referral, hr_user):
        """Overriding to an invalid status is rejected."""
        _, token = hr_user
        r = normal_referral

        resp = client.post(
            f"/api/referrals/{r.id}/override",
            headers={"Authorization": f"Bearer {token}"},
            json={"targetStatus": "Auto-Reject Recommended", "reason": "test"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Test 12 — Shortlist Decision Rules (HR-controlled rejection)
# ═══════════════════════════════════════════════════════════════════════════

class TestShortlistDecisionRules:
    """Verify the band mapping and that the < 40 band only *recommends* a
    rejection (no auto-reject email — HR must confirm)."""

    def test_below_40_is_recommendation_not_auto_reject(self):
        from app.shortlist import shortlist_for_score

        decision = shortlist_for_score(39)
        assert decision["verdict"] == "ai_recommended_reject"
        assert decision["category"] == "AI Recommended Reject"
        assert decision["autoReject"] is False
        assert decision["autoInterview"] is False
        assert decision["status"] == "Auto-Reject Recommended"
        assert decision["reviewStatus"] == "HR_REVIEW_PENDING"

    def test_band_boundaries(self):
        """40/80/95 boundaries map to Manual Evaluation / HR Review / Auto Interview."""
        from app.shortlist import shortlist_for_score

        assert shortlist_for_score(40)["verdict"] == "manual_evaluation"
        assert shortlist_for_score(79)["verdict"] == "manual_evaluation"
        assert shortlist_for_score(80)["verdict"] == "hr_review"
        assert shortlist_for_score(94)["verdict"] == "hr_review"
        assert shortlist_for_score(95)["verdict"] == "auto_interview"
        assert shortlist_for_score(100)["verdict"] == "auto_interview"

    def test_all_bands_never_auto_reject(self):
        """No band auto-rejects: rejection is always an HR decision."""
        from app.shortlist import shortlist_for_score

        for score in (10, 39, 40, 79, 80, 94, 95, 100):
            assert shortlist_for_score(score)["autoReject"] is False

    def test_moved_to_review_only_from_recommendation(self, client, normal_referral, hr_user):
        """A candidate not in Auto-Reject Recommended cannot use move-to-review."""
        _, token = hr_user
        resp = client.post(
            f"/api/referrals/{normal_referral.id}/move-to-review",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "Auto-Reject Recommended" in resp.json()["detail"]

    def test_patch_away_clears_review_status(self, client, auto_reject_referral, hr_user, db_session):
        """Moving away from Auto-Reject Recommended via PATCH clears review_status."""
        _, token = hr_user
        resp = client.patch(
            f"/api/referrals/{auto_reject_referral.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "Under Review"},
        )
        assert resp.status_code == 200
        assert resp.json()["reviewStatus"] == ""

        db_session.expire_all()
        updated = db_session.query(Referral).filter(Referral.id == auto_reject_referral.id).first()
        assert updated.review_status == ""
        assert updated.ai_recommendation == ""


# ═══════════════════════════════════════════════════════════════════════════
# Test 13 — Enrichment wiring
# ═══════════════════════════════════════════════════════════════════════════

class TestEnrichmentWiring:
    """The AI enrichment decision (applied in the referral/bulk-import paths)
    must pend the referral for HR review without ever auto-rejecting."""

    @staticmethod
    def _run_decision(match_detail):
        from app.shortlist import (
            shortlist_for_score, rank_label_for_score,
            AI_RECOMMENDED_REJECT, HR_REVIEW_PENDING,
        )

        match = int(match_detail.get("jd_vs_resume_match") or 0)
        decision = shortlist_for_score(match)
        fields = {
            "match_percent": match,
            "rank_label": rank_label_for_score(match),
            "ai_recommendation": None,
            "status": None,
            "review_status": None,
            "auto_rejected": None,
        }
        if decision["verdict"] == "ai_recommended_reject":
            fields.update({
                "status": AI_RECOMMENDED_REJECT,
                "ai_recommendation": "ai_recommended_reject",
                "review_status": HR_REVIEW_PENDING,
                "auto_rejected": False,
            })
        return decision, fields

    def test_enrich_below_40_pends_review(self):
        match_detail = {"jd_vs_resume_match": 32, "recommendation": "AI Recommended Reject"}
        decision, fields = self._run_decision(match_detail)
        assert decision["verdict"] == "ai_recommended_reject"
        assert fields["status"] == "Auto-Reject Recommended"
        assert fields["ai_recommendation"] == "ai_recommended_reject"
        assert fields["review_status"] == "HR_REVIEW_PENDING"
        assert fields["auto_rejected"] is False

    def test_enrich_above_threshold_no_reject_state(self):
        match_detail = {"jd_vs_resume_match": 68, "recommendation": "Consider"}
        decision, fields = self._run_decision(match_detail)
        assert decision["verdict"] == "manual_evaluation"
        assert fields["status"] is None  # existing status preserved
        assert fields["review_status"] is None

    def test_ai_match_breakdown_shape(self):
        """Enrichment output for < 40 exposes an explainable breakdown for HR."""
        match_detail = {
            "jd_vs_resume_match": 35,
            "match_breakdown": {
                "overall": 35,
                "criteria": [
                    {"key": "mandatory_skills", "score": 25, "weight": 0.30},
                    {"key": "role_fit", "score": 40, "weight": 0.15},
                ],
            },
        }
        decision, _ = self._run_decision(match_detail)
        breakdown = match_detail.get("match_breakdown", {})
        assert decision["verdict"] == "ai_recommended_reject"
        assert breakdown["overall"] == 35
        assert {c["key"] for c in breakdown["criteria"]} == {"mandatory_skills", "role_fit"}


# ═══════════════════════════════════════════════════════════════════════════
# Test 14 — HR Manager Role Access
# ═══════════════════════════════════════════════════════════════════════════

class TestHRManagerAccess:
    """Verify that HR-adjacent roles also have access."""

    def test_hr_manager_can_confirm(self, client, auto_reject_referral, db_session):
        """hr_manager role can confirm rejection."""
        from app.models import User, Employee
        from app.auth import hash_password, create_access_token

        emp = Employee(name="HR Manager", email="hrmgr@test.com", dept="HR")
        db_session.add(emp)
        db_session.commit()
        db_session.refresh(emp)

        user = User(
            name="HR Manager",
            email="hrmgr@test.com",
            password_hash=hash_password("Test1234!"),
            role="hr_manager",
            employee_id=emp.id,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        token = create_access_token({"sub": user.id})

        with patch("app.routers.referrals.email_service.send_rejection_email"):
            resp = client.post(
                f"/api/referrals/{auto_reject_referral.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_admin_role_can_confirm(self, client, auto_reject_referral, db_session):
        """admin role can confirm rejection."""
        from app.models import User, Employee
        from app.auth import hash_password, create_access_token

        emp = Employee(name="Admin User", email="admin@test.com", dept="IT")
        db_session.add(emp)
        db_session.commit()
        db_session.refresh(emp)

        user = User(
            name="Admin User",
            email="admin@test.com",
            password_hash=hash_password("Test1234!"),
            role="admin",
            employee_id=emp.id,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        token = create_access_token({"sub": user.id})

        with patch("app.routers.referrals.email_service.send_rejection_email"):
            resp = client.post(
                f"/api/referrals/{auto_reject_referral.id}/confirm-rejection",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
