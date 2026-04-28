from datetime import datetime, timezone

import pytest

from app.api.routes import get_ingestion_job
from app.core.auth import AuthContext
from app.core.errors import NotFoundError, ValidationAppError
from app.models.document import IngestionJob
from app.services.ingestion_job_service import IngestionJobService


class FakeDocument:
    id = 10
    raw_file_uri = "local://raw/test.pdf"
    storage_backend = "local"
    content_hash = "abc123"
    file_size_bytes = 9


class FakeVersion:
    id = 20
    parsed_text_uri = "local://parsed/test.txt"


class SuccessfulIngestionService:
    storage_backend = None

    def ingest_pdf_with_acl(
        self,
        db,
        filename,
        content_type,
        content,
        owner_id=None,
        visibility="private",
        allowed_user_ids=None,
        allowed_group_ids=None,
        raw_file_uri=None,
    ):
        return FakeDocument(), FakeVersion(), 3


class FailingIngestionService:
    storage_backend = None

    def ingest_pdf_with_acl(
        self,
        db,
        filename,
        content_type,
        content,
        owner_id=None,
        visibility="private",
        allowed_user_ids=None,
        allowed_group_ids=None,
        raw_file_uri=None,
    ):
        raise ValidationAppError("Uploaded file does not look like a PDF")


class FakeStorage:
    name = "local"

    def put_bytes(self, key, content, content_type=None):
        return f"local://fake/{key}"

    def get_bytes(self, uri):
        return b"%PDF-fake"


class JobCreationIngestionService:
    storage_backend = FakeStorage()


SuccessfulIngestionService.storage_backend = FakeStorage()
FailingIngestionService.storage_backend = FakeStorage()


class FakeDB:
    def __init__(self, job=None):
        self.job = job
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.refreshed = False
        self.closed = False

    def add(self, item):
        self.added.append(item)
        self.job = item

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, item):
        self.refreshed = True

    def get(self, model, job_id):
        if self.job is not None and self.job.id == job_id:
            return self.job
        return None

    class Query:
        def __init__(self, job):
            self.job = job

        def filter(self, *args):
            return self

        def all(self):
            return [self.job] if self.job is not None else []

        def order_by(self, *args):
            return self

        def with_for_update(self, **kwargs):
            return self

        def first(self):
            return self.job

    def query(self, model):
        return self.Query(self.job)

    def close(self):
        self.closed = True


def make_job(status="queued"):
    return IngestionJob(
        id="job-1",
        trace_id="trace-1",
        filename="test.pdf",
        content_type="application/pdf",
        raw_file_uri="local://fake/raw/test.pdf",
        content_hash="abc123",
        file_size_bytes=9,
        status=status,
        owner_id="user-1",
        visibility="private",
        allowed_user_ids=["user-1"],
        allowed_group_ids=["default"],
        chunk_count=0,
        retry_count=0,
        max_retries=3,
        created_at=datetime.now(timezone.utc),
    )


def test_ingestion_job_creation():
    db = FakeDB()
    service = IngestionJobService(ingestion_service=JobCreationIngestionService())

    job = service.create_job(db, "test.pdf", "application/pdf", b"%PDF-fake", "trace-1")

    assert job.id
    assert job.status == "queued"
    assert job.trace_id == "trace-1"
    assert job.content_hash
    assert job.file_size_bytes == len(b"%PDF-fake")
    assert job.raw_file_uri.startswith("local://fake/raw/")
    assert not hasattr(job, "content")
    assert db.committed is True
    assert db.refreshed is True


def test_successful_job_completion(monkeypatch):
    job = make_job()
    db = FakeDB(job)
    monkeypatch.setattr("app.services.ingestion_job_service.SessionLocal", lambda: db)
    service = IngestionJobService(ingestion_service=SuccessfulIngestionService())

    service.process_job("job-1")

    assert job.status == "completed"
    assert job.document_id == 10
    assert job.document_version_id == 20
    assert job.chunk_count == 3
    assert job.content_hash is not None
    assert job.started_at is not None
    assert job.completed_at is not None
    assert db.closed is True


def test_failed_pdf_ingestion_persists_error(monkeypatch):
    job = make_job()
    job.max_retries = 1
    db = FakeDB(job)
    monkeypatch.setattr("app.services.ingestion_job_service.SessionLocal", lambda: db)
    service = IngestionJobService(ingestion_service=FailingIngestionService())

    service.process_job("job-1")

    assert job.status == "failed"
    assert "does not look like a PDF" in job.error_message
    assert job.failed_at is not None
    assert db.rolled_back is True


def test_failed_job_retries_until_limit(monkeypatch):
    job = make_job()
    job.max_retries = 2
    db = FakeDB(job)
    monkeypatch.setattr("app.services.ingestion_job_service.SessionLocal", lambda: db)
    service = IngestionJobService(ingestion_service=FailingIngestionService())

    service.process_job("job-1")

    assert job.status == "queued"
    assert job.retry_count == 1
    assert job.failed_at is None


def test_stale_processing_job_recovery():
    job = make_job(status="processing")
    job.locked_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    db = FakeDB(job)

    recovered = IngestionJobService(ingestion_service=SuccessfulIngestionService()).recover_stale_jobs(db, stale_after_seconds=1)

    assert recovered == 1
    assert job.status == "queued"
    assert job.locked_at is None


def test_job_status_endpoint_returns_status_payload():
    job = make_job(status="completed")
    job.document_id = 10
    job.chunk_count = 3
    job.completed_at = datetime.now(timezone.utc)

    response = get_ingestion_job("job-1", db=FakeDB(job), auth=AuthContext(user_id="user-1", groups=["default"], role="user"))

    assert response.job_id == "job-1"
    assert response.status == "completed"
    assert response.document_id == 10
    assert response.chunk_count == 3


def test_job_status_endpoint_404_for_missing_job():
    with pytest.raises(NotFoundError):
        get_ingestion_job("missing", db=FakeDB(), auth=AuthContext(user_id="user-1", groups=["default"], role="user"))
