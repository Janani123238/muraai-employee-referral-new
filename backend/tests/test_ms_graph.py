"""Tests for Microsoft Graph Teams interview scheduling.

These focus on the integration *logic* that was broken:
  * safe configuration detection (never leaks the secret's value)
  * precise Graph error translation (401/403/404/400)
  * correct scheduling payload + join-URL extraction (mocked HTTP)
"""
import types

import pytest

from app import ms_graph
from app.config import settings


@pytest.fixture
def clear_azure(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AZURE_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", "")


def test_missing_app_config_reports_only_non_secret_vars(clear_azure):
    missing = ms_graph.missing_app_config()
    assert set(missing) == {"AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID"}
    assert ms_graph.app_configured() is False


def test_app_configured_true_when_all_set(clear_azure, monkeypatch):
    monkeypatch.setattr(settings, "AZURE_CLIENT_ID", "id-123")
    monkeypatch.setattr(settings, "AZURE_CLIENT_SECRET", "secret-xyz")
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", "tenant-456")
    assert ms_graph.app_configured() is True
    # The secret value must never appear in the diagnostic output.
    assert "secret-xyz" not in str(ms_graph.missing_app_config())


class _FakeResp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_graph_403_names_missing_permission():
    body = {
        "error": {
            "code": "Forbidden",
            "message": "Access is denied. Missing one or more required permissions: Calendars.ReadWrite.All.",
        }
    }
    with pytest.raises(RuntimeError) as exc:
        ms_graph._raise_graph_error(_FakeResp(403, body))
    msg = str(exc.value)
    assert "403" in msg
    assert "Calendars.ReadWrite.All" in msg
    assert "Dhs8Q" not in msg  # secret must never leak


def test_graph_401_clear_message():
    with pytest.raises(RuntimeError) as exc:
        ms_graph._raise_graph_error(_FakeResp(401, {"error": {"message": "Unauthorized"}}))
    assert "401" in str(exc.value)


def test_graph_404_mailbox_not_found():
    with pytest.raises(RuntimeError) as exc:
        ms_graph._raise_graph_error(_FakeResp(404, {"error": {"message": "User not found"}}))
    assert "404" in str(exc.value)
    assert "mailbox" in str(exc.value).lower()


def test_create_teams_interview_builds_correct_payload(monkeypatch):
    monkeypatch.setattr(ms_graph, "get_app_token", lambda: "fake-token")

    captured = {}

    class _FakePostResp:
        def __init__(self):
            self.status_code = 201
        def json(self):
            return {
                "id": "event-abc",
                "webLink": "https://outlook.office.com/calendar/event",
                "onlineMeeting": {
                    "id": "meeting-xyz",
                    "joinUrl": "https://teams.microsoft.com/l/meetup-join/abc",
                },
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["auth"] = headers.get("Authorization")
        return _FakePostResp()

    monkeypatch.setattr(ms_graph.httpx, "post", fake_post)

    from datetime import datetime
    result = ms_graph.create_teams_interview(
        organizer_upn="interviewer@contoso.com",
        subject="Interview: Jane — Technical Round 1",
        start_dt=datetime(2026, 9, 1, 10, 0),
        end_dt=datetime(2026, 9, 1, 10, 45),
        timezone="Asia/Kolkata",
        attendee_emails=["candidate@contoso.com", "interviewer@contoso.com"],
        body="Notes",
    )

    # Organizer must not also be an attendee.
    attendee_addresses = [a["emailAddress"]["address"] for a in captured["json"]["attendees"]]
    assert "interviewer@contoso.com" not in attendee_addresses
    assert "candidate@contoso.com" in attendee_addresses

    assert captured["json"]["isOnlineMeeting"] is True
    assert captured["json"]["onlineMeetingProvider"] == "teamsForBusiness"
    assert "/users/interviewer%40contoso.com/calendar/events" in captured["url"]
    assert captured["auth"] == "Bearer fake-token"

    assert result["event_id"] == "event-abc"
    assert result["join_url"] == "https://teams.microsoft.com/l/meetup-join/abc"
    assert result["online_meeting_id"] == "meeting-xyz"
