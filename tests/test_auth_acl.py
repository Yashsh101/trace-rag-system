import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.core.auth import AuthContext, require_auth
from app.core.config import settings
from app.core.errors import AuthenticationError
from app.main import app
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.query import QueryRequest
from app.services.access_control import can_access_document, filter_retrieved_chunks
from app.services.citation_formatter import RetrievedChunk
from app.services.retrieval_service import RetrievalTrace


def test_missing_api_key_is_rejected():
    with pytest.raises(AuthenticationError, match="Missing X-API-Key"):
        require_auth(None)


def test_invalid_api_key_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_keys", "admin-key")
    monkeypatch.setattr(settings, "user_api_keys", "user-key:user-1:default")

    with pytest.raises(AuthenticationError, match="Invalid API key"):
        require_auth("wrong-key")


def test_missing_api_key_http_response():
    response = TestClient(app).post("/api/v1/query", json={"question": "What is in the docs?"})

    assert response.status_code == 401


def test_admin_access_private_document():
    document = Document(
        id=1,
        filename="private.pdf",
        content_type="application/pdf",
        content_hash="abc",
        owner_id="user-1",
        visibility="private",
        allowed_user_ids=[],
        allowed_group_ids=[],
    )

    assert can_access_document(document, AuthContext(user_id="admin", groups=["admin"], role="admin")) is True


def test_private_document_access_for_owner():
    document = Document(
        id=1,
        filename="private.pdf",
        content_type="application/pdf",
        content_hash="abc",
        owner_id="user-1",
        visibility="private",
        allowed_user_ids=[],
        allowed_group_ids=[],
    )

    assert can_access_document(document, AuthContext(user_id="user-1", groups=[], role="user")) is True


def test_blocked_unauthorized_retrieval_is_filtered():
    document = Document(
        id=1,
        filename="private.pdf",
        content_type="application/pdf",
        content_hash="abc",
        owner_id="owner",
        visibility="private",
        allowed_user_ids=[],
        allowed_group_ids=[],
    )
    chunk = Chunk(
        id=10,
        document_id=1,
        document_version_id=1,
        chunk_index=0,
        text="secret",
        token_count=1,
        embedding=[0.0] * 1536,
        metadata_json={},
    )
    chunk.document = document

    allowed, denied = filter_retrieved_chunks(
        [RetrievedChunk(chunk=chunk, score=0.9)],
        AuthContext(user_id="user-2", groups=[], role="user"),
    )

    assert allowed == []
    assert denied == 1


def test_public_document_retrieval_allowed():
    document = Document(
        id=1,
        filename="public.pdf",
        content_type="application/pdf",
        content_hash="abc",
        owner_id="owner",
        visibility="public",
        allowed_user_ids=[],
        allowed_group_ids=[],
    )

    assert can_access_document(document, AuthContext(user_id="anyone", groups=[], role="user")) is True


class UnauthorizedRetrievalService:
    def retrieve_with_trace(self, db, query, top_k=None, auth=None):
        document = Document(
            id=1,
            filename="secret.pdf",
            content_type="application/pdf",
            content_hash="abc",
            owner_id="owner",
            visibility="private",
            allowed_user_ids=[],
            allowed_group_ids=[],
        )
        chunk = Chunk(
            id=10,
            document_id=1,
            document_version_id=1,
            chunk_index=0,
            text="secret",
            token_count=1,
            embedding=[0.0] * 1536,
            metadata_json={},
        )
        chunk.document = document
        return RetrievalTrace(
            results=[RetrievedChunk(chunk=chunk, score=0.9)],
            trace={"rewritten_query": None, "retrieved_chunks": [{"chunk_id": 10}], "reranked_chunks": [{"chunk_id": 10}]},
            metrics={"retrieval_latency_ms": 1, "embedding_latency_ms": 1},
        )


class FakeDB:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, item):
        self.added.append(item)

    def flush(self):
        for index, item in enumerate(self.added, start=1):
            if getattr(item, "id", None) is None:
                item.id = index

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


class FakeRequest:
    class State:
        trace_id = "trace-acl"

    state = State()


def test_query_denies_unauthorized_retrieval(monkeypatch):
    monkeypatch.setattr(routes, "retrieval_service", UnauthorizedRetrievalService())
    db = FakeDB()

    response = routes.query(
        FakeRequest(),
        QueryRequest(question="What is secret?"),
        db=db,
        auth=AuthContext(user_id="user-2", groups=[], role="user"),
    )

    assert response.no_answer is True
    query_log = db.added[-1]
    assert query_log.denied_retrieval_count == 1
    assert query_log.user_id == "user-2"
