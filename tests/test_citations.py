from app.models.chunk import Chunk
from app.models.document import Document
from app.services.citation_formatter import RetrievedChunk, answer_has_strong_citation_support, build_source_context, select_citations_for_answer


def test_build_source_context_formats_labels_and_pages():
    document = Document(id=7, filename="source.pdf", content_type="application/pdf", content_hash="abc")
    chunk = Chunk(
        id=11,
        document_id=7,
        document_version_id=3,
        chunk_index=0,
        text="Revenue increased because enterprise customers expanded usage.",
        token_count=7,
        page_start=2,
        page_end=2,
        embedding=[0.0] * 1536,
        metadata_json={},
    )
    chunk.document = document

    context, citations = build_source_context([RetrievedChunk(chunk=chunk, score=0.9)])

    assert "[S1] source.pdf, page 2" in context
    assert citations[0]["label"] == "S1"
    assert citations[0]["chunk_id"] == 11
    assert citations[0]["page_start"] == 2
    assert citations[0]["score"] == 0.9


def test_select_citations_keeps_only_answer_referenced_sources():
    _, citations = build_source_context(
        [
            RetrievedChunk(
                chunk=Chunk(
                    id=11,
                    document_id=7,
                    document_version_id=3,
                    chunk_index=0,
                    text="First source.",
                    token_count=2,
                    page_start=1,
                    page_end=1,
                    embedding=[0.0] * 1536,
                    metadata_json={},
                ),
                score=0.9,
            ),
            RetrievedChunk(
                chunk=Chunk(
                    id=12,
                    document_id=7,
                    document_version_id=3,
                    chunk_index=1,
                    text="Second source.",
                    token_count=2,
                    page_start=2,
                    page_end=2,
                    embedding=[0.0] * 1536,
                    metadata_json={},
                ),
                score=0.8,
            ),
        ]
    )

    answer, selected = select_citations_for_answer("Use the second source [S2].", citations)

    assert answer == "Use the second source [S2]."
    assert [citation["label"] for citation in selected] == ["S2"]


def test_citation_score_filtering_rejects_weak_support():
    answer = "Revenue increased due to enterprise expansion [S1]."
    citations = [{"label": "S1", "score": 0.1}]

    assert answer_has_strong_citation_support(answer, citations, min_score=0.2) is False
