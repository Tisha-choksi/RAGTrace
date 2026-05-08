# AI Audit Trail Middleware for RAG Systems

MVP implementation for a document-grounded chat system that records every retrieval and answer in an auditable trail.

## Features

- Upload PDF documents
- Ask questions against uploaded documents
- Retrieve source chunks from ChromaDB
- Store query, retrieved chunks, response, timestamp, model, user, and document filters
- Generate SHA256 verification hashes for each audit record
- Search audit history by user, document, date, or text
- Dashboard for sources, timestamps, hashes, and responses

## Stack

- Backend: FastAPI
- RAG: ChromaDB with sentence-transformer embeddings
- AI: OpenAI, Gemini, or local extractive fallback
- Database: SQLite
- Frontend: React + Vite + Tailwind

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Set either `OPENAI_API_KEY` or `GEMINI_API_KEY` in `backend/.env` to use a hosted model. Without keys, the app still works in local demo mode using retrieved chunks to produce an extractive answer.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## API Overview

- `POST /documents/upload` uploads a PDF and indexes it
- `GET /documents` lists uploaded documents
- `POST /chat` asks a RAG question and writes an audit log
- `GET /audit-logs` searches audit history
- `GET /audit-logs/{id}/verify` recomputes and verifies the SHA256 hash
- `GET /health` returns service status

