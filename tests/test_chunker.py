from app.services.chunker import Chunker
from app.services.pdf_parser import ParsedPage


def test_chunker_creates_overlapping_page_aware_chunks():
    pages = [
        ParsedPage(page_number=1, text=" ".join(f"alpha{i}" for i in range(8))),
        ParsedPage(page_number=2, text=" ".join(f"beta{i}" for i in range(8))),
    ]

    chunks = Chunker(chunk_size=10, overlap=2).chunk_pages(pages)

    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert chunks[1].text.startswith("alpha6 alpha7")
    assert chunks[1].metadata["page_numbers"] == [1, 2]


def test_chunker_does_not_emit_overlap_only_duplicate():
    pages = [ParsedPage(page_number=1, text=" ".join(f"word{i}" for i in range(10)))]

    chunks = Chunker(chunk_size=10, overlap=3).chunk_pages(pages)

    assert len(chunks) == 1
