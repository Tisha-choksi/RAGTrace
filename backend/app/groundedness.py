from __future__ import annotations

import numpy as np

_ef = None


def _get_ef():
    global _ef
    if _ef is None:
        from app.vector_store import vector_store
        _ef = vector_store._embedding_fn
    return _ef


def score_groundedness(response: str, chunks: list[dict]) -> float:
    """
    Returns 0–1: cosine similarity between response and the best-matching chunk.
    A low score means the LLM answer is not well-supported by retrieved context.
    """
    if not chunks or not response.strip():
        return 0.0
    texts = [c.get("text", "") for c in chunks if c.get("text")]
    if not texts:
        return 0.0
    try:
        ef = _get_ef()
        all_embs = np.array(ef([response] + texts), dtype=float)
        norms = np.linalg.norm(all_embs, axis=1, keepdims=True) + 1e-9
        all_embs = all_embs / norms
        similarities = all_embs[1:] @ all_embs[0]
        return float(round(float(np.max(similarities)), 4))
    except Exception:
        return 0.0
