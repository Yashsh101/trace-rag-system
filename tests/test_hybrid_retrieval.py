from app.services.citation_formatter import RetrievedChunk
from app.services.reranker import NoOpReranker
from app.services.retrieval_service import RetrievalService
import inspect


class FakeChunk:
    def __init__(self, chunk_id, text):
        self.id = chunk_id
        self.text = text
        self.document_id = 1
        self.document_version_id = 1
        self.page_start = 1
        self.page_end = 1


class HybridTestRetrievalService(RetrievalService):
    def __init__(self, vector_results, keyword_results):
        super().__init__(embedding_service=None, reranker=NoOpReranker())
        self.vector_results = vector_results
        self.keyword_results = keyword_results

    def _vector_search(self, db, query, limit, auth=None, metrics=None):
        return self.vector_results

    def _keyword_search(self, db, query, limit, auth=None):
        return self.keyword_results


class KeywordFailingRetrievalService(HybridTestRetrievalService):
    def _keyword_search(self, db, query, limit, auth=None):
        raise RuntimeError("keyword failure")


def test_hybrid_search_fusion_prefers_result_seen_by_both_paths():
    shared = FakeChunk(1, "shared revenue expansion")
    vector_only = FakeChunk(2, "semantic revenue")
    keyword_only = FakeChunk(3, "exact contract")
    service = RetrievalService(embedding_service=None, reranker=NoOpReranker())

    fused = service._weighted_rrf(
        [
            RetrievedChunk(shared, score=0.9, source="vector"),
            RetrievedChunk(vector_only, score=0.8, source="vector"),
        ],
        [
            RetrievedChunk(shared, score=1.0, source="keyword"),
            RetrievedChunk(keyword_only, score=0.7, source="keyword"),
        ],
    )

    assert fused[0].chunk.id == 1
    assert fused[0].source == "keyword+vector"


def test_keyword_only_match_is_returned_when_vector_has_no_hits():
    keyword_chunk = FakeChunk(3, "force majeure exact clause")
    service = HybridTestRetrievalService(
        vector_results=[],
        keyword_results=[RetrievedChunk(keyword_chunk, score=1.0, source="keyword")],
    )

    results = service.retrieve(db=None, query="force majeure", top_k=3)

    assert [result.chunk.id for result in results] == [3]
    assert results[0].source == "keyword"


def test_vector_fallback_when_hybrid_keyword_path_fails():
    vector_chunk = FakeChunk(2, "semantic fallback")
    service = KeywordFailingRetrievalService(
        vector_results=[RetrievedChunk(vector_chunk, score=0.9, source="vector")],
        keyword_results=[],
    )

    results = service.retrieve(db=None, query="semantic fallback", top_k=3)

    assert [result.chunk.id for result in results] == [2]
    assert results[0].source == "vector"


def test_keyword_retrieval_uses_indexed_search_vector():
    source = inspect.getsource(RetrievalService._keyword_search)

    assert "Chunk.search_vector" in source
    assert "to_tsvector" not in source
