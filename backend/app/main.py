import json
import csv
import io
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import inspect, text
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts import detect_alerts
from app.audit import generate_audit_hash
from app.config import settings
from app.database import Base, engine, get_db
from app.llm import active_model_name, generate_answer
from app.models import AuditLog, Document
from app.pii import mask_chunks, mask_pii
from app.pdf_loader import chunk_text, extract_pdf_pages, save_upload
from app.schemas import AuditLogOut, ChatRequest, ChatResponse, DocumentOut, VerifyOut
from app.vector_store import vector_store

settings.ensure_dirs()
Base.metadata.create_all(bind=engine)


def migrate_sqlite() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "audit_logs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("audit_logs")}
    with engine.begin() as connection:
        if "alerts" not in columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN alerts TEXT DEFAULT '[]'"))
        if "pii_masked" not in columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN pii_masked VARCHAR(10) DEFAULT 'true'"))


migrate_sqlite()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.post("/documents/upload", response_model=DocumentOut)
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Document:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")

    stored_path = save_upload(file)
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
            chunk_index += 1

    vector_store.add_chunks(texts, metadatas, ids)
    document.chunk_count = len(texts)
    db.commit()
    db.refresh(document)
    return document


@app.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.uploaded_at.desc())))


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    if request.document_id:
        document = db.get(Document, request.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")
    raw_chunks = vector_store.query(request.query, document_id=request.document_id)
    masked_query = mask_pii(request.query)
    chunks = mask_chunks(raw_chunks)
    response = mask_pii(await generate_answer(masked_query, chunks))
    model = active_model_name()
    timestamp = datetime.utcnow()
    alerts = detect_alerts(db, request.user_id or "anonymous", masked_query, chunks, timestamp)
    sha_hash = generate_audit_hash(masked_query, response, chunks)

    log = AuditLog(
        user_id=request.user_id or "anonymous",
        query=masked_query,
        retrieved_chunks=json.dumps(chunks, ensure_ascii=False),
        response=response,
        model=model,
        sha256_hash=sha_hash,
        alerts=json.dumps(alerts, ensure_ascii=False),
        pii_masked="true",
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
    )


@app.get("/audit-logs", response_model=list[AuditLogOut])
def audit_logs(
    user_id: str | None = None,
    document_id: int | None = None,
    text: str | None = None,
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
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
        like = f"%{text}%"
        statement = statement.where(AuditLog.query.like(like) | AuditLog.response.like(like))

    rows = db.scalars(statement).all()
    output = []
    for row in rows:
        output.append(
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
                timestamp=row.timestamp,
                document_id=row.document_id,
                document_name=row.document.filename if row.document else None,
            )
        )
    return output


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
            "id",
            "user_id",
            "query",
            "response",
            "model",
            "sha256_hash",
            "alerts",
            "pii_masked",
            "timestamp",
            "document_id",
            "document_name",
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
