from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader

from app.core.errors import ValidationAppError
from app.utils.text import normalize_text

PARSER_VERSION = "pypdf-5.1.0-v1"


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str


class PDFParser:
    def parse(self, content: bytes) -> list[ParsedPage]:
        if not content:
            raise ValidationAppError("Uploaded PDF is empty")
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise ValidationAppError("Uploaded file is not a readable PDF") from exc

        pages: list[ParsedPage] = []
        for idx, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            if text:
                pages.append(ParsedPage(page_number=idx, text=text))

        if not pages:
            raise ValidationAppError("No extractable text found in PDF. OCR is planned for a later phase.")

        return pages
