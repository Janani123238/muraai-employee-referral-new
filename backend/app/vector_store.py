"""Embeddings vector store for semantic RAG over the knowledge base.

Produces embeddings with a local Ollama embedding model (default: all-minilm),
stores chunk vectors in SQLite (``document_chunks``) and searches them with
cosine similarity. Uses FAISS (IndexFlatIP) when available for speed, and
falls back to a pure-Python cosine scan otherwise — so a missing native lib
never breaks the assistant.

All entry points are defensive: if Ollama is unreachable or embeddings fail,
they return empty results and the caller keeps working with structured
DB-context RAG only.
"""
import hashlib
import json
import logging
import time
from typing import List, Optional

from sqlalchemy.orm import Session

from .config import settings
from . import models

logger = logging.getLogger("vector_store")

try:
    import numpy as np
    import faiss

    _HAS_FAISS = True
except Exception:  # pragma: no cover - native lib optional
    _HAS_FAISS = False
    np = None
    faiss = None

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None

try:
    import http.client
except Exception:  # pragma: no cover
    http.client = None

_index_cache = {"signature": None, "index": None, "chunks": None}

_EMBED_TIMEOUT = 30
# all-minilm (and similar small models) have short contexts; keep embedding
# input comfortably inside the token budget so chunks never 500 on length.
_MAX_EMBED_CHARS = 1800

# Embedding cache: avoid re-embedding the same text within a session
_embed_text_cache = {}
_EMBED_CACHE_TTL = 3600  # 1 hour


def _embed_sync(text: str) -> Optional[List[float]]:
    """Embed a single text via Ollama using a raw stdlib HTTP call.

    Deliberately uses http.client (not httpx/requests) so localhost calls never
    get routed through system proxies, which caused long hangs on Windows."""
    if not text or not text.strip() or http.client is None:
        return None
    host = settings.OLLAMA_BASE_URL.rstrip("/")
    if host.startswith("http://"):
        host = host[len("http://"):]
    elif host.startswith("https://"):
        host = host[len("https://"):]
    path = "/api/embeddings"
    payload = json.dumps({"model": settings.OLLAMA_EMBED_MODEL, "prompt": text.strip()[:_MAX_EMBED_CHARS]})
    try:
        conn = http.client.HTTPConnection(host, timeout=_EMBED_TIMEOUT)
        try:
            conn.request("POST", path, body=payload, headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            raw = resp.read()
            if resp.status != 200:
                logger.warning("embed HTTP %s: %s", resp.status, raw[:200])
                return None
            emb = json.loads(raw.decode("utf-8")).get("embedding")
            return list(emb) if emb else None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("embed failed: %s", exc)
        return None


def embed_text(text: str) -> Optional[List[float]]:
    """Embed a single text (sync). Returns a float list or None on failure."""
    if not text or not text.strip():
        return None
    # Check cache first
    cache_key = hashlib.sha256(text.strip()[:1800].encode("utf-8")).hexdigest()
    now = time.time()
    if cache_key in _embed_text_cache:
        cached_ts, cached_emb = _embed_text_cache[cache_key]
        if now - cached_ts < _EMBED_CACHE_TTL:
            return cached_emb
    result = _embed_sync(text)
    if result is not None:
        _embed_text_cache[cache_key] = (now, result)
        # Keep cache size manageable
        if len(_embed_text_cache) > 100:
            _embed_text_cache.clear()
    return result


def _to_float_list(raw) -> List[float]:
    try:
        vals = json.loads(raw)
        return [float(v) for v in vals]
    except Exception:
        return []


def _chunks_for(db: Session, audience: str) -> List[models.DocumentChunk]:
    """Chunks the given audience may see. 'all' is visible to everyone."""
    if audience == "hr":
        return db.query(models.DocumentChunk).all()
    return (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.audience.in_(["all", audience]))
        .all()
    )


def _build_index(db: Session, audience: str):
    """Build (or reuse) a normalized cosine index over the visible chunks."""
    chunks = _chunks_for(db, audience)
    signature = (len(chunks), json.dumps([c.id for c in chunks]))
    cached = _index_cache.get("signature")
    if cached == signature and _index_cache.get("chunks"):
        return _index_cache["index"], _index_cache["chunks"]

    embs = []
    valid = []
    for c in chunks:
        vec = _to_float_list(c.embedding)
        if len(vec) >= 8:
            embs.append(vec)
            valid.append(c)
    index = None
    if embs and _HAS_FAISS:
        try:
            mat = np.asarray(embs, dtype="float32")
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            mat = mat / norms
            index = faiss.IndexFlatIP(mat.shape[1])
            index.add(mat)
        except Exception as exc:
            logger.warning("faiss build failed, falling back to numpy scan: %s", exc)
            index = None
    _index_cache["signature"] = signature
    _index_cache["chunks"] = valid
    _index_cache["index"] = index
    return index, valid


def _cosine_similarities(query: List[float], rows) -> List[float]:
    """Pure-Python cosine fallback — no numpy required."""
    qn = sum(v * v for v in query) ** 0.5
    if qn == 0:
        return [0.0] * len(rows)
    out = []
    for emb in rows:
        dot = sum(a * b for a, b in zip(query, emb))
        en = sum(v * v for v in emb) ** 0.5
        out.append(dot / (qn * en) if en else 0.0)
    return out


def retrieve(db: Session, query: str, audience: str = "all", top_k: int = 4) -> List[dict]:
    """Return the top-k most semantically relevant chunks for the query.

    Each result: {title, sourceType, sourceId, content, score}.
    """
    if not query or not query.strip():
        return []
    try:
        index, chunks = _build_index(db, audience)
    except Exception as exc:
        logger.warning("vector retrieve index build failed: %s", exc)
        return []
    if not chunks:
        return []

    query_emb = embed_text(query)
    if not query_emb or len(query_emb) < 8:
        return []

    if index is not None and _HAS_FAISS:
        try:
            qv = np.asarray([query_emb], dtype="float32")
            qn = np.linalg.norm(qv)
            if qn:
                qv = qv / qn
            scores, idxs = index.search(qv, min(top_k, len(chunks)))
            results = []
            for score, ci in zip(scores[0], idxs[0]):
                if ci < 0 or score <= 0:
                    continue
                c = chunks[int(ci)]
                results.append({
                    "title": c.title or "",
                    "sourceType": c.source_type or "kb",
                    "sourceId": c.source_id or "",
                    "content": c.content,
                    "score": round(float(score), 4),
                })
            return results
        except Exception as exc:
            logger.warning("faiss search failed, falling back to numpy scan: %s", exc)

    scores = _cosine_similarities(query_emb, [_to_float_list(c.embedding) for c in chunks])
    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [
        {
            "title": c.title or "",
            "sourceType": c.source_type or "kb",
            "sourceId": c.source_id or "",
            "content": c.content,
            "score": round(float(s), 4),
        }
        for c, s in ranked[:top_k]
        if s > 0.12
    ]


def reset_index_cache():
    _index_cache["signature"] = None
    _index_cache["index"] = None
    _index_cache["chunks"] = None


def _split_content(text: str, max_chars: int = 1400) -> List[str]:
    """Split a long text into chunks on paragraph/sentence boundaries."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    parts = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        while len(para) > max_chars:
            split_at = para.rfind(" ", 0, max_chars)
            if split_at < max_chars * 0.6:
                split_at = max_chars
            parts.append(para[:split_at].strip())
            para = para[split_at:].strip()
        if para:
            parts.append(para)
    return parts


def reindex(db: Session) -> dict:
    """Wipe and rebuild the embedding index from KB articles, policy, and jobs."""
    db.query(models.DocumentChunk).delete()
    db.commit()

    texts, meta = [], []

    articles = db.query(models.KnowledgeArticle).all()
    for art in articles:
        for seg in _split_content(art.content):
            texts.append(f"{art.title}\n{seg}")
            meta.append(("kb", art.id, art.title, seg, art.audience or "all"))

    policy = db.query(models.ReferralPolicy).first()
    if policy and policy.content:
        for seg in _split_content(policy.content):
            texts.append(f"Referral Policy\n{seg}")
            meta.append(("policy", "policy", "Referral Policy", seg, "all"))

    jobs = db.query(models.Job).all()
    for job in jobs:
        body = f"{job.title} | dept: {job.dept} | exp: {job.exp} | loc: {job.location}"
        if job.skills:
            body += f" | skills: {', '.join(job.skills)}"
        if job.description:
            body += f"\n{job.description}"
        for seg in _split_content(body):
            texts.append(seg)
            meta.append(("job", job.id, job.title, seg, "all"))

    embeddings = [embed_text(t) for t in texts]
    added = 0
    for (source_type, source_id, title, seg, audience), emb in zip(meta, embeddings):
        if emb:
            db.add(models.DocumentChunk(
                source_type=source_type,
                source_id=source_id,
                title=title,
                content=seg.strip(),
                audience=audience,
                embedding=json.dumps(emb),
            ))
            added += 1
    db.commit()
    reset_index_cache()
    return {"chunks": added, "sources": len({m[1] for m in meta})}
