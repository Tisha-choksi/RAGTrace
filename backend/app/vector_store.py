import threading
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import settings

_lock = threading.Lock()
_instance: "VectorStore | None" = None


class VectorStore:
    def __init__(self) -> None:
        if settings.chroma_server_host:
            self.client = chromadb.HttpClient(
                host=settings.chroma_server_host,
                port=settings.chroma_server_port,
            )
        else:
            self.client = chromadb.PersistentClient(path=settings.chroma_dir)
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
        self.collection = self.client.get_or_create_collection(
            name="rag_documents",
            embedding_function=embedding_fn,
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
