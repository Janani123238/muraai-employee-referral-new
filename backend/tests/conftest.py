"""Shared fixtures for backend tests.

Uses an in-memory SQLite database with StaticPool to ensure all connections
share the same in-memory database (SQLite in-memory DBs are per-connection).
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import User, Employee, Job, Referral
from app.auth import hash_password, create_access_token
from app.main import app


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Yield an isolated SQLAlchemy session backed by an in-memory SQLite DB.

    Uses StaticPool so every connection (including those opened by nested
    commits/refreshes inside the endpoint code) shares the same tables.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign-key enforcement for SQLite
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient whose DB dependency is overridden with our in-memory
    session so every request shares the same transactional context.
    """
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    # Prevent background scheduler and startup hooks from running during tests
    with patch("app.main.start_scheduler"), \
         patch("app.main.stop_scheduler"), \
         patch("app.main.bootstrap"), \
         patch("app.main._build_vector_index_background"):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User / auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def hr_user(db_session):
    """Create an HR user and return (user_model, token_str)."""
    emp = Employee(name="HR Tester", email="hr@test.com", dept="HR")
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)

    user = User(
        name="HR Tester",
        email="hr@test.com",
        password_hash=hash_password("Test1234!"),
        role="hr",
        employee_id=emp.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"sub": user.id})
    return user, token


@pytest.fixture()
def employee_user(db_session):
    """Create an employee (non-HR) user and return (user_model, token_str)."""
    emp = Employee(name="Employee Tester", email="emp@test.com", dept="Engineering")
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)

    user = User(
        name="Employee Tester",
        email="emp@test.com",
        password_hash=hash_password("Test1234!"),
        role="employee",
        employee_id=emp.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"sub": user.id})
    return user, token


# ---------------------------------------------------------------------------
# Job / Referral fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def job(db_session):
    """Create a standard open job and return it."""
    j = Job(title="Backend Developer", skills=["Python", "FastAPI"], status="Open")
    db_session.add(j)
    db_session.commit()
    db_session.refresh(j)
    return j


@pytest.fixture()
def auto_reject_referral(db_session, job, hr_user):
    """Create a referral already in 'Auto-Reject Recommended' status — the
    starting state for the HR-confirmed auto-rejection workflow.
    """
    hr_user_model, _ = hr_user
    referral = Referral(
        candidate_name="Jane Doe",
        email="jane@example.com",
        phone="555-0100",
        resume_text="Experienced Python developer with 5 years of experience.",
        job_id=job.id,
        status="Auto-Reject Recommended",
        match_percent=35,
        original_match=35,
        ai_recommendation="ai_recommended_reject",
        auto_rejected=False,
        review_status="HR_REVIEW_PENDING",
        rejection_reason="AI match score 35% fell below the threshold.",
        evaluation_history=[
            {
                "action": "AI recommended auto-rejection",
                "matchBefore": None,
                "matchAfter": 35,
                "verdict": "ai_recommended_reject",
                "autoReject": False,
                "by": "MuraAI AI",
                "at": datetime.utcnow().isoformat(),
            }
        ],
    )
    db_session.add(referral)
    db_session.commit()
    db_session.refresh(referral)
    return referral


@pytest.fixture()
def normal_referral(db_session, job, employee_user):
    """Create a standard referral in 'Applied' status."""
    emp_user_model, _ = employee_user
    referral = Referral(
        candidate_name="John Smith",
        email="john@example.com",
        phone="555-0200",
        resume_text="Full-stack developer with React and Node.js experience.",
        job_id=job.id,
        status="Applied",
        match_percent=75,
        referred_by=emp_user_model.employee_id,
    )
    db_session.add(referral)
    db_session.commit()
    db_session.refresh(referral)
    return referral
