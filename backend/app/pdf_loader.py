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
    with target.open("wb") as out:
        out.write(file.file.read())
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
