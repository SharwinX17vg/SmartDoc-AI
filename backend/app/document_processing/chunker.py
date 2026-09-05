from dataclasses import dataclass

from .pdf_extractor import PageText


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int
    section_title: str | None
    text: str


def chunk_pages(
    pages: list[PageText],
    chunk_size: int = 900,
    overlap: int = 120,
    document_id: str = "document",
    document_name: str = "document.pdf",
) -> list[DocumentChunk]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks: list[DocumentChunk] = []
    for page in pages:
        start = 0
        chunk_number = 0
        while start < len(page.text):
            end = min(start + chunk_size, len(page.text))
            text = page.text[start:end].strip()
            if text:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"p{page.page_number}-c{chunk_number}",
                        document_id=document_id,
                        document_name=document_name,
                        page_number=page.page_number,
                        section_title=_section_title(page.text[:start]),
                        text=text,
                    )
                )
            if end == len(page.text):
                break
            start = end - overlap
            chunk_number += 1
    return chunks


def _section_title(prefix: str) -> str | None:
    lines = [line.strip() for line in prefix.splitlines() if line.strip()]
    if not lines:
        return None
    candidate = lines[-1]
    return candidate if len(candidate) <= 100 and len(candidate.split()) <= 12 else None
