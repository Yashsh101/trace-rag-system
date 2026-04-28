from app.services.citation_formatter import RetrievedChunk
from app.services.reranker import LocalReranker


class FakeChunk:
    def __init__(self, chunk_id, text):
        self.id = chunk_id
        self.text = text


def test_local_reranker_promotes_lexically_relevant_chunk():
    weak_vector_match = RetrievedChunk(FakeChunk(1, "general company overview"), score=0.7, source="vector")
    lexical_match = RetrievedChunk(FakeChunk(2, "revenue expansion enterprise customers"), score=0.5, source="keyword")

    reranked = LocalReranker().rerank("revenue expansion", [weak_vector_match, lexical_match], top_k=2)

    assert reranked[0].chunk.id == 2
    assert reranked[0].score > reranked[1].score

