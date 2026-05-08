from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import settings


class VectorStore:
    def __init__(self) -> None:
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


vector_store = VectorStore()

