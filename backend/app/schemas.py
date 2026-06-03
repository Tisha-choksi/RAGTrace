from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: int
    filename: str
    chunk_count: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str = "anonymous"
    document_id: int | None = None


class RetrievedChunk(BaseModel):
    text: str
    document_id: int
    filename: str
    page: int
    chunk_index: int
    score: float | None = None


class ChatResponse(BaseModel):
    query: str
    response: str
    model: str
    timestamp: datetime
    sha256_hash: str
    retrieved_chunks: list[RetrievedChunk]
    audit_log_id: int
    alerts: list[str] = []
    pii_masked: bool = True
    groundedness_score: float | None = None


class AuditLogOut(BaseModel):
    id: int
    user_id: str
    query: str
    retrieved_chunks: list[dict[str, Any]]
    response: str
    model: str
    sha256_hash: str
    alerts: list[str] = []
    pii_masked: bool = True
    groundedness_score: float | None = None
    timestamp: datetime
    document_id: int | None = None
    document_name: str | None = None


class PaginatedLogsResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


class VerifyOut(BaseModel):
    id: int
    stored_hash: str
    recomputed_hash: str
    verified: bool
