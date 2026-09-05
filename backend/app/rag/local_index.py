import json
from dataclasses import asdict
from pathlib import Path

from ..document_processing.chunker import DocumentChunk
from .embeddings import TfidfEmbeddingModel


class LocalHybridIndex:
    """Small persisted index used behind a replaceable vector-store boundary."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.embedding_model = TfidfEmbeddingModel()
        self.document_name = ""
        self.chunks: list[DocumentChunk] = []
        self.matrix = None

    def add_document(self, document_name: str, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            raise ValueError("The PDF did not contain extractable text")
        self.document_name = document_name
        self.chunks = chunks
        self.matrix = self.embedding_model.fit_transform([chunk.text for chunk in chunks])
        self._save()

    def search(self, query: str, top_k: int = 5) -> list[tuple[DocumentChunk, float]]:
        if not self.chunks or self.matrix is None:
            return []
        query_vector = self.embedding_model.transform([query])
        semantic_scores = (self.matrix @ query_vector.T).toarray().ravel()
        terms = {term.lower() for term in query.split() if term.strip()}
        results = []
        for index, chunk in enumerate(self.chunks):
            words = set(chunk.text.lower().split())
            keyword_score = len(terms & words) / max(len(terms), 1)
            combined_score = (0.7 * float(semantic_scores[index])) + (0.3 * keyword_score)
            results.append((chunk, combined_score))
        return sorted(results, key=lambda item: item[1], reverse=True)[:top_k]

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(
                {
                    "document_name": self.document_name,
                    "chunks": [asdict(chunk) for chunk in self.chunks],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
