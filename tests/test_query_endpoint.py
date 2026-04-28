import pytest

from app.api import routes
from app.core.auth import AuthContext
from app.core.errors import ExternalServiceError
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.query import QueryRequest
from app.services.citation_formatter import RetrievedChunk
from app.services.llm_service import LLMResult
from app.services.retrieval_service import RetrievalTrace


class FakeRequest:
    class State:
        trace_id = "trace-test"

    state = State()


AUTH = AuthContext(user_id="user-1", groups=["default"], role="user")


class FakeDB:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False

    def add(self, item):
        self.added.append(item)

    def flush(self):
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = len(self.added)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class EmptyRetrievalService:
    def retrieve_with_trace(self, db, query, top_k=None, auth=None):
        return RetrievalTrace(
            results=[],
            trace={"rewritten_query": None, "retrieved_chunks": [], "reranked_chunks": []},
            metrics={"retrieval_latency_ms": 3, "embedding_latency_ms": 2},
        )


class FailingRetrievalService:
    def retrieve_with_trace(self, db, query, top_k=None, auth=None):
        raise ExternalServiceError("Embedding provider request failed")


class RelevantRetrievalService:
    def retrieve_with_trace(self, db, query, top_k=None, auth=None):
        document = Document(
            id=7,
            filename="source.pdf",
            content_type="application/pdf",
            content_hash="abc",
            owner_id="user-1",
            visibility="private",
            allowed_user_ids=["user-1"],
            allowed_group_ids=["default"],
        )
        chunk = Chunk(
            id=11,
            document_id=7,
            document_version_id=3,
            chunk_index=0,
            text="Revenue increased due to enterprise expansion.",
            token_count=6,
            page_start=2,
            page_end=2,
            embedding=[0.0] * 1536,
            metadata_json={},
        )
        chunk.document = document
        retrieved = [
            {
                "chunk_id": 11,
                "document_id": 7,
                "filename": "source.pdf",
                "page_start": 2,
                "page_end": 2,
                "score": 0.92,
                "source": "hybrid",
                "snippet": chunk.text,
            }
        ]
        return RetrievalTrace(
            results=[RetrievedChunk(chunk=chunk, score=0.92)],
            trace={"rewritten_query": None, "retrieved_chunks": retrieved, "fused_chunks": retrieved, "reranked_chunks": retrieved},
            metrics={"retrieval_latency_ms": 4, "embedding_latency_ms": 1},
        )


class FakeLLMService:
    def answer(self, question, source_context):
        assert "[S1]" in source_context
        return LLMResult(answer="Revenue increased due to enterprise expansion [S1].", total_tokens=42)


class UncitedLLMService:
    def answer(self, question, source_context):
        return LLMResult(answer="Revenue increased due to enterprise expansion.", total_tokens=30)


def test_query_returns_no_answer_when_retrieval_is_empty(monkeypatch):
    monkeypatch.setattr(routes, "retrieval_service", EmptyRetrievalService())
    db = FakeDB()

    response = routes.query(FakeRequest(), QueryRequest(question="What is missing?"), db=db, auth=AUTH)

    assert response.no_answer is True
    assert response.citations == []
    assert "could not find" in response.answer.lower()
    assert db.committed is True


def test_query_records_failure_when_embedding_fails(monkeypatch):
    monkeypatch.setattr(routes, "retrieval_service", FailingRetrievalService())
    db = FakeDB()

    with pytest.raises(ExternalServiceError):
        routes.query(FakeRequest(), QueryRequest(question="What is revenue?"), db=db, auth=AUTH)

    assert db.rolled_back is True
    assert db.committed is True
    assert db.added[-1].status == "failed"
    assert "Embedding provider" in db.added[-1].error_message


def test_query_logs_success_and_persists_referenced_citation(monkeypatch):
    monkeypatch.setattr(routes, "retrieval_service", RelevantRetrievalService())
    monkeypatch.setattr(routes, "llm_service", FakeLLMService())
    db = FakeDB()

    response = routes.query(FakeRequest(), QueryRequest(question="Why did revenue increase?"), db=db, auth=AUTH)

    assert response.no_answer is False
    assert response.citations[0].label == "S1"
    assert response.citations[0].filename == "source.pdf"
    assert db.committed is True
    assert any(getattr(item, "status", None) == "completed" for item in db.added)
    query_log = next(item for item in db.added if getattr(item, "status", None) == "completed")
    assert query_log.metrics_json["retrieval_latency_ms"] == 4
    assert query_log.metrics_json["embedding_latency_ms"] == 1
    assert query_log.metrics_json["llm_latency_ms"] >= 0
    assert query_log.metrics_json["no_answer"] is False
    assert query_log.user_id == "user-1"
    assert query_log.groups == ["default"]
    assert query_log.auth_role == "user"


def test_query_returns_no_answer_when_answer_has_uncited_claim(monkeypatch):
    monkeypatch.setattr(routes, "retrieval_service", RelevantRetrievalService())
    monkeypatch.setattr(routes, "llm_service", UncitedLLMService())
    db = FakeDB()

    response = routes.query(FakeRequest(), QueryRequest(question="Why did revenue increase?"), db=db, auth=AUTH)

    assert response.no_answer is True
    assert response.citations == []
    assert "could not find" in response.answer.lower()
