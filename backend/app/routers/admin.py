from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from .. import models
from ..auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-logs")
def list_audit_logs(db: Session = Depends(get_db), user=Depends(require_admin)):
    logs = db.query(models.AuditLog).order_by(desc(models.AuditLog.created_at)).limit(200).all()
    return [{
        "id": l.id, "userName": l.user_name, "userRole": l.user_role,
        "action": l.action, "target": l.target, "targetId": l.target_id,
        "details": l.details, "created_at": l.created_at,
    } for l in logs]


@router.get("/users")
def list_all_users(db: Session = Depends(get_db), user=Depends(require_admin)):
    users = db.query(models.User).all()
    return [{
        "id": u.id, "name": u.name, "email": u.email,
        "role": u.role, "isActive": u.is_active, "created_at": u.created_at,
    } for u in users]


@router.patch("/users/{user_id}/role")
def change_user_role(user_id: str, role: str, db: Session = Depends(get_db),
                     user=Depends(require_admin)):
    VALID_ROLES = {"employee", "manager", "hr", "hr_manager", "chro", "vp", "cto", "ceo", "system_admin", "admin"}
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    old_role = target.role
    target.role = role
    db.commit()
    log_audit(db, user, "Role changed", target="user", target_id=user_id,
              details=f"{old_role} -> {role}")
    return {"ok": True, "role": role}


def log_audit(db: Session, user, action: str, target: str = "", target_id: str = "", details: str = ""):
    log = models.AuditLog(
        user_id=user.id if user else "",
        user_name=user.name if user else "",
        user_role=user.role if user else "",
        action=action, target=target, target_id=target_id, details=details,
    )
    db.add(log)
    db.commit()
