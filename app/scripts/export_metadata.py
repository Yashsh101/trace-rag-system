import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.chunk import Chunk
from app.models.document import Document, IngestionJob
from app.models.query_log import QueryLog


def main() -> None:
    parser = argparse.ArgumentParser(description="Export RAG metadata tables to JSONL")
    parser.add_argument("--out-dir", default="exports", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        _export(out_dir / "documents.jsonl", db.scalars(select(Document)).all(), _document_to_dict)
        _export(out_dir / "chunks_metadata.jsonl", db.scalars(select(Chunk)).all(), _chunk_to_dict)
        _export(out_dir / "ingestion_jobs.jsonl", db.scalars(select(IngestionJob)).all(), _job_to_dict)
        _export(out_dir / "query_logs.jsonl", db.scalars(select(QueryLog)).all(), _query_log_to_dict)
    finally:
        db.close()


def _export(path: Path, rows: list[Any], serializer) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(serializer(row), default=_json_default) + "\n")
    print(f"exported {len(rows)} rows to {path}")


def _document_to_dict(document: Document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "content_hash": document.content_hash,
        "raw_file_uri": document.raw_file_uri,
        "storage_backend": document.storage_backend,
        "file_size_bytes": document.file_size_bytes,
        "owner_id": document.owner_id,
        "visibility": document.visibility,
        "allowed_user_ids": document.allowed_user_ids,
        "allowed_group_ids": document.allowed_group_ids,
        "created_at": document.created_at,
    }


def _chunk_to_dict(chunk: Chunk) -> dict:
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "document_version_id": chunk.document_version_id,
        "chunk_index": chunk.chunk_index,
        "token_count": chunk.token_count,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "section_path": chunk.section_path,
        "metadata_json": chunk.metadata_json,
        "created_at": chunk.created_at,
    }


def _job_to_dict(job: IngestionJob) -> dict:
    return {
        "id": job.id,
        "trace_id": job.trace_id,
        "filename": job.filename,
        "content_type": job.content_type,
        "status": job.status,
        "document_id": job.document_id,
        "document_version_id": job.document_version_id,
        "raw_file_uri": job.raw_file_uri,
        "parsed_text_uri": job.parsed_text_uri,
        "storage_backend": job.storage_backend,
        "content_hash": job.content_hash,
        "file_size_bytes": job.file_size_bytes,
        "owner_id": job.owner_id,
        "visibility": job.visibility,
        "allowed_user_ids": job.allowed_user_ids,
        "allowed_group_ids": job.allowed_group_ids,
        "chunk_count": job.chunk_count,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "failed_at": job.failed_at,
    }


def _query_log_to_dict(query_log: QueryLog) -> dict:
    return {
        "id": query_log.id,
        "trace_id": query_log.trace_id,
        "query": query_log.query,
        "answer": query_log.answer,
        "retrieved_chunk_ids": query_log.retrieved_chunk_ids,
        "latency_ms": query_log.latency_ms,
        "model": query_log.model,
        "prompt_tokens": query_log.prompt_tokens,
        "completion_tokens": query_log.completion_tokens,
        "total_tokens": query_log.total_tokens,
        "status": query_log.status,
        "user_id": query_log.user_id,
        "groups": query_log.groups,
        "auth_role": query_log.auth_role,
        "denied_retrieval_count": query_log.denied_retrieval_count,
        "error_message": query_log.error_message,
        "metrics_json": query_log.metrics_json,
        "validation_json": query_log.validation_json,
        "created_at": query_log.created_at,
    }


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


if __name__ == "__main__":
    main()
