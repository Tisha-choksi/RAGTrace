from __future__ import annotations

import re
import threading
from typing import TYPE_CHECKING, Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_lock = threading.Lock()
_instance: "VectorStore | None" = None

_reranker: Any = None
_reranker_loaded = False
_reranker_lock = threading.Lock()


def _get_reranker() -> Any:
    global _reranker, _reranker_loaded
    if not _reranker_loaded:
        with _reranker_lock:
            if not _reranker_loaded:
                _reranker_loaded = True
                if settings.enable_reranker:
                    try:
                        from sentence_transformers.cross_encoder import CrossEncoder
                        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                    except Exception:
                        _reranker = None
    return _reranker


def _fts5_query(query: str) -> str:
    words = [w for w in re.sub(r"[^\w\s]", " ", query).split() if len(w) > 2]
    if not words:
        return '""'
    return " OR ".join(f'"{w}"' for w in words[:12])


class VectorStore:
    def __init__(self) -> None:
        if settings.chroma_server_host:
            self.client = chromadb.HttpClient(
                host=settings.chroma_server_host,
                port=settings.chroma_server_port,
            )
        else:
            self.client = chromadb.PersistentClient(path=settings.chroma_dir)
        self._embedding_fn = SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
        self.collection = self.client.get_or_create_collection(
            name="rag_documents",
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[str], metadatas: list[dict[str, Any]], ids: list[str]) -> None:
        if chunks:
            self.collection.add(documents=chunks, metadatas=metadatas, ids=ids)

    def query(self, query: str, document_id: int | None = None, n_results: int = 5) -> list[dict[str, Any]]:
        where = {"document_id": document_id} if document_id else None
        result = self.collection.query(query_texts=[query], n_results=n_results, where=where)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        chunks = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            item = dict(metadata)
            item["text"] = text
            item["score"] = None if distance is None else round(1 - float(distance), 4)
            chunks.append(item)
        return chunks


def get_vector_store() -> VectorStore:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = VectorStore()
    return _instance


vector_store = get_vector_store()


def hybrid_query(
    query: str,
    db: "Session",
    document_id: int | None = None,
    n_results: int = 5,
) -> list[dict[str, Any]]:
    """
    Combine ChromaDB vector search + SQLite FTS5 keyword search via Reciprocal Rank
    Fusion, then re-rank the merged candidates with a cross-encoder.
    """
    from sqlalchemy import select
    from sqlalchemy import text as sa_text

    from app.models import Document, DocumentChunk

    candidate_count = max(n_results * 4, 20)

    # ── 1. Vector search ──────────────────────────────────────────────────────
    vector_results = vector_store.query(query, document_id, n_results=candidate_count)

    # ── 2. Keyword search (FTS5 for SQLite, ILIKE for PostgreSQL) ─────────────
    fts_q = _fts5_query(query)
    fts_results: list[dict[str, Any]] = []
    try:
        from sqlalchemy import text as sa_text
        is_sqlite = str(db.bind.url).startswith("sqlite")

        if is_sqlite:
            if document_id:
                rows = db.execute(
                    sa_text(
                        "SELECT dc.id FROM document_chunks dc "
                        "JOIN document_chunks_fts fts ON fts.rowid = dc.id "
                        "WHERE document_chunks_fts MATCH :q AND dc.document_id = :did "
                        "ORDER BY fts.rank LIMIT :lim"
                    ),
                    {"q": fts_q, "did": document_id, "lim": candidate_count},
                ).fetchall()
            else:
                rows = db.execute(
                    sa_text(
                        "SELECT rowid FROM document_chunks_fts "
                        "WHERE document_chunks_fts MATCH :q "
                        "ORDER BY rank LIMIT :lim"
                    ),
                    {"q": fts_q, "lim": candidate_count},
                ).fetchall()
            fts_ids = [r[0] for r in rows]
        else:
            stmt = select(DocumentChunk)
            if document_id:
                stmt = stmt.where(DocumentChunk.document_id == document_id)
            like = f"%{query}%"
            stmt = stmt.where(DocumentChunk.chunk_text.ilike(like)).limit(candidate_count)
            objs = db.scalars(stmt).all()
            fts_ids = [o.id for o in objs]

        if fts_ids:
            id_to_rank = {rid: rank for rank, rid in enumerate(fts_ids)}
            objs = db.scalars(
                select(DocumentChunk).where(DocumentChunk.id.in_(fts_ids))
            ).all()
            objs_sorted = sorted(objs, key=lambda o: id_to_rank.get(o.id, 9999))
            fts_results = [
                {
                    "text": obj.chunk_text,
                    "document_id": obj.document_id,
                    "page": obj.page,
                    "chunk_index": obj.chunk_index,
                    "filename": None,
                    "score": None,
                }
                for obj in objs_sorted
            ]
    except Exception:
        pass

    # ── 3. Reciprocal Rank Fusion (k=60) ──────────────────────────────────────
    K = 60
    rrf_scores: dict[str, float] = {}
    candidates: dict[str, dict[str, Any]] = {}

    for rank, chunk in enumerate(vector_results):
        key = f"{chunk.get('document_id')}-{chunk.get('chunk_index')}"
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (K + rank + 1)
        candidates[key] = chunk

    for rank, chunk in enumerate(fts_results):
        key = f"{chunk.get('document_id')}-{chunk.get('chunk_index')}"
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (K + rank + 1)
        if key not in candidates:
            candidates[key] = chunk

    top_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)[: n_results * 2]
    merged = [candidates[k] for k in top_keys]

    # ── 4. Cross-encoder re-ranking (optional, lazy-loaded) ───────────────────
    reranker = _get_reranker()
    if reranker is not None and len(merged) > 1:
        pairs = [(query, c.get("text", "")) for c in merged]
        try:
            ce_scores: list[float] = reranker.predict(pairs).tolist()
            for chunk, ce_score in zip(merged, ce_scores):
                chunk["score"] = round(float(ce_score), 4)
            merged.sort(key=lambda c: c.get("score") or 0.0, reverse=True)
        except Exception:
            pass

    # Fallback score from RRF for chunks not scored by cross-encoder
    for key, chunk in zip(top_keys, merged):
        if chunk.get("score") is None:
            chunk["score"] = round(rrf_scores.get(key, 0.0), 6)

    # ── 5. Resolve filenames for FTS-only hits ────────────────────────────────
    missing_name_ids = {c["document_id"] for c in merged if not c.get("filename") and c.get("document_id")}
    if missing_name_ids:
        doc_map = {
            d.id: d.filename
            for d in db.scalars(select(Document).where(Document.id.in_(missing_name_ids))).all()
        }
        for chunk in merged:
            if not chunk.get("filename"):
                chunk["filename"] = doc_map.get(chunk.get("document_id"), "unknown")

    return merged[:n_results]
