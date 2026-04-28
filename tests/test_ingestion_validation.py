import pytest

from app.core.errors import ExternalServiceError, ValidationAppError
from app.services.ingestion_service import IngestionService
from app.services.pdf_parser import ParsedPage


class FakeDB:
    def __init__(self):
        self.rolled_back = False

    class Result:
        def scalar_one_or_none(self):
            return None

    def execute(self, statement):
        return self.Result()

    def rollback(self):
        self.rolled_back = True


class FakeParser:
    def parse(self, content):
        return [ParsedPage(page_number=1, text="This PDF has extractable text.")]


class FailingEmbeddingService:
    def embed_texts(self, texts):
        raise ExternalServiceError("Embedding provider request failed")


class FakeStorage:
    name = "local"

    def __init__(self):
        self.writes = []

    def put_bytes(self, key, content, content_type=None):
        self.writes.append((key, content, content_type))
        return f"local://fake/{key}"


class SuccessfulEmbeddingService:
    def embed_texts(self, texts):
        return [[0.1] * 1536 for _ in texts]


class PersistingFakeDB(FakeDB):
    def __init__(self):
        super().__init__()
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, item):
        if getattr(item, "id", None) is None:
            item.id = len(self.added) + 1
        self.added.append(item)

    def flush(self):
        pass

    def commit(self):
        self.committed = True

    def refresh(self, item):
        self.refreshed.append(item)


class OwnerAwareFakeDB(PersistingFakeDB):
    class Result:
        def __init__(self, statement):
            self.statement = statement

        def scalar_one_or_none(self):
            assert "documents.owner_id" in str(self.statement)
            return None

    def execute(self, statement):
        return self.Result(statement)


def test_ingestion_rejects_bad_pdf_bytes():
    db = FakeDB()

    with pytest.raises(ValidationAppError, match="does not look like a PDF"):
        IngestionService().ingest_pdf(db, "bad.pdf", "application/pdf", b"not a pdf")

    assert db.rolled_back is True


def test_ingestion_rejects_empty_pdf():
    db = FakeDB()

    with pytest.raises(ValidationAppError, match="empty"):
        IngestionService().ingest_pdf(db, "empty.pdf", "application/pdf", b"")

    assert db.rolled_back is True


def test_ingestion_rolls_back_when_embedding_fails():
    db = FakeDB()
    service = IngestionService(parser=FakeParser(), embedding_service=FailingEmbeddingService())

    with pytest.raises(ExternalServiceError):
        service.ingest_pdf(db, "ok.pdf", "application/pdf", b"%PDF-fake")

    assert db.rolled_back is True


def test_ingestion_persists_artifact_uris():
    db = PersistingFakeDB()
    storage = FakeStorage()
    service = IngestionService(parser=FakeParser(), embedding_service=SuccessfulEmbeddingService(), storage_backend=storage)

    document, version, chunk_count = service.ingest_pdf(db, "ok.pdf", "application/pdf", b"%PDF-fake")

    assert document.raw_file_uri.startswith("local://fake/raw/")
    assert version.parsed_text_uri.startswith("local://fake/parsed/")
    assert document.storage_backend == "local"
    assert document.file_size_bytes == len(b"%PDF-fake")
    assert chunk_count == 1
    assert db.committed is True
    assert len(storage.writes) == 2


def test_duplicate_uploads_by_different_users_create_distinct_owner_records():
    storage = FakeStorage()
    service = IngestionService(parser=FakeParser(), embedding_service=SuccessfulEmbeddingService(), storage_backend=storage)

    doc_a, _, _ = service.ingest_pdf_with_acl(
        OwnerAwareFakeDB(),
        "same.pdf",
        "application/pdf",
        b"%PDF-same",
        owner_id="user-a",
        allowed_user_ids=["user-a"],
    )
    doc_b, _, _ = service.ingest_pdf_with_acl(
        OwnerAwareFakeDB(),
        "same.pdf",
        "application/pdf",
        b"%PDF-same",
        owner_id="user-b",
        allowed_user_ids=["user-b"],
    )

    assert doc_a.content_hash == doc_b.content_hash
    assert doc_a.owner_id == "user-a"
    assert doc_b.owner_id == "user-b"
