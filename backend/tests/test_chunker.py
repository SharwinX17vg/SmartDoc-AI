from app.document_processing.chunker import chunk_pages
from app.document_processing.pdf_extractor import PageText


def test_chunker_preserves_page_number():
    chunks = chunk_pages([PageText(page_number=3, text="alpha " * 300)], chunk_size=50, overlap=10)
    assert chunks
    assert all(chunk.page_number == 3 for chunk in chunks)
