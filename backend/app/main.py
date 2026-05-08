import json
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import generate_audit_hash
from app.config import settings
from app.database import Base, engine, get_db
from app.llm import active_model_name, generate_answer
from app.models import AuditLog, Document
from app.pdf_loader import chunk_text, extract_pdf_pages, save_upload
from app.schemas import AuditLogOut, ChatRequest, ChatResponse, DocumentOut, VerifyOut
from app.vector_store import vector_store

settings.ensure_dirs()
Base.metadata.create_all(bind=engine)

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
    chunks = vector_store.query(request.query, document_id=request.document_id)
    response = await generate_answer(request.query, chunks)
    model = active_model_name()
    timestamp = datetime.utcnow()
    sha_hash = generate_audit_hash(request.query, response, chunks)

    log = AuditLog(
        user_id=request.user_id or "anonymous",
        query=request.query,
        retrieved_chunks=json.dumps(chunks, ensure_ascii=False),
        response=response,
        model=model,
        sha256_hash=sha_hash,
        timestamp=timestamp,
        document_id=request.document_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return ChatResponse(
        query=request.query,
        response=response,
        model=model,
        timestamp=timestamp,
        sha256_hash=sha_hash,
        retrieved_chunks=chunks,
        audit_log_id=log.id,
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
                timestamp=row.timestamp,
                document_id=row.document_id,
                document_name=row.document.filename if row.document else None,
            )
        )
    return output


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

