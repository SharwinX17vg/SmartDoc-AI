from pathlib import Path
from uuid import uuid4

from ..document_processing.chunker import chunk_pages
from ..document_processing.pdf_extractor import extract_pdf_pages
from ..models.schemas import UploadResponse
from ..rag.local_index import LocalHybridIndex


class DocumentService:
    def __init__(self, index: LocalHybridIndex) -> None:
        self.index = index
        self.document_id: str | None = None

    def ingest(self, filename: str, pdf_bytes: bytes) -> UploadResponse:
        pages = extract_pdf_pages(pdf_bytes)
        chunks = chunk_pages(pages)
        self.index.add_document(filename, chunks)
        self.document_id = str(uuid4())
        return UploadResponse(
            document_id=self.document_id,
            document_name=filename,
            page_count=len(pages),
            chunk_count=len(chunks),
        )
