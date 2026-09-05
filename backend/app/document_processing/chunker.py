from dataclasses import dataclass

from .pdf_extractor import PageText


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    page_number: int
    text: str


def chunk_pages(pages: list[PageText], chunk_size: int = 900, overlap: int = 120) -> list[DocumentChunk]:
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
                        page_number=page.page_number,
                        text=text,
                    )
                )
            if end == len(page.text):
                break
            start = end - overlap
            chunk_number += 1
    return chunks
