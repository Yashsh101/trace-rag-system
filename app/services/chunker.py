from dataclasses import dataclass
import re

from app.core.config import settings
from app.services.pdf_parser import ParsedPage
from app.utils.text import count_tokens_approx, normalize_text

CHUNKER_VERSION = "paragraph-aware-token-window-v2"
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    token_count: int
    page_start: int | None
    page_end: int | None
    metadata: dict


class Chunker:
    def __init__(self, chunk_size: int | None = None, overlap: int | None = None):
        self.chunk_size = chunk_size or settings.chunk_size_tokens
        self.overlap = overlap if overlap is not None else settings.chunk_overlap_tokens
        if self.overlap >= self.chunk_size:
            raise ValueError("chunk overlap must be smaller than chunk size")

    def chunk_pages(self, pages: list[ParsedPage]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        current: list[tuple[str, int]] = []

        def flush(force: bool = False) -> None:
            nonlocal current
            if not current:
                return
            if chunks and not force and len(current) <= self.overlap:
                return

            words = [word for word, _ in current]
            pages_for_words = [page for _, page in current]
            text = normalize_text(" ".join(words))
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    text=text,
                    token_count=count_tokens_approx(text),
                    page_start=min(pages_for_words) if pages_for_words else None,
                    page_end=max(pages_for_words) if pages_for_words else None,
                    metadata={"page_numbers": sorted(set(pages_for_words))},
                )
            )

            if self.overlap > 0:
                current = current[-self.overlap :]
            else:
                current = []

        for page in pages:
            paragraphs = [part.strip() for part in PARAGRAPH_SPLIT_RE.split(page.text) if part.strip()]
            for paragraph in paragraphs:
                for word in paragraph.split():
                    current.append((word, page.page_number))
                    if len(current) >= self.chunk_size:
                        flush()

                if len(current) >= int(self.chunk_size * 0.75):
                    flush()

        if current and (not chunks or len(current) > self.overlap):
            flush(force=True)

        return chunks
