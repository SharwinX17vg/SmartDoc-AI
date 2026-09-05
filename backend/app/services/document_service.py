import os
from uuid import uuid4

from ..document_processing.chunker import chunk_pages
from ..document_processing.pdf_extractor import extract_pdf_pages
from ..models.schemas import DocumentSummary, UploadResponse
from ..rag.local_index import LocalHybridIndex


class DocumentService:
    def __init__(self, index: LocalHybridIndex) -> None:
        self.index = index
        self.document_id: str | None = None
        self.max_documents = int(os.getenv("MAX_DOCUMENTS_PER_SESSION", "10"))
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE_MB", "25")) * 1024 * 1024
        self.max_total_size = int(os.getenv("MAX_TOTAL_UPLOAD_SIZE_MB", "100")) * 1024 * 1024
        self.document_sizes: dict[str, int] = {}

    def ingest(self, filename: str, pdf_bytes: bytes) -> UploadResponse:
        if len(pdf_bytes) > self.max_file_size:
            raise ValueError(f"PDF exceeds the {self.max_file_size // 1024 // 1024} MB file limit")
        if len(self.index.documents) >= self.max_documents:
            raise ValueError("The document workspace has reached its document limit")
        if self._total_size() + len(pdf_bytes) > self.max_total_size:
            raise ValueError("The document workspace has reached its total upload limit")
        pages = extract_pdf_pages(pdf_bytes)
        document_id = str(uuid4())
        chunks = chunk_pages(pages, document_id=document_id, document_name=filename)
        self.index.add_document(filename, chunks, document_id=document_id, size_bytes=len(pdf_bytes))
        self.document_sizes[document_id] = len(pdf_bytes)
        self.document_id = document_id
        return UploadResponse(
            document_id=self.document_id,
            document_name=filename,
            page_count=len(pages),
            chunk_count=len(chunks),
        )

    def list_documents(self) -> list[DocumentSummary]:
        return [DocumentSummary(**summary) for summary in self.index.summaries()]

    def remove(self, document_id: str) -> bool:
        removed = self.index.remove_document(document_id)
        self.document_sizes.pop(document_id, None)
        return removed

    def clear(self) -> None:
        self.index.clear()
        self.document_sizes.clear()

    def _total_size(self) -> int:
        persisted_sizes = sum(document.get("size_bytes", 0) for document in self.index.documents.values())
        return max(persisted_sizes, sum(self.document_sizes.values()))
