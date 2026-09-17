from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user, HR_ROLES
from .. import vector_store

router = APIRouter(prefix="/api/kb", tags=["kb"])


def _is_hr(role: str) -> bool:
    return role in HR_ROLES


def _audience_for(user) -> str:
    return "hr" if _is_hr(user.role) else "employee"


@router.get("")
def list_articles(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Role-scoped KB articles. Employees see 'all' + 'employee' articles; HR
    and admins see every article including HR-only guidance."""
    audience = _audience_for(user)
    if audience == "hr":
        rows = db.query(models.KnowledgeArticle).order_by(
            models.KnowledgeArticle.category, models.KnowledgeArticle.title
        ).all()
    else:
        rows = db.query(models.KnowledgeArticle).filter(
            models.KnowledgeArticle.audience.in_(["all", "employee"])
        ).order_by(
            models.KnowledgeArticle.category, models.KnowledgeArticle.title
        ).all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "category": a.category or "General",
            "audience": a.audience or "all",
            "content": a.content,
            "tags": a.tags or [],
            "updatedAt": a.updated_at,
            "updatedBy": a.updated_by,
        }
        for a in rows
    ]


def _get_article_or_404(db, article_id: str) -> models.KnowledgeArticle:
    a = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id == article_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    return a


@router.post("")
def create_article(payload: schemas.KnowledgeArticleIn, db: Session = Depends(get_db),
                   user=Depends(get_current_user)):
    if not _is_hr(user.role):
        raise HTTPException(status_code=403, detail="Only HR or admins can manage the knowledge base.")
    art = models.KnowledgeArticle(
        title=payload.title.strip(),
        category=(payload.category or "General").strip(),
        audience=payload.audience if payload.audience in ("all", "employee", "hr") else "all",
        content=payload.content,
        tags=payload.tags or [],
        updated_by=user.name,
    )
    db.add(art)
    db.commit()
    db.refresh(art)
    _refresh_index(db)
    return {"id": art.id, "title": art.title}


@router.put("/{article_id}")
def update_article(article_id: str, payload: schemas.KnowledgeArticleIn,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _is_hr(user.role):
        raise HTTPException(status_code=403, detail="Only HR or admins can manage the knowledge base.")
    art = _get_article_or_404(db, article_id)
    art.title = payload.title.strip()
    art.category = (payload.category or "General").strip()
    art.audience = payload.audience if payload.audience in ("all", "employee", "hr") else art.audience
    art.content = payload.content
    art.tags = payload.tags or []
    art.updated_by = user.name
    art.updated_at = datetime.utcnow()
    db.commit()
    _refresh_index(db)
    return {"id": art.id, "title": art.title}


@router.delete("/{article_id}")
def delete_article(article_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _is_hr(user.role):
        raise HTTPException(status_code=403, detail="Only HR or admins can manage the knowledge base.")
    art = _get_article_or_404(db, article_id)
    db.delete(art)
    db.commit()
    _refresh_index(db)
    return {"ok": True}


@router.post("/reindex")
def force_reindex(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Rebuild the embedding index for the vector store (KB + policy + jobs)."""
    if not _is_hr(user.role):
        raise HTTPException(status_code=403, detail="Only HR or admins can reindex.")
    result = vector_store.reindex(db)
    return {"ok": True, **result}


def _refresh_index(db: Session):
    """Best-effort background refresh of the embedding index after a write.
    Never blocks or fails the write itself."""
    try:
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(_reindex_worker)
        executor.shutdown(wait=False)
    except Exception:
        pass


def _reindex_worker():
    from ..database import SessionLocal
    try:
        db = SessionLocal()
        try:
            vector_store.reindex(db)
        finally:
            db.close()
    except Exception as exc:
        logging.getLogger("kb").warning("background reindex failed: %s", exc)

