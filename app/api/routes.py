import logging
import time
import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.core.auth import AuthContext, require_auth
from app.core.config import settings
from app.core.errors import AppError, NotFoundError, ValidationAppError
from app.db.session import get_db
from app.models.citation import Citation
from app.models.document import IngestionJob
from app.models.query_log import QueryLog
from app.schemas.document import DocumentIngestResponse, IngestionJobResponse
from app.schemas.health import HealthResponse
from app.schemas.query import CitationResponse, QueryRequest, QueryResponse
from app.services.citation_formatter import answer_has_strong_citation_support, build_source_context, select_citations_for_answer
from app.services.access_control import filter_retrieved_chunks
from app.services.ingestion_job_service import IngestionJobService
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService
from app.services.observability import LangfuseTracer, QueryObservation, estimate_cost
from app.services.readiness import readiness_check
from app.services.retrieval_service import RetrievalService

router = APIRouter()
ingestion_service = IngestionService()
ingestion_job_service = IngestionJobService(ingestion_service=ingestion_service)
retrieval_service = RetrievalService()
llm_service = LLMService()
tracer = LangfuseTracer()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict:
    result = readiness_check(db)
    if not result["ready"]:
        return {"status": "not_ready", **result}
    return {"status": "ready", **result}


@router.post("/documents/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> DocumentIngestResponse:
    content = await _read_upload_file_limited(file)
    job = ingestion_job_service.create_job(
        db=db,
        filename=file.filename or "uploaded.pdf",
        content_type=file.content_type or "application/pdf",
        content=content,
        trace_id=getattr(request.state, "trace_id", None),
        owner_id=auth.user_id,
        visibility="private",
        allowed_user_ids=[auth.user_id],
        allowed_group_ids=auth.groups,
    )
    logger.info(
        "ingestion_job_queued",
        extra={"event": "ingestion_job_queued", "trace_id": getattr(request.state, "trace_id", None)},
    )
    return DocumentIngestResponse(
        job_id=job.id,
        document_id=job.document_id or 0,
        document_version_id=job.document_version_id,
        filename=job.filename,
        chunk_count=job.chunk_count,
        status=job.status,
    )


@router.get("/ingestion-jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(
    job_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> IngestionJobResponse:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise NotFoundError("Ingestion job not found")
    if not auth.is_admin and job.owner_id != auth.user_id:
        raise NotFoundError("Ingestion job not found")
    return IngestionJobResponse(
        job_id=job.id,
        status=job.status,
        document_id=job.document_id,
        error_message=job.error_message,
        chunk_count=job.chunk_count,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failed_at=job.failed_at,
    )


@router.post("/query", response_model=QueryResponse)
def query(
    request: Request,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> QueryResponse:
    trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex)
    started = time.perf_counter()

    try:
        retrieval_result = retrieval_service.retrieve_with_trace(db=db, query=payload.question, top_k=payload.top_k, auth=auth)
        results, denied_retrieval_count = filter_retrieved_chunks(retrieval_result.results, auth)
        if not results:
            answer = "I could not find this in the uploaded documents."
            metrics = _build_metrics(
                started=started,
                retrieval_metrics=retrieval_result.metrics,
                llm_latency_ms=0,
                prompt_tokens=None,
                completion_tokens=None,
                empty_retrieval=True,
                no_answer=True,
                citation_failure=False,
            )
            validation = {"support_ok": False, "reason": "empty_retrieval"}
            query_log = QueryLog(
                trace_id=trace_id,
                query=payload.question,
                answer=answer,
                retrieved_chunk_ids=[],
                latency_ms=_elapsed_ms(started),
                model=settings.openai_chat_model,
                trace_json={**retrieval_result.trace, "retrieved_chunks": [], "reranked_chunks": []},
                metrics_json=metrics,
                validation_json=validation,
                user_id=auth.user_id,
                groups=auth.groups,
                auth_role=auth.role,
                denied_retrieval_count=denied_retrieval_count,
                status="no_answer",
            )
            db.add(query_log)
            db.flush()
            query_log_id = query_log.id
            db.commit()
            _trace_query(
                trace_id=trace_id,
                query=payload.question,
                answer=answer,
                retrieved_chunks=[],
                citations=[],
                metrics=metrics,
                validation=validation,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
            )
            return QueryResponse(trace_id=trace_id, query_log_id=query_log_id, answer=answer, citations=[], no_answer=True)

        source_context, citation_payloads = build_source_context(results, max_chars=settings.max_context_chars)
        llm_started = time.perf_counter()
        llm_result = llm_service.answer(question=payload.question, source_context=source_context)
        llm_latency_ms = _elapsed_ms(llm_started)
        answer, selected_citation_payloads = select_citations_for_answer(llm_result.answer, citation_payloads)
        support_ok = answer_has_strong_citation_support(answer, selected_citation_payloads, min_score=settings.min_citation_score)
        no_answer = "could not find" in answer.lower() or not support_ok
        if not support_ok:
            answer = "I could not find this in the uploaded documents."
            selected_citation_payloads = []
        validation = {
            "support_ok": support_ok,
            "reason": "ok" if support_ok else "weak_or_missing_citation_support",
            "min_citation_score": settings.min_citation_score,
        }
        metrics = _build_metrics(
            started=started,
            retrieval_metrics=retrieval_result.metrics,
            llm_latency_ms=llm_latency_ms,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            empty_retrieval=False,
            no_answer=no_answer,
            citation_failure=not support_ok,
        )

        query_log = QueryLog(
            trace_id=trace_id,
            query=payload.question,
            answer=answer,
            retrieved_chunk_ids=[result.chunk.id for result in results],
            latency_ms=_elapsed_ms(started),
            model=settings.openai_chat_model,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
            trace_json={
                **retrieval_result.trace,
                "retrieved_chunks": _results_to_trace(results),
                "reranked_chunks": _results_to_trace(results),
                "final_citations": selected_citation_payloads,
            },
            metrics_json=metrics,
            validation_json=validation,
            user_id=auth.user_id,
            groups=auth.groups,
            auth_role=auth.role,
            denied_retrieval_count=denied_retrieval_count,
            status="no_answer" if no_answer else "completed",
        )
        db.add(query_log)
        db.flush()

        citations: list[CitationResponse] = []
        if not no_answer:
            for citation_payload in selected_citation_payloads:
                db.add(
                    Citation(
                        query_log_id=query_log.id,
                        chunk_id=citation_payload["chunk_id"],
                        citation_label=citation_payload["label"],
                        source_filename=citation_payload["filename"],
                        page_start=citation_payload["page_start"],
                        page_end=citation_payload["page_end"],
                        score=citation_payload["score"],
                        snippet=citation_payload["snippet"],
                    )
                )
                citations.append(CitationResponse(**citation_payload))

        db.commit()
        _trace_query(
            trace_id=trace_id,
            query=payload.question,
            answer=answer,
            retrieved_chunks=retrieval_result.trace.get("reranked_chunks", []),
            citations=selected_citation_payloads,
            metrics=metrics,
            validation=validation,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
        )
        logger.info(
            "query_completed",
            extra={
                "event": "query_completed",
                "trace_id": trace_id,
                "latency_ms": _elapsed_ms(started),
                "model": settings.openai_chat_model,
                "total_tokens": llm_result.total_tokens,
            },
        )
        return QueryResponse(trace_id=trace_id, query_log_id=query_log.id, answer=answer, citations=citations, no_answer=no_answer)
    except AppError as exc:
        db.rollback()
        _record_failed_query(db, trace_id, payload.question, started, exc.message, auth=auth)
        logger.warning(
            "query_failed",
            extra={"event": "query_failed", "trace_id": trace_id, "user_id": auth.user_id, "auth_role": auth.role},
        )
        raise


@router.get("/query/{query_log_id}/trace")
def get_query_trace(
    query_log_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> dict:
    query_log = db.get(QueryLog, query_log_id, options=[joinedload(QueryLog.citations)])
    if query_log is None:
        raise NotFoundError("Query log not found")
    if not auth.is_admin and query_log.user_id != auth.user_id:
        raise NotFoundError("Query log not found")

    trace_payload = query_log.trace_json or {}
    return {
        "query_log_id": query_log.id,
        "trace_id": query_log.trace_id,
        "original_query": query_log.query,
        "rewritten_query": trace_payload.get("rewritten_query"),
        "retrieved_chunks": trace_payload.get("retrieved_chunks", []),
        "reranked_chunks": trace_payload.get("reranked_chunks", []),
        "final_citations": [_citation_to_dict(citation) for citation in query_log.citations],
        "validation_result": query_log.validation_json or {},
        "model_usage": {
            "model": query_log.model,
            "prompt_tokens": query_log.prompt_tokens,
            "completion_tokens": query_log.completion_tokens,
            "total_tokens": query_log.total_tokens,
            "estimated_cost": (query_log.metrics_json or {}).get("estimated_cost"),
        },
        "metrics": query_log.metrics_json or {},
        "answer": query_log.answer,
        "status": query_log.status,
        "auth": {"user_id": query_log.user_id, "groups": query_log.groups, "role": query_log.auth_role},
        "denied_retrieval_count": query_log.denied_retrieval_count,
    }


async def _read_upload_file_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(settings.upload_read_chunk_bytes)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise ValidationAppError(f"File exceeds max upload size of {settings.max_upload_mb} MB")
        chunks.append(chunk)
    return b"".join(chunks)


def _record_failed_query(
    db: Session,
    trace_id: str,
    question: str,
    started: float,
    error_message: str,
    auth: AuthContext | None = None,
) -> None:
    try:
        metrics = _build_metrics(
            started=started,
            retrieval_metrics={},
            llm_latency_ms=0,
            prompt_tokens=None,
            completion_tokens=None,
            empty_retrieval=False,
            no_answer=False,
            citation_failure=False,
        )
        db.add(
            QueryLog(
                trace_id=trace_id,
                query=question,
                answer=None,
                retrieved_chunk_ids=[],
                latency_ms=_elapsed_ms(started),
                model=settings.openai_chat_model,
                trace_json={},
                metrics_json=metrics,
                validation_json={"support_ok": False, "reason": "query_failed"},
                user_id=auth.user_id if auth else None,
                groups=auth.groups if auth else [],
                auth_role=auth.role if auth else None,
                denied_retrieval_count=0,
                status="failed",
                error_message=error_message,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed_to_record_query_failure", extra={"event": "failed_to_record_query_failure", "trace_id": trace_id})


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _build_metrics(
    started: float,
    retrieval_metrics: dict,
    llm_latency_ms: int,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    empty_retrieval: bool,
    no_answer: bool,
    citation_failure: bool,
) -> dict:
    return {
        "query_latency_ms": _elapsed_ms(started),
        "retrieval_latency_ms": retrieval_metrics.get("retrieval_latency_ms", 0),
        "embedding_latency_ms": retrieval_metrics.get("embedding_latency_ms", 0),
        "llm_latency_ms": llm_latency_ms,
        "empty_retrieval": empty_retrieval,
        "no_answer": no_answer,
        "citation_failure": citation_failure,
        "estimated_cost": estimate_cost(prompt_tokens, completion_tokens),
    }


def _trace_query(
    trace_id: str,
    query: str,
    answer: str | None,
    retrieved_chunks: list[dict],
    citations: list[dict],
    metrics: dict,
    validation: dict,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
) -> None:
    tracer.trace_query(
        QueryObservation(
            trace_id=trace_id,
            query=query,
            answer=answer,
            retrieved_chunks=retrieved_chunks,
            citations=citations,
            metrics=metrics,
            validation=validation,
            model_usage={
                "model": settings.openai_chat_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": metrics.get("estimated_cost"),
            },
        )
    )


def _citation_to_dict(citation: Citation) -> dict:
    return {
        "label": citation.citation_label,
        "chunk_id": citation.chunk_id,
        "filename": citation.source_filename,
        "page_start": citation.page_start,
        "page_end": citation.page_end,
        "score": citation.score,
        "snippet": citation.snippet,
    }


def _results_to_trace(results) -> list[dict]:
    payload = []
    for result in results:
        chunk = result.chunk
        payload.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "filename": chunk.document.filename if getattr(chunk, "document", None) else None,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "score": round(result.score, 4),
                "source": result.source,
                "snippet": chunk.text[:500],
            }
        )
    return payload
from app.core.auth import AuthContext, require_auth
