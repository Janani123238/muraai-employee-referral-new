from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def serialize(n: models.Notification):
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "type": n.type,
        "category": n.category,
        "isRead": n.is_read,
        "link": n.link,
        "created_at": n.created_at,
    }


def create_notification(db: Session, user_id: str, title: str, message: str,
                        ntype: str = "info", category: str = "general", link: str = ""):
    n = models.Notification(
        user_id=user_id, title=title, message=message,
        type=ntype, category=category, link=link,
    )
    db.add(n)
    db.commit()
    return n


@router.get("")
def list_notifications(db: Session = Depends(get_db), user=Depends(get_current_user)):
    notes = db.query(models.Notification).filter(
        models.Notification.user_id == user.id
    ).order_by(desc(models.Notification.created_at)).limit(50).all()
    return [serialize(n) for n in notes]


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user=Depends(get_current_user)):
    count = db.query(models.Notification).filter(
        models.Notification.user_id == user.id,
        models.Notification.is_read == False,
    ).count()
    return {"count": count}


@router.post("/mark-read")
def mark_read(payload: schemas.NotificationMarkRead, db: Session = Depends(get_db),
              user=Depends(get_current_user)):
    if payload.ids:
        db.query(models.Notification).filter(
            models.Notification.id.in_(payload.ids),
            models.Notification.user_id == user.id,
        ).update({models.Notification.is_read: True}, synchronize_session=False)
    else:
        db.query(models.Notification).filter(
            models.Notification.user_id == user.id,
            models.Notification.is_read == False,
        ).update({models.Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"ok": True}
