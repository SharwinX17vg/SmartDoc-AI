import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from ..document_processing.chunker import DocumentChunk
from .embeddings import TfidfEmbeddingModel


logger = logging.getLogger(__name__)


class LocalHybridIndex:
    """Small persisted index used behind a replaceable vector-store boundary."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.embedding_model = TfidfEmbeddingModel()
        self.document_name = ""
        self.document_id = ""
        self.chunks: list[DocumentChunk] = []
        self.matrix = None
        self.documents: dict[str, dict] = {}
        self._load()

    def add_document(
        self,
        document_name: str,
        chunks: list[DocumentChunk],
        document_id: str | None = None,
        size_bytes: int = 0,
    ) -> str:
        if not chunks:
            raise ValueError("The PDF did not contain extractable text")
        document_id = document_id or str(uuid4())
        self.documents[document_id] = {
            "document_id": document_id,
            "document_name": document_name,
            "page_count": len({chunk.page_number for chunk in chunks}),
            "chunk_count": len(chunks),
            "size_bytes": size_bytes,
            "chunks": chunks,
        }
        self._rebuild()
        self._save()
        return document_id

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_ids: list[str] | None = None,
        candidates: int = 15,
        min_score: float = 0.0,
    ) -> list[tuple[DocumentChunk, float]]:
        if not self.chunks or self.matrix is None:
            return []
        query_vector = self.embedding_model.transform([query])
        semantic_scores = (self.matrix @ query_vector.T).toarray().ravel()
        terms = set(re.findall(r"[a-z0-9][a-z0-9'-]*", query.lower()))
        allowed = set(document_ids) if document_ids else None
        results = []
        for index, chunk in enumerate(self.chunks):
            if allowed is not None and chunk.document_id not in allowed:
                continue
            words = set(re.findall(r"[a-z0-9][a-z0-9'-]*", chunk.text.lower()))
            keyword_score = len(terms & words) / max(len(terms), 1)
            combined_score = (0.7 * float(semantic_scores[index])) + (0.3 * keyword_score)
            if combined_score >= min_score:
                results.append((chunk, combined_score))
        ranked = sorted(results, key=lambda item: item[1], reverse=True)[: max(candidates, top_k)]
        deduped: list[tuple[DocumentChunk, float]] = []
        seen: set[str] = set()
        for chunk, score in ranked:
            normalized = " ".join(chunk.text.lower().split())
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append((chunk, score))
        return deduped[:top_k]

    def remove_document(self, document_id: str) -> bool:
        removed = self.documents.pop(document_id, None) is not None
        if removed:
            self._rebuild()
            self._save()
        return removed

    def clear(self) -> None:
        self.documents.clear()
        self._rebuild()
        self._save()

    def summaries(self) -> list[dict]:
        return [
            {key: value for key, value in document.items() if key != "chunks"}
            for document in self.documents.values()
        ]

    def _rebuild(self) -> None:
        self.chunks = [chunk for document in self.documents.values() for chunk in document["chunks"]]
        self.document_id = self.chunks[0].document_id if self.chunks else ""
        self.document_name = self.chunks[0].document_name if self.chunks else ""
        self.matrix = self.embedding_model.fit_transform([chunk.text for chunk in self.chunks]) if self.chunks else None

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(
                {
                    "document_name": self.document_name,
                    "documents": [
                        {
                            **{key: value for key, value in document.items() if key != "chunks"},
                            "chunks": [asdict(chunk) for chunk in document["chunks"]],
                        }
                        for document in self.documents.values()
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
            documents = payload.get("documents", [])
            if not documents and payload.get("chunks"):
                legacy_name = payload.get("document_name", "document.pdf")
                legacy_id = "legacy-document"
                legacy_chunks = [
                    DocumentChunk(
                        chunk_id=chunk["chunk_id"],
                        document_id=chunk.get("document_id", legacy_id),
                        document_name=chunk.get("document_name", legacy_name),
                        page_number=chunk["page_number"],
                        section_title=chunk.get("section_title"),
                        text=chunk["text"],
                    )
                    for chunk in payload["chunks"]
                ]
                if legacy_chunks:
                    documents = [{
                        "document_id": legacy_chunks[0].document_id,
                        "document_name": payload.get("document_name", legacy_chunks[0].document_name),
                        "page_count": len({chunk.page_number for chunk in legacy_chunks}),
                        "chunks": [asdict(chunk) for chunk in legacy_chunks],
                    }]
            for document in documents:
                chunks = [DocumentChunk(**chunk) for chunk in document.get("chunks", [])]
                if chunks:
                    self.documents[document["document_id"]] = {
                        "document_id": document["document_id"],
                        "document_name": document["document_name"],
                        "page_count": document.get("page_count", len({chunk.page_number for chunk in chunks})),
                        "chunk_count": len(chunks),
                        "size_bytes": document.get("size_bytes", 0),
                        "chunks": chunks,
                    }
            self._rebuild()
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            logger.warning("Could not load persisted document index; starting empty: %s", error)
            self.documents.clear()
