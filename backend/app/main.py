from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import logging
import sys

# Configure logging so custom module loggers (ms_graph, interviews) appear in
# container stdout — gunicorn's access log alone does not capture them.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

from sqlalchemy import text

from .database import Base, engine, SessionLocal
from .config import settings
from .seed import bootstrap
from .routers import auth, jobs, referrals, employees, settings as settings_router, ai, resumes, notifications, policy, admin, reports, interviews, activity, candidates, emails, kb
from .scheduler import start_scheduler, stop_scheduler

Base.metadata.create_all(bind=engine)


def ensure_columns():
    """Idempotent, migration-safe column backfills for existing SQLite databases."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    db = SessionLocal()
    try:
        backfills = {
            "employees": [("phone", "TEXT DEFAULT ''"), ("location", "TEXT DEFAULT ''")],
            "jobs": [("is_deleted", "BOOLEAN DEFAULT 0"), ("deleted_at", "DATETIME"), ("deleted_by", "TEXT DEFAULT ''")],
            "referrals": [("is_deleted", "BOOLEAN DEFAULT 0"), ("deleted_at", "DATETIME"),
                          ("deleted_by", "TEXT DEFAULT ''"), ("screening", "TEXT"),
                          ("auto_rejected", "BOOLEAN DEFAULT 0"),
                          ("review_status", "TEXT DEFAULT ''"),
                          ("match_breakdown", "TEXT"),
                          ("rejection_reason", "TEXT DEFAULT ''"),
                          ("original_match", "INTEGER DEFAULT 0"),
                          ("match_percent", "INTEGER DEFAULT 0"),
                          ("rank_label", "TEXT DEFAULT ''"),
                          ("evaluation_history", "TEXT"),
                          ("review_deadline", "DATETIME"),
                          ("last_review_reminder", "DATETIME"),
                          ("ai_recommendation", "TEXT DEFAULT ''"),
                          ("rejection_confirmed_by", "TEXT DEFAULT ''"),
                          ("rejection_confirmed_at", "DATETIME"),
                          ("rejection_email_sent", "BOOLEAN DEFAULT 0"),
                          ("rejection_email_sent_at", "DATETIME"),
                          ("rejection_email_status", "TEXT DEFAULT ''"),
                          ("rejection_email_error", "TEXT DEFAULT ''")],
            "interviews": [("is_deleted", "BOOLEAN DEFAULT 0"), ("deleted_at", "DATETIME"),
                           ("deleted_by", "TEXT DEFAULT ''"), ("meeting_id", "TEXT DEFAULT ''"),
                           ("graph_event_id", "TEXT DEFAULT ''"), ("timezone", "TEXT DEFAULT ''")],
            "app_settings": [("sender_name", "TEXT DEFAULT ''")],
        }
        for table, cols in backfills.items():
            try:
                existing = {row[1] for row in db.execute(text(f"PRAGMA table_info({table})")).fetchall()}
            except Exception:
                continue
            for col, ddl in cols:
                if col not in existing:
                    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        # If a database was created by an interim model that used a dedicated
        # jd_vs_resume_match column, bring it in line with the match_percent name
        # that the rest of the app (and the schema) uses.
        try:
            ref_cols = {row[1] for row in db.execute(text("PRAGMA table_info(referrals)")).fetchall()}
            if "jd_vs_resume_match" in ref_cols and "match_percent" not in ref_cols:
                db.execute(text("ALTER TABLE referrals RENAME COLUMN jd_vs_resume_match TO match_percent"))
        except Exception:
            db.rollback()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

ensure_columns()


def drop_ats_score():
    """Remove the dedicated ATS Score column from existing databases.

    SQLite only gained ALTER TABLE ... DROP COLUMN in 3.35.0. On engines too
    old to drop it, the column is left in place unused — the ORM no longer
    reads, writes, or serializes it, so nothing breaks.
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        db = SessionLocal()
        try:
            cols = {row[1] for row in db.execute(text("PRAGMA table_info(referrals)")).fetchall()}
            if "ats_score" not in cols:
                return
            try:
                db.execute(text("ALTER TABLE referrals DROP COLUMN ats_score"))
            except Exception:
                db.rollback()
                logging.getLogger("app.startup").warning(
                    "Could not drop referrals.ats_score on this SQLite version; "
                    "leaving the unused column in place."
                )
        except Exception:
            db.rollback()
        finally:
            db.close()
    else:
        db = SessionLocal()
        try:
            db.execute(text("ALTER TABLE referrals DROP COLUMN IF EXISTS ats_score"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


drop_ats_score()

# PostgreSQL migration: add new columns if they don't exist
try:
    _db = SessionLocal()
    try:
        for _table, _col, _ddl in [
            ("referrals", "review_deadline", "TIMESTAMP NULL"),
            ("referrals", "last_review_reminder", "TIMESTAMP NULL"),
            ("referrals", "match_percent", "INTEGER DEFAULT 0"),
            ("referrals", "original_match", "INTEGER DEFAULT 0"),
            ("referrals", "rank_label", "VARCHAR DEFAULT ''"),
            ("referrals", "ai_recommendation", "VARCHAR DEFAULT ''"),
            ("referrals", "rejection_confirmed_by", "VARCHAR DEFAULT ''"),
            ("referrals", "rejection_confirmed_at", "TIMESTAMP NULL"),
            ("referrals", "rejection_email_sent", "BOOLEAN DEFAULT FALSE"),
            ("referrals", "rejection_email_sent_at", "TIMESTAMP NULL"),
            ("referrals", "rejection_email_status", "VARCHAR DEFAULT ''"),
            ("referrals", "rejection_email_error", "TEXT DEFAULT ''"),
            ("referrals", "review_status", "VARCHAR DEFAULT ''"),
            ("referrals", "match_breakdown", "JSONB NULL"),
            ("app_settings", "sender_name", "VARCHAR DEFAULT ''"),
        ]:
            try:
                _exists = _db.execute(text(
                    f"SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='{_table}' AND column_name='{_col}')"
                )).scalar()
                if not _exists:
                    _db.execute(text(f"ALTER TABLE {_table} ADD COLUMN {_col} {_ddl}"))
            except Exception:
                pass
        # Interim-model databases may have a dedicated jd_vs_resume_match column;
        # rename it to match_percent so the ORM (which reads match_percent) works.
        try:
            _mpe = _db.execute(text(
                "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                "WHERE table_name='referrals' AND column_name='match_percent')"
            )).scalar()
            _jvr = _db.execute(text(
                "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                "WHERE table_name='referrals' AND column_name='jd_vs_resume_match')"
            )).scalar()
            if _jvr and not _mpe:
                _db.execute(text("ALTER TABLE referrals RENAME COLUMN jd_vs_resume_match TO match_percent"))
        except Exception:
            _db.rollback()
        _db.commit()
    except Exception:
        _db.rollback()
    finally:
        _db.close()
except Exception:
    pass

# Backfill review_deadline for existing referrals that don't have one set
try:
    _db = SessionLocal()
    try:
        _db.execute(text("""
            UPDATE referrals
            SET review_deadline = submitted_date + INTERVAL '7 days'
            WHERE review_deadline IS NULL
              AND submitted_date IS NOT NULL
              AND is_deleted = false
        """))
        _db.commit()
    except Exception:
        _db.rollback()
    finally:
        _db.close()
except Exception:
    pass


app = FastAPI(title="MuraAI Refer API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(referrals.router)
app.include_router(employees.router)
app.include_router(settings_router.router)
app.include_router(ai.router)
app.include_router(resumes.router)
app.include_router(notifications.router)
app.include_router(policy.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(interviews.router)
app.include_router(activity.router)
app.include_router(candidates.router)
app.include_router(emails.router)
app.include_router(kb.router)


@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    try:
        bootstrap(db)
    finally:
        db.close()
    _build_vector_index_background()
    # Start the background scheduler for automated Teams meetings & reminders
    if settings.SCHEDULER_ENABLED:
        try:
            start_scheduler()
        except Exception as exc:
            logging.getLogger("startup").warning("Scheduler startup skipped: %s", exc)


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


def _build_vector_index_background():
    """Warm the semantic embedding index on startup without blocking the server.
    Best-effort: if Ollama is down the index just gets built on first chat."""
    try:
        from concurrent.futures import ThreadPoolExecutor
        from . import vector_store, models

        def work():
            db = SessionLocal()
            try:
                if db.query(models.DocumentChunk).count() == 0:
                    vector_store.reindex(db)
            except Exception as exc:
                import logging
                logging.getLogger("startup").warning("vector index warm-up skipped: %s", exc)
            finally:
                db.close()

        ThreadPoolExecutor(max_workers=1).submit(work)
    except Exception:
        pass


@app.get("/api/health")
def health():
    from .scheduler import scheduler
    jobs = []
    if scheduler.running:
        jobs = [j.id for j in scheduler.get_jobs()]
    return {"status": "ok", "scheduler": {"running": scheduler.running, "jobs": jobs}}


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


class NoCacheStaticFiles(StaticFiles):
    """Serve static files with revalidation headers so browsers always pick up
    fresh JS/CSS after a redeploy instead of replaying stale cached copies."""
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


if os.path.isdir(FRONTEND_DIR):
    CSS_DIR = os.path.join(FRONTEND_DIR, "css")
    JS_DIR = os.path.join(FRONTEND_DIR, "js")
    if os.path.isdir(CSS_DIR):
        app.mount("/css", NoCacheStaticFiles(directory=CSS_DIR), name="css")
    if os.path.isdir(JS_DIR):
        app.mount("/js", NoCacheStaticFiles(directory=JS_DIR), name="js")
    app.mount("/assets", NoCacheStaticFiles(directory=FRONTEND_DIR), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        return FileResponse(index_path)
