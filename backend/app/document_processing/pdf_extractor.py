from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


def extract_pdf_pages(pdf_bytes: bytes) -> list[PageText]:
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[PageText] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(PageText(page_number=page_number, text=text))
    return pages
