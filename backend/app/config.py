import os
import json
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _resolve_database_url() -> str:
    raw_url = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(PROJECT_ROOT, 'muraai.db')}")
    if raw_url.startswith("sqlite:///") and not raw_url.startswith("sqlite:////"):
        relative_path = raw_url.replace("sqlite:///", "", 1)
        if relative_path and not os.path.isabs(relative_path):
            return f"sqlite:///{os.path.abspath(os.path.join(PROJECT_ROOT, relative_path))}"
    return raw_url


class Settings:
    # Database: defaults to the workspace-level SQLite file, override with a Postgres URL in production
    DATABASE_URL: str = _resolve_database_url()

    # Supabase client (optional, used for auth / storage if desired)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_API_KEY: str = os.getenv("SUPABASE_API_KEY", "")

    # JWT auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-this-secret-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # Ollama local model server — kept server-side only, never sent to the browser
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    # Dedicated embedding model used by the vector store (KB semantic retrieval)
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "all-minilm")
    # Generic AI provider timeout (seconds) for chat & other model calls
    AI_TIMEOUT_SECONDS: float = float(os.getenv("AI_TIMEOUT_SECONDS", "120"))

    # External AI provider settings (can also be configured via Admin panel in DB)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # Gemini: accept both the newer GOOGLE_GENERATIVE_AI_API_KEY and the legacy GEMINI_API_KEY
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    # CORS
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")

    # Optional: automatically create the first HR/admin account on startup from
    # env vars (recommended for production — avoids relying on "first user to
    # register becomes admin"). Leave unset to use that fallback instead.
    BOOTSTRAP_ADMIN_NAME: str = os.getenv("BOOTSTRAP_ADMIN_NAME", "")
    BOOTSTRAP_ADMIN_EMAIL: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "")
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

    ENV: str = os.getenv("ENV", "development")

    # Password reset
    PASSWORD_RESET_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))
    # Base URL of the deployed frontend, used to build the reset link sent by email
    # e.g. https://refer.muraai.com — the SPA reads ?reset_token=... from this URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8000")

    # SMTP (optional). If unset, reset emails are logged instead of sent — fine for
    # local dev, but set these in production or password resets won't reach anyone.
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "MuraAI Refer <no-reply@muraai.com>")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

    # Microsoft Entra ID (MSAL) SSO. When AZURE_CLIENT_ID / AZURE_TENANT_ID are
    # set, the sign-in flow redirects to Entra ID and exchanges the auth code
    # for a session JWT. Leave empty to disable SSO.
    AZURE_CLIENT_ID: str = os.getenv("AZURE_CLIENT_ID", "")
    AZURE_CLIENT_SECRET: str = os.getenv("AZURE_CLIENT_SECRET", "")
    AZURE_TENANT_ID: str = os.getenv("AZURE_TENANT_ID", "")

    # Microsoft Graph mail (send/read) via client credentials. When the Azure
    # app registration has the Graph 'application permissions' Mail.Send and
    # Mail.Read (Admin Consent granted), emails are sent through Graph instead
    # of SMTP. GRAPH_SENDER_EMAIL is the mailbox that sends/reads — e.g. a shared
    # mailbox such as hr@yourcompany.com. Leave GRAPH_SENDER_EMAIL empty to keep
    # old SMTP path.
    GRAPH_SENDER_EMAIL: str = os.getenv("GRAPH_SENDER_EMAIL", "")
    AZURE_AUTHORITY: str = os.getenv(
        "AZURE_AUTHORITY",
        f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID', 'organizations')}",
    )

    # Background scheduler for automated Teams meetings & reminders
    SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() != "false"

    @property
    def microsoft_redirect_uri(self) -> str:
        """The exact redirect URI registered in Entra (App registration ->
        Authentication -> Web). Derived from FRONTEND_URL so the same code works
        for local dev and production: {FRONTEND_URL}/api/auth/microsoft/callback.
        Example: http://localhost:8000/api/auth/microsoft/callback"""
        return f"{self.FRONTEND_URL.rstrip('/')}/api/auth/microsoft/callback"

    # SSO role provisioning. Emails that match a key in SSO_ROLE_MAP (JSON, e.g.
    # {"ceo@muraai.com":"ceo","hr@muraai.com":"hr"}) get that role on first
    # sign-in. Otherwise SSO_ORG_DOMAIN users are provisioned via the email
    # local-part heuristic (ceo/cto/vp/hr/chro/manager/admin prefixes).
    SSO_ROLE_MAP: dict = json.loads(os.getenv("SSO_ROLE_MAP", "{}"))
    SSO_ORG_DOMAIN: str = os.getenv("SSO_ORG_DOMAIN", "muraai.com")


settings = Settings()
