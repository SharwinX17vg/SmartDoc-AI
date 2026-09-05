from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


def extract_pdf_pages(pdf_bytes: bytes) -> list[PageText]:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except (PdfReadError, OSError) as error:
        raise ValueError("the PDF could not be read") from error
    pages: list[PageText] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = _clean_text(page.extract_text() or "")
        if text:
            pages.append(PageText(page_number=page_number, text=text))
    return pages


def _clean_text(text: str) -> str:
    return "\n".join(
        line.strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        if line.strip()
    ).strip()
