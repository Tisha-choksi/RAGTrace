import hashlib
import json
from typing import Any


def canonical_chunks(chunks: list[dict[str, Any]]) -> str:
    return json.dumps(chunks, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def generate_audit_hash(query: str, response: str, chunks: list[dict[str, Any]]) -> str:
    payload = query + response + canonical_chunks(chunks)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

