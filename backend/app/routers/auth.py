from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import quote
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    validate_password_strength,
    generate_password_reset_token,
    consume_password_reset_token,
)
from .. import email_service
from ..config import settings
from .. import msal_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_public(user: models.User):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "employeeId": user.employee_id,
    }


VALID_SSO_ROLES = {"employee", "manager", "hr", "hr_manager", "chro", "vp", "cto", "ceo", "system_admin", "admin"}


def infer_sso_role(email: str) -> str:
    """Best-effort role for a first-time Entra sign-in.

    Priority:
      1. Exact email match in SSO_ROLE_MAP (env JSON, e.g. {"ceo@muraai.com":"ceo"}).
      2. Local-part keyword heuristic for SSO_ORG_DOMAIN accounts
         (ceo/cto/vp/chro/hr/hr_manager/admin/manager/…).
      3. Default 'employee'.
    """
    lowered = (email or "").strip().lower()
    explicit = settings.SSO_ROLE_MAP.get(lowered)
    if explicit and explicit in VALID_SSO_ROLES:
        return explicit

    domain = lowered.rsplit("@", 1)[-1] if "@" in lowered else ""
    if domain != settings.SSO_ORG_DOMAIN.strip().lower():
        return "employee"

    local = lowered.split("@", 1)[0]
    patterns = [
        ("hr_manager", "hr_manager"), ("system_admin", "system_admin"),
        ("chro", "chro"), ("ceo", "ceo"), ("cto", "cto"),
        ("hr", "hr"), ("admin", "admin"), ("manager", "manager"),
        ("vp", "vp"), ("lead", "manager"),
    ]
    for keyword, role in patterns:
        if keyword in local:
            return role
    return "employee"


@router.post("/sso")
def sso_login(payload: schemas.SSOIn, db: Session = Depends(get_db)):
    """SSO provider check — returns whether Microsoft Entra ID SSO is active."""
    if payload.provider == "azure-ad":
        return {
            "ok": msal_service.sso_enabled(),
            "message": "Microsoft Entra ID SSO is active." if msal_service.sso_enabled()
            else "Microsoft SSO is not configured. Contact your administrator.",
            "provider": payload.provider,
        }
    providers = ["saml", "oidc", "azure-ad", "okta", "google"]
    if payload.provider not in providers:
        raise HTTPException(status_code=400, detail=f"Unsupported SSO provider. Supported: {', '.join(providers)}")
    return {
        "ok": False,
        "message": f"SSO with {payload.provider} is configured but not yet active. Contact your administrator.",
        "provider": payload.provider,
    }


@router.get("/microsoft/login")
def microsoft_login():
    """Kick off the Microsoft Entra ID authorization-code flow."""
    if not msal_service.sso_enabled():
        raise HTTPException(status_code=503, detail="Microsoft SSO is not configured. Contact your administrator.")
    callback_url = settings.microsoft_redirect_uri
    auth_url = msal_service.build_auth_url(callback_url)
    return RedirectResponse(auth_url)


@router.get("/microsoft/callback")
def microsoft_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    """Exchange the Entra auth code, upsert the user, and return to the SPA
    with a signed MuraAI token (?sso_token=<jwt>)."""
    if error:
        return RedirectResponse(f"{settings.FRONTEND_URL.rstrip('/')}/desk?sso_error={quote(error_description or error)}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    from ..database import SessionLocal
    callback_url = settings.microsoft_redirect_uri
    result = msal_service.exchange_code(callback_url, code, state=state)
    profile = msal_service.resolve_profile(result)

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == profile["email"]).first()
        if not user:
            # First Entra sign-in provisions the account automatically. Role is
            # inferred from SSO_ROLE_MAP / the email local-part (see infer_sso_role),
            # defaulting to employee. Admin can re-assign later.
            inferred_role = infer_sso_role(profile["email"])
            emp = models.Employee(name=profile["name"], dept="General", email=profile["email"])
            db.add(emp)
            db.flush()
            user = models.User(
                name=profile["name"],
                email=profile["email"],
                password_hash=hash_password("__sso__"),
                role=inferred_role,
                employee_id=emp.id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        elif user.is_active is False:
            raise HTTPException(status_code=403, detail="This account has been deactivated.")
        else:
            user.name = profile["name"] or user.name
            db.commit()

        token = create_access_token({"sub": user.id})

        # Cache the delegated Graph tokens so this user can create Teams
        # meetings / calendar events on their own behalf (best-effort).
        try:
            from .. import ms_graph
            ms_graph.save_tokens(user.id, result)
        except Exception:
            pass

        redirect = f"{settings.FRONTEND_URL.rstrip('/')}/desk?sso_token={token}"
        return RedirectResponse(redirect)
    finally:
        db.close()


@router.get("/microsoft/logout")
def microsoft_logout():
    """End the Microsoft Entra ID session and return to the frontend.

    Redirects to the v2.0 logout endpoint for the configured tenant, which signs
    the user out of Microsoft and posts back to post_logout_redirect_uri (the
    SPA root). The SPA clears the local JWT *before* navigating here, so the
    post-back renders the landing page. If SSO is not configured, just go home.
    """
    base = settings.FRONTEND_URL.rstrip('/')
    tenant = (settings.AZURE_TENANT_ID or "").strip()
    if not tenant or not msal_service.sso_enabled():
        return RedirectResponse(base)
    logout_url = (
        f"https://login.microsoftonline.com/{quote(tenant, safe='')}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={quote(base, safe='')}"
    )
    return RedirectResponse(logout_url)


@router.post("/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "user": user_public(user)}


@router.get("/me")
def me(user: models.User = Depends(get_current_user)):
    return user_public(user)


@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordIn, db: Session = Depends(get_db)):
    """Always returns the same generic message whether or not the email exists —
    prevents account enumeration via response differences."""
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user and user.is_active:
        raw_token = generate_password_reset_token(db, user)
        reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/?reset_token={raw_token}"
        email_service.send_password_reset_email(user.email, reset_link)
    return {"message": "If an account exists for that email, a password reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordIn, db: Session = Depends(get_db)):
    validate_password_strength(payload.newPassword)
    user = consume_password_reset_token(db, payload.token)
    user.password_hash = hash_password(payload.newPassword)
    db.commit()
    return {"message": "Password updated. You can now sign in with your new password."}
