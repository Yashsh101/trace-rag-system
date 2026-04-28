from app.api.routes import get_query_trace
from app.core.auth import AuthContext
from app.models.citation import Citation
from app.models.query_log import QueryLog


class FakeDB:
    def __init__(self, query_log):
        self.query_log = query_log

    def get(self, model, query_log_id, options=None):
        assert model is QueryLog
        assert query_log_id == self.query_log.id
        return self.query_log


def test_query_trace_endpoint_returns_debug_payload():
    query_log = QueryLog(
        id=123,
        trace_id="trace-123",
        query="What changed?",
        answer="It changed [S1].",
        retrieved_chunk_ids=[11],
        latency_ms=50,
        model="gpt-test",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        trace_json={
            "rewritten_query": None,
            "retrieved_chunks": [{"chunk_id": 11, "score": 0.9}],
            "reranked_chunks": [{"chunk_id": 11, "score": 0.95}],
        },
        metrics_json={"query_latency_ms": 50, "estimated_cost": 0.01},
        validation_json={"support_ok": True},
        status="completed",
    )
    query_log.citations = [
        Citation(
            citation_label="S1",
            chunk_id=11,
            source_filename="source.pdf",
            page_start=2,
            page_end=2,
            score=0.95,
            snippet="It changed.",
        )
    ]

    query_log.user_id = "user-1"
    query_log.groups = ["default"]
    query_log.auth_role = "user"
    query_log.denied_retrieval_count = 0

    response = get_query_trace(123, db=FakeDB(query_log), auth=AuthContext(user_id="user-1", groups=["default"], role="user"))

    assert response["original_query"] == "What changed?"
    assert response["retrieved_chunks"][0]["chunk_id"] == 11
    assert response["reranked_chunks"][0]["score"] == 0.95
    assert response["final_citations"][0]["chunk_id"] == 11
    assert response["validation_result"]["support_ok"] is True
    assert response["model_usage"]["total_tokens"] == 15
    assert response["auth"]["user_id"] == "user-1"
