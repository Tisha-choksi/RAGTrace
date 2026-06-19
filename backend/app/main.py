import asyncio
import json
import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, inspect, text
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts import detect_alerts
from app.audit import generate_audit_hash
from app.config import settings
from app.database import Base, engine, get_db
from app.groundedness import score_groundedness
from app.llm import active_model_name, generate_answer, generate_answer_stream
from app.models import AuditLog, Document, DocumentChunk
from app.pii import mask_chunks, mask_pii
from app.pdf_loader import chunk_text, extract_pdf_pages, save_upload
from app.schemas import AuditLogOut, ChatRequest, ChatResponse, DocumentOut, PaginatedLogsResponse, VerifyOut
from app.vector_store import hybrid_query, vector_store

settings.ensure_dirs()
Base.metadata.create_all(bind=engine)


def _fts5_escape(term: str) -> str:
    return '"' + term.replace('"', "") + '"'


def migrate_database() -> None:
    inspector = inspect(engine)
    if "audit_logs" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("audit_logs")}

    with engine.begin() as conn:
        if "alerts" not in columns:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN alerts TEXT DEFAULT '[]'"))
        if "pii_masked" not in columns:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN pii_masked VARCHAR(10) DEFAULT 'true'"))
        if "raw_query" not in columns:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN raw_query TEXT"))
        if "raw_response" not in columns:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN raw_response TEXT"))
        if "raw_retrieved_chunks" not in columns:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN raw_retrieved_chunks TEXT"))
        if "groundedness_score" not in columns:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN groundedness_score REAL"))


migrate_database()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.post("/documents/upload", response_model=DocumentOut)
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)) -> DocumentOut:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")

    try:
        stored_path = save_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    document = Document(filename=file.filename, stored_path=str(stored_path), chunk_count=0)
    db.add(document)
    db.commit()
    db.refresh(document)

    pages = extract_pdf_pages(Path(stored_path))
    texts: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    chunk_index = 0
    for page_number, page_text in pages:
        for chunk in chunk_text(page_text):
            texts.append(chunk)
            metadatas.append(
                {
                    "document_id": document.id,
                    "filename": document.filename,
                    "page": page_number,
                    "chunk_index": chunk_index,
                }
            )
            ids.append(f"doc-{document.id}-chunk-{chunk_index}")
            db.add(DocumentChunk(
                document_id=document.id,
                chunk_index=chunk_index,
                page=page_number,
                chunk_text=chunk,
            ))
            chunk_index += 1

    vector_store.add_chunks(texts, metadatas, ids)
    document.chunk_count = len(texts)
    db.commit()
    db.refresh(document)
    return document


@app.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    return list(db.scalars(select(Document).order_by(Document.uploaded_at.desc())))


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    if request.document_id:
        document = db.get(Document, request.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")

    raw_chunks = hybrid_query(request.query, db, request.document_id)
    masked_query = mask_pii(request.query)
    chunks = mask_chunks(raw_chunks)
    raw_response = await generate_answer(masked_query, chunks)
    response = mask_pii(raw_response)
    groundedness = score_groundedness(response, chunks)
    model = active_model_name()
    timestamp = datetime.now(timezone.utc)
    alerts = detect_alerts(db, request.user_id or "anonymous", masked_query, chunks, timestamp, groundedness)
    sha_hash = generate_audit_hash(masked_query, response, chunks)

    raw_chunks_json = json.dumps(raw_chunks, ensure_ascii=False)
    masked_chunks_json = json.dumps(chunks, ensure_ascii=False)

    log = AuditLog(
        user_id=request.user_id or "anonymous",
        query=masked_query,
        raw_query=request.query if request.query != masked_query else None,
        retrieved_chunks=masked_chunks_json,
        raw_retrieved_chunks=raw_chunks_json if raw_chunks_json != masked_chunks_json else None,
        response=response,
        raw_response=raw_response if raw_response != response else None,
        model=model,
        sha256_hash=sha_hash,
        alerts=json.dumps(alerts, ensure_ascii=False),
        pii_masked="true",
        groundedness_score=groundedness,
        timestamp=timestamp,
        document_id=request.document_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return ChatResponse(
        query=masked_query,
        response=response,
        model=model,
        timestamp=timestamp,
        sha256_hash=sha_hash,
        retrieved_chunks=chunks,
        audit_log_id=log.id,
        alerts=alerts,
        pii_masked=True,
        groundedness_score=groundedness,
    )


async def _stream_chat_events(request: ChatRequest, db: Session):
    """Async generator yielding SSE-formatted events for a streaming chat request."""
    if request.document_id:
        document = db.get(Document, request.document_id)
        if not document:
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Document not found.'})}\n\n"
            return

    raw_chunks = hybrid_query(request.query, db, request.document_id)
    masked_query = mask_pii(request.query)
    chunks = mask_chunks(raw_chunks)

    full_response = ""
    async for token in generate_answer_stream(masked_query, chunks):
        full_response += token
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    response = mask_pii(full_response)
    groundedness = score_groundedness(response, chunks)
    model_name = active_model_name()
    timestamp = datetime.now(timezone.utc)
    alerts = detect_alerts(db, request.user_id or "anonymous", masked_query, chunks, timestamp, groundedness)
    sha_hash = generate_audit_hash(masked_query, response, chunks)

    raw_chunks_json = json.dumps(raw_chunks, ensure_ascii=False)
    masked_chunks_json = json.dumps(chunks, ensure_ascii=False)

    log = AuditLog(
        user_id=request.user_id or "anonymous",
        query=masked_query,
        raw_query=request.query if request.query != masked_query else None,
        retrieved_chunks=masked_chunks_json,
        raw_retrieved_chunks=raw_chunks_json if raw_chunks_json != masked_chunks_json else None,
        response=response,
        raw_response=full_response if full_response != response else None,
        model=model_name,
        sha256_hash=sha_hash,
        alerts=json.dumps(alerts, ensure_ascii=False),
        pii_masked="true",
        groundedness_score=groundedness,
        timestamp=timestamp,
        document_id=request.document_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    done_payload = {
        "type": "done",
        "query": masked_query,
        "response": response,
        "model": model_name,
        "timestamp": timestamp.isoformat(),
        "sha256_hash": sha_hash,
        "retrieved_chunks": chunks,
        "audit_log_id": log.id,
        "alerts": alerts,
        "pii_masked": True,
        "groundedness_score": groundedness,
    }
    yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    return StreamingResponse(
        _stream_chat_events(request, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/audit-logs", response_model=PaginatedLogsResponse)
def audit_logs(
    user_id: str | None = None,
    document_id: int | None = None,
    text: str | None = None,
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedLogsResponse:
    statement = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if user_id:
        statement = statement.where(AuditLog.user_id == user_id)
    if document_id:
        statement = statement.where(AuditLog.document_id == document_id)
    if from_date:
        statement = statement.where(AuditLog.timestamp >= from_date)
    if to_date:
        statement = statement.where(AuditLog.timestamp <= to_date)
    if text:
        if settings.database_url.startswith("sqlite"):
            fts_ids = db.execute(
                text("SELECT rowid FROM audit_logs_fts WHERE audit_logs_fts MATCH :q LIMIT 10000"),
                {"q": _fts5_escape(text)},
            ).scalars().all()
            total = len(fts_ids)
            paged_ids = fts_ids[offset : offset + limit]
            statement = statement.where(AuditLog.id.in_(paged_ids))
            rows = db.scalars(statement).all()
        else:
            like = f"%{text}%"
            statement = statement.where(AuditLog.query.ilike(like) | AuditLog.response.ilike(like))
            total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
            rows = db.scalars(statement.limit(limit).offset(offset)).all()
    else:
        total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = db.scalars(statement.limit(limit).offset(offset)).all()

    items = []
    for row in rows:
        items.append(
            AuditLogOut(
                id=row.id,
                user_id=row.user_id,
                query=row.query,
                retrieved_chunks=json.loads(row.retrieved_chunks),
                response=row.response,
                model=row.model,
                sha256_hash=row.sha256_hash,
                alerts=json.loads(row.alerts or "[]"),
                pii_masked=(row.pii_masked or "true") == "true",
                groundedness_score=row.groundedness_score,
                timestamp=row.timestamp,
                document_id=row.document_id,
                document_name=row.document.filename if row.document else None,
            )
        )
    return PaginatedLogsResponse(items=items, total=total, limit=limit, offset=offset)


@app.get("/audit-logs/export")
def export_audit_logs(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc())).all()
    payload = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "query": row.query,
            "response": row.response,
            "model": row.model,
            "sha256_hash": row.sha256_hash,
            "alerts": json.loads(row.alerts or "[]"),
            "pii_masked": (row.pii_masked or "true") == "true",
            "groundedness_score": row.groundedness_score,
            "timestamp": row.timestamp.isoformat(),
            "document_id": row.document_id,
            "document_name": row.document.filename if row.document else None,
            "retrieved_chunks": json.loads(row.retrieved_chunks),
        }
        for row in rows
    ]

    if format == "json":
        return JSONResponse(
            content=payload,
            headers={"Content-Disposition": "attachment; filename=ragtrace-audit-logs.json"},
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id", "user_id", "query", "response", "model", "sha256_hash",
            "alerts", "pii_masked", "groundedness_score", "timestamp", "document_id", "document_name",
        ],
    )
    writer.writeheader()
    for item in payload:
        row = dict(item)
        row.pop("retrieved_chunks", None)
        row["alerts"] = "; ".join(row["alerts"])
        writer.writerow(row)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ragtrace-audit-logs.csv"},
    )


@app.get("/audit-logs/{log_id}/verify", response_model=VerifyOut)
def verify_log(log_id: int, db: Session = Depends(get_db)) -> VerifyOut:
    log = db.get(AuditLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found.")
    chunks = json.loads(log.retrieved_chunks)
    recomputed = generate_audit_hash(log.query, log.response, chunks)
    return VerifyOut(
        id=log.id,
        stored_hash=log.sha256_hash,
        recomputed_hash=recomputed,
        verified=log.sha256_hash == recomputed,
    )
