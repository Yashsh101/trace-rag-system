import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.document import IngestionJob
from app.services.ingestion_service import IngestionService
from app.utils.hash import sha256_bytes

logger = logging.getLogger(__name__)


class IngestionJobService:
    def __init__(self, ingestion_service: IngestionService | None = None):
        self.ingestion_service = ingestion_service or IngestionService()

    def create_job(
        self,
        db: Session,
        filename: str,
        content_type: str,
        content: bytes,
        trace_id: str | None,
        owner_id: str | None = None,
        visibility: str = "private",
        allowed_user_ids: list[str] | None = None,
        allowed_group_ids: list[str] | None = None,
    ) -> IngestionJob:
        content_hash = sha256_bytes(content)
        raw_file_uri = self.ingestion_service.storage_backend.put_bytes(
            key=f"raw/{content_hash}/{filename}",
            content=content,
            content_type=content_type,
        )
        job = IngestionJob(
            id=uuid.uuid4().hex,
            trace_id=trace_id,
            filename=filename,
            content_type=content_type,
            raw_file_uri=raw_file_uri,
            content_hash=content_hash,
            file_size_bytes=len(content),
            storage_backend=self.ingestion_service.storage_backend.name,
            owner_id=owner_id,
            visibility=visibility,
            allowed_user_ids=allowed_user_ids or [],
            allowed_group_ids=allowed_group_ids or [],
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def process_job(self, job_id: str, worker_id: str | None = None) -> None:
        worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        db = SessionLocal()
        try:
            job = db.get(IngestionJob, job_id)
            if job is None:
                logger.error("ingestion_job_missing", extra={"event": "ingestion_job_missing"})
                return

            job.status = "processing"
            job.started_at = _utcnow()
            job.last_attempt_at = _utcnow()
            job.locked_at = _utcnow()
            job.locked_by = worker_id
            db.commit()

            try:
                if not job.raw_file_uri:
                    raise ValueError("Ingestion job is missing raw_file_uri")
                content = self.ingestion_service.storage_backend.get_bytes(job.raw_file_uri)
                document, version, chunk_count = self.ingestion_service.ingest_pdf_with_acl(
                    db=db,
                    filename=job.filename,
                    content_type=job.content_type,
                    content=content,
                    owner_id=job.owner_id,
                    visibility=job.visibility,
                    allowed_user_ids=job.allowed_user_ids,
                    allowed_group_ids=job.allowed_group_ids,
                    raw_file_uri=job.raw_file_uri,
                )
                job = db.get(IngestionJob, job_id)
                if job is None:
                    return
                job.status = "completed"
                job.document_id = document.id
                job.document_version_id = version.id
                job.chunk_count = chunk_count
                job.raw_file_uri = document.raw_file_uri
                job.parsed_text_uri = version.parsed_text_uri
                job.storage_backend = document.storage_backend
                job.content_hash = document.content_hash
                job.file_size_bytes = document.file_size_bytes
                job.completed_at = _utcnow()
                job.locked_at = None
                job.locked_by = None
                db.commit()
                logger.info("ingestion_job_completed", extra={"event": "ingestion_job_completed", "trace_id": job.trace_id})
            except Exception as exc:
                db.rollback()
                failed_job = db.get(IngestionJob, job_id)
                if failed_job is not None:
                    failed_job.retry_count = (failed_job.retry_count or 0) + 1
                    max_retries = failed_job.max_retries or 3
                    failed_job.status = "failed" if failed_job.retry_count >= max_retries else "queued"
                    failed_job.error_message = str(exc)
                    failed_job.failed_at = _utcnow() if failed_job.status == "failed" else None
                    failed_job.locked_at = None
                    failed_job.locked_by = None
                    db.commit()
                    logger.exception(
                        "ingestion_job_failed",
                        extra={"event": "ingestion_job_failed", "trace_id": failed_job.trace_id},
                    )
        finally:
            db.close()

    def recover_stale_jobs(self, db: Session, stale_after_seconds: int = 900) -> int:
        cutoff = _utcnow() - timedelta(seconds=stale_after_seconds)
        jobs = (
            db.query(IngestionJob)
            .filter(IngestionJob.status == "processing", IngestionJob.locked_at.is_not(None), IngestionJob.locked_at < cutoff)
            .all()
        )
        for job in jobs:
            retry_count = job.retry_count or 0
            max_retries = job.max_retries or 3
            job.status = "queued" if retry_count < max_retries else "failed"
            job.error_message = "Recovered stale processing job"
            job.locked_at = None
            job.locked_by = None
            if job.status == "failed":
                job.failed_at = _utcnow()
        db.commit()
        return len(jobs)

    def claim_next_job(self, db: Session, worker_id: str) -> IngestionJob | None:
        job = (
            db.query(IngestionJob)
            .filter(IngestionJob.status == "queued", IngestionJob.retry_count < IngestionJob.max_retries)
            .order_by(IngestionJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if job is None:
            return None
        job.status = "processing"
        job.started_at = job.started_at or _utcnow()
        job.last_attempt_at = _utcnow()
        job.locked_at = _utcnow()
        job.locked_by = worker_id
        db.commit()
        return job


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
