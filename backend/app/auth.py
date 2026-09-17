from datetime import datetime, timedelta
from typing import Optional
import hashlib
import re
import secrets

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from . import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# bcrypt has a hard 72-byte input limit; truncate defensively (passwords this
# long are already well past any reasonable strength requirement).
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:_BCRYPT_MAX_BYTES], hashed.encode("utf-8"))
    except ValueError:
        return False


_PASSWORD_RULES = [
    (re.compile(r".{8,}"), "at least 8 characters"),
    (re.compile(r"[A-Z]"), "an uppercase letter"),
    (re.compile(r"[a-z]"), "a lowercase letter"),
    (re.compile(r"[0-9]"), "a number"),
    (re.compile(r"[^A-Za-z0-9]"), "a special character"),
]


def validate_password_strength(password: str) -> None:
    """Raises HTTPException(422) with a specific, actionable message if the
    password doesn't meet the platform's minimum strength bar."""
    missing = [desc for pattern, desc in _PASSWORD_RULES if not pattern.search(password or "")]
    if missing:
        raise HTTPException(
            status_code=422,
            detail="Password must contain " + ", ".join(missing) + ".",
        )


def _hash_token(raw_token: str) -> str:
    # Reset tokens are high-entropy random strings, not user-chosen secrets,
    # so a fast SHA-256 hash (rather than bcrypt) is appropriate and lets us
    # look the token up by hash without iterating every outstanding token.
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_password_reset_token(db: Session, user: "models.User") -> str:
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    record = models.PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    return raw_token


def consume_password_reset_token(db: Session, raw_token: str) -> "models.User":
    token_hash = _hash_token(raw_token)
    record = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token_hash == token_hash)
        .first()
    )
    if not record or record.used or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Request a new one.")
    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Request a new one.")
    record.used = True
    db.commit()
    return user


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    return user


ADMIN_ROLES = {"hr", "hr_manager", "chro", "vp", "cto", "ceo", "system_admin", "admin"}
HR_ROLES = {"hr", "hr_manager", "chro", "vp", "cto", "ceo", "system_admin", "admin"}
EMPLOYEE_ROLES = {"employee", "manager"}

def require_hr(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role not in HR_ROLES:
        raise HTTPException(status_code=403, detail="HR access required")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
