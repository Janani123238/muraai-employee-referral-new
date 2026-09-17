
# MuraAI Refer — Full-Stack Edition

## Fix log (latest pass — real forgot/reset password, strength rules, remember me)

Item 10 of the fix prompt ("Show/Hide Password, Forgot Password, Password
Reset via Email, Strong password validation, Remember Me") wasn't
implemented at all before this pass — there was no reset flow, no server-side
password strength check, and the login form always used `localStorage`
regardless of intent. This adds the real thing:

- **`POST /api/auth/forgot-password`** — generates a single-use, 30-minute
  (configurable) reset token, hashed at rest (`PasswordResetToken` table),
  and emails a reset link via SMTP if `SMTP_HOST` is configured
  (`backend/app/email_service.py`). If SMTP isn't configured, the link is
  logged server-side instead of silently vanishing — set `SMTP_*` in `.env`
  for production. Always returns the same generic message whether or not the
  email exists, to avoid leaking which emails have accounts.
- **`POST /api/auth/reset-password`** — validates the token (exists, unused,
  unexpired), enforces the same password-strength rule as registration, and
  updates the password.
- **Server-side password strength** (`validate_password_strength` in
  `auth.py`) — 8+ chars, upper, lower, number, symbol — now enforced on both
  `/register` and `/reset-password`, not just a client-side hint.
- **Frontend**: real show/hide (👁️) toggle on every password field, a
  "Forgot password?" link → request form → email sent, and a reset screen
  that activates automatically when the app is opened via
  `/?reset_token=...` (what the emailed link points to). "Remember me" on
  login now actually controls whether the session token goes in
  `localStorage` (persists across restarts) or `sessionStorage` (cleared
  when the browser closes).
- New `FRONTEND_URL`, `PASSWORD_RESET_EXPIRE_MINUTES`, and `SMTP_*` settings
  in `.env.example`.

> **Existing databases:** this adds a new `password_reset_tokens` table.
> `create_all` will create it automatically on next startup — no action
> needed, it just won't exist until the app restarts once.

## Fix log (real resume upload + OCR)

Previously, only `.txt` files actually worked. Uploading a PDF/DOC/DOCX just
attached the filename and asked the user to paste the text manually — there
was no real file storage, parsing, or OCR anywhere in the app, despite the
UI implying otherwise. This pass adds the real thing:

- **New endpoint `POST /api/resumes/upload`** (`backend/app/routers/resumes.py`) —
  accepts a multipart file (PDF, DOCX, DOC, PNG/JPG/WEBP), stores it under
  `backend/uploads/resumes/`, and returns extracted plain text.
- **New `backend/app/resume_parser.py`** — real text extraction:
  - PDF: native text layer via `pdfplumber`; any page with too little
    selectable text (i.e. a scanned image) is automatically rendered and
    run through Tesseract OCR (`pdf2image` + `pytesseract`) instead.
  - DOCX: `python-docx` (paragraphs + table cells).
  - PNG/JPG/WEBP: direct OCR via Tesseract.
  - Legacy `.doc` returns a clear error asking for `.docx`/`.pdf` — there's
    no reliable pure-Python parser for the old binary format.
- **Referral records now keep the uploaded file**: `resume_file_url` /
  `resume_file_name` columns added to `Referral`, and `GET /api/resumes/file/{id}`
  serves the stored file back (auth-required).
- **Frontend** (`frontend/index.html`): both the main "Refer Candidate" dropzone
  and the "Autofill from Resume" modal now actually upload PDFs/DOCX/images to
  the backend and use the real extracted text, instead of silently doing
  nothing for anything but `.txt`.
- **New system dependencies**: `tesseract-ocr` and `poppler-utils` (for
  `pdf2image`'s PDF→image rendering) must be installed on the host/Docker
  image — already added to `backend/Dockerfile`. For local dev on macOS:
  `brew install tesseract poppler`; on Debian/Ubuntu:
  `sudo apt install tesseract-ocr poppler-utils`.
- New Python deps in `requirements.txt`: `pdfplumber`, `pdf2image`,
  `python-docx`, `pytesseract`, `pillow`, `python-multipart`.

> **Note on existing databases:** this adds two new columns to the `referrals`
> table. There's no migration tool wired up (SQLAlchemy's `create_all` only
> creates tables that don't exist yet) — on SQLite dev setups, delete
> `muraai.db` and let it recreate, or add the columns manually
> (`ALTER TABLE referrals ADD COLUMN resume_file_url VARCHAR DEFAULT ''`, same
> for `resume_file_name`) before restarting on Postgres/prod.

## Fix log (previous pass)

| Issue reported | Root cause | Fix |
|---|---|---|
| AI Job Match fails on paste | `ANTHROPIC_MODEL` defaulted to a non-existent model string (`claude-sonnet-4-6`) | Defaults to `claude-sonnet-5` in `config.py` and `.env.example`; set `ANTHROPIC_MODEL` explicitly if you use a different model |
| AI errors were opaque / hard to diagnose | `ai_service.call_claude` didn't handle network errors, non-200 responses, or unparseable bodies | Now catches timeouts/connection errors and surfaces a specific message for bad API keys (401) or unknown models (404) instead of a raw 500 |
| Backend crashed on startup (`ValueError: password cannot be longer than 72 bytes…`) | `passlib` (unmaintained since 2020) is broken by modern `bcrypt` (>=4.1) release changes | Removed `passlib`; `auth.py` now calls `bcrypt` directly. Re-run `pip install -r requirements.txt` after pulling this update |
| "Signed up as HR but still see Employee portal" | By design, only the very first account on a fresh DB can register as HR — every later signup is silently forced to Employee | No longer silent: `POST /api/auth/register` now returns a `notice` explaining why, and the register screen calls the new `GET /api/auth/hr-status` to warn *before* you submit. Existing HR admins promote further accounts from Employees → role |
| Add Referral page didn't match the requested design | — | Rebuilt as a two-column layout: candidate form + "Autofill from Resume" on the left, live AI Candidate Summary / Quality Score / Improvement Tips on the right (see screenshots) |
| Empty resume text silently produced bad AI results | No server-side validation | `resumeText` now requires 20+ characters (422 with a clear message otherwise) |

No mock data, mock APIs, or hardcoded demo values were found or reintroduced anywhere in this pass — the app was already wired to the real backend/database end-to-end (see "What changed from the original demo" below).



A complete, deployable version of the MuraAI Refer employee-referral platform:
a **Python (FastAPI) backend** with a real SQL database, JWT authentication,
REST APIs, and server-side Claude API calls, plus the original glassmorphism
frontend wired up to talk to it instead of browser-only mock storage.

```
muraai-refer/
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI app, CORS, static hosting, startup bootstrap
│   │   ├── config.py        env-driven settings
│   │   ├── database.py      SQLAlchemy engine/session
│   │   ├── models.py        User, Employee, Job, Referral, AppSettings
│   │   ├── schemas.py       Pydantic request/response models
│   │   ├── auth.py          password hashing, JWT issue/verify
│   │   ├── ai_service.py    server-side Claude API calls (key never leaves the server)
│   │   ├── seed.py          startup bootstrap — NO fake data, just the settings row + optional first admin
│   │   └── routers/         auth, jobs, referrals, employees, settings, ai
│   ├── static/index.html    bundled frontend (see sync_frontend.sh)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   └── index.html           source of truth for the UI
├── docker-compose.yml       API + Postgres for local/prod
├── sync_frontend.sh         copies frontend/ into backend/static/
└── README.md
```

## What changed from the original demo

The original file was a single HTML artifact that used `window.storage`
(a Claude.ai-only sandbox API) for persistence, called the Anthropic API
directly **from the browser**, and auto-seeded fake jobs/employees/referrals
on every load. This version is a real, deployable application:

- Replaces `window.storage` with a real **Postgres/SQLite database** via SQLAlchemy.
- Moves every AI call (resume parsing, job matching, scoring, fraud checks,
  interview prediction, JD generation, the chat assistant, etc.) **server-side**,
  behind authenticated REST endpoints. Your `ANTHROPIC_API_KEY` lives only in
  the backend's environment variables.
- Adds real **JWT-based authentication** (register/login) instead of fake
  Microsoft/OTP/Face login buttons.
- **No mock data.** A fresh deployment starts with an empty database — no
  fake candidates, no fake employees, no fake jobs. HR adds real jobs and
  onboards real employees through the app itself (see below).
- Adds **role-based authorization**: only accounts with `role=hr` can post
  jobs, change a referral's pipeline status, manage employees, or edit AI
  settings; the backend enforces this even if someone tampers with the frontend.
- All dashboard charts and stats are computed from real stored data — no
  hardcoded chart series or placeholder metrics.
- Everything is safe to actually deploy on a server, in Docker, or on a PaaS.

## 1. Local setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY, JWT_SECRET, and (recommended) the
# BOOTSTRAP_ADMIN_* vars so you have a real HR login on first run

uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Interactive docs (Swagger UI) are
automatically available at `http://localhost:8000/docs`.

### Getting your first HR/admin login

The database starts **completely empty** — no seeded jobs, employees, or
referrals. You have two ways to get your first HR account:

1. **Recommended:** set `BOOTSTRAP_ADMIN_NAME` / `BOOTSTRAP_ADMIN_EMAIL` /
   `BOOTSTRAP_ADMIN_PASSWORD` in `.env` before first startup — that account
   is created automatically and you can log straight in.
2. **Fallback:** leave those unset, open the app, click "Create an account",
   choose **HR / Admin** as the account type, and register. This only
   succeeds for the very first account on a fresh database — every
   registration after that is forced to "Employee", and further HR accounts
   must be granted from the **Employees** panel by an existing HR admin.

Once you're logged in as HR: go to **Manage Jobs** to post real open roles,
and **Employees** to onboard real employees (optionally creating a login for
each one — a one-time temporary password is shown so you can hand it off
securely). Employees can also self-register from the login screen; that
always creates a plain employee account.

### Frontend

The frontend is a single static HTML file with no build step.

**Option A — served by FastAPI (recommended, single service):**
```bash
./sync_frontend.sh          # copies frontend/index.html -> backend/static/index.html
```
Then just open `http://localhost:8000/` — FastAPI serves the file directly
and all `/api/...` calls are same-origin.

**Option B — served separately (e.g. from any static file host):**
Open `frontend/index.html` directly, but first tell it where the API lives
by adding this before the `</head>` tag (or via your host's env injection):
```html
<script>window.MURAAI_API_BASE = 'https://your-api-domain.com';</script>
```
and make sure `CORS_ORIGINS` in the backend `.env` includes your frontend's
origin (not `*`, if you're sending credentials).

## 2. Deploying with Docker

```bash
cp backend/.env.example backend/.env
# edit backend/.env: set ANTHROPIC_API_KEY and a strong JWT_SECRET

./sync_frontend.sh
docker compose up --build -d
```

This starts:
- `db` — Postgres 16 with a persistent volume
- `api` — the FastAPI app (serving the bundled frontend too), on port 8000

Visit `http://localhost:8000`. To use SQLite instead of Postgres for a
lightweight single-container deploy, remove the `db` service and the
`DATABASE_URL` override in `docker-compose.yml` (it will fall back to the
`sqlite:///./muraai.db` default from `.env`).

## 3. Deploying to a cloud platform

Any platform that runs a Docker container or a Python web service works.

**Render / Railway / Fly.io / Heroku-style platforms:**
1. Push this repo to GitHub.
2. Create a new **Web Service** pointing at `backend/` (Dockerfile detected
   automatically), or use the buildpack with:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:$PORT`
3. Add a managed Postgres addon and set `DATABASE_URL` to its connection string.
4. Set environment variables: `ANTHROPIC_API_KEY`, `JWT_SECRET`,
   `CORS_ORIGINS` (your frontend origin, or `*` while testing).
5. Run `./sync_frontend.sh` before deploying (or add it as a pre-build step)
   so the bundled frontend ships with the image.

**Plain VPS (systemd + nginx):**
```bash
# on the server, inside backend/
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 127.0.0.1:8000
```
Put this behind an nginx reverse proxy with TLS (certbot), and point it at
`127.0.0.1:8000`. Run the gunicorn command via a systemd unit so it restarts
on boot/crash.

## 4. Environment variables (`backend/.env`)

| Variable | Purpose | Example |
|---|---|---|
| `DATABASE_URL` | SQL connection string | `postgresql://user:pass@host:5432/db` or `sqlite:///./muraai.db` |
| `JWT_SECRET` | Signs auth tokens — must be long/random in production | `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Login session length | `1440` (24h) |
| `ANTHROPIC_API_KEY` | Your Claude API key, server-side only | `sk-ant-...` |
| `ANTHROPIC_MODEL` | Model string to call | `claude-sonnet-4-6` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `https://app.example.com` |
| `BOOTSTRAP_ADMIN_NAME` | Display name for the auto-created first HR account | `Priya Sharma` |
| `BOOTSTRAP_ADMIN_EMAIL` | Login email for that account | `hr@yourcompany.com` |
| `BOOTSTRAP_ADMIN_PASSWORD` | Login password for that account (change after first login) | `a-strong-password` |

## 5. API overview

All endpoints except `/api/auth/register` and `/api/auth/login` require a
`Authorization: Bearer <token>` header, obtained by logging in.

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | public | Create an employee account (or the first-ever HR account) |
| POST | `/api/auth/login` | public | Get a JWT |
| GET | `/api/auth/me` | any | Current user |
| GET | `/api/jobs` | any | List open roles |
| POST/PUT/DELETE | `/api/jobs...` | hr | Post, edit, or remove real roles |
| GET | `/api/referrals` | any | All referrals |
| GET | `/api/referrals/mine` | any | Your own referrals |
| POST | `/api/referrals` | employee | Submit a referral (AI-enriched server-side) |
| PATCH | `/api/referrals/{id}/status` | hr | Move a candidate through the pipeline |
| GET | `/api/referrals/check-duplicate` | any | Duplicate-candidate check |
| GET | `/api/employees` | any | Employee directory |
| POST | `/api/employees` | hr | Onboard a real employee (optional login + one-time temp password) |
| PUT | `/api/employees/{id}` | hr | Edit profile / activate / deactivate (also disables their login) |
| PATCH | `/api/employees/{id}/role` | hr | Promote/demote an employee's login between employee and hr |
| GET/PUT | `/api/settings` | any / hr | AI feature toggles |
| POST | `/api/ai/parse-resume` | any | Structured resume extraction |
| POST | `/api/ai/match-job`, `/match-all-jobs` | any | Resume ↔ role matching |
| POST | `/api/ai/summary`, `/quality-score`, `/improvement`, `/fraud-check`, `/interview-prediction`, `/auto-tags` | any | Per-candidate AI analysis |
| POST | `/api/ai/compare-candidates` | any | Head-to-head candidate comparison |
| POST | `/api/ai/generate-email`, `/generate-jd` | any / hr flow | Drafting helpers |
| POST | `/api/ai/chat` | any | Contextual chat assistant |

Full interactive docs: `GET /docs` (Swagger) or `GET /redoc`.

## 6. Notes & next steps

- **Migrations:** tables are created with `Base.metadata.create_all` on
  startup, which is fine for a fresh deploy but won't auto-migrate schema
  changes later. For ongoing schema evolution, add
  [Alembic](https://alembic.sqlalchemy.org/) (`pip install alembic`,
  `alembic init migrations`) and generate a migration per model change.
- **Rate limiting / cost control:** each AI endpoint makes one live Claude
  API call. Consider adding a rate limiter (e.g. `slowapi`) in front of
  `/api/ai/*` before opening this up publicly.
- **File uploads:** resume upload currently accepts pasted text or `.txt`
  files client-side — wire in a PDF text-extraction library (e.g. `pypdf`)
  server-side if you need real PDF resume uploads.
- **Real SSO:** the login screen is now real email/password auth. If you
  want actual Microsoft/Google SSO, add an OAuth2 flow (e.g. with
  `authlib`) alongside the existing JWT issuance.
- **Password resets / email delivery:** onboarding an employee returns a
  one-time temporary password directly in the API response for HR to relay
  manually. For a bigger deployment, wire up transactional email (e.g.
  SendGrid/SES) to send it directly and add a forgot-password flow.

=======
# Employee-referral-
>>>>>>> a4e144e1e09b4f729325410776d4aa036282326e
