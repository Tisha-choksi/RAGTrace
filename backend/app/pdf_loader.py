from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import settings


def save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"
    stored_name = f"{uuid4().hex}{suffix}"
    target = Path(settings.upload_dir) / stored_name
    max_bytes = settings.max_upload_mb * 1024 * 1024
    total = 0
    with target.open("wb") as out:
        while True:
            chunk = file.file.read(65_536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                target.unlink(missing_ok=True)
                raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit.")
            out.write(chunk)
    return target


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        clean = " ".join(text.split())
        if clean:
            pages.append((index, clean))
    return pages


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]
