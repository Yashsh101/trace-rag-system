import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.auth import AuthContext
from app.core.config import settings
from app.db.types import is_sqlite_url
from app.core.errors import ValidationAppError
from app.models.chunk import Chunk
from app.models.document import Document, DocumentVersion
from app.services.access_control import can_access_document, document_acl_filter
from app.services.citation_formatter import RetrievedChunk
from app.services.embedding_service import EmbeddingService
from app.services.reranker import Reranker, build_reranker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievalTrace:
    results: list[RetrievedChunk]
    trace: dict[str, Any]
    metrics: dict[str, int]


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        reranker: Reranker | None = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.reranker = reranker or build_reranker()

    def retrieve(self, db: Session, query: str, top_k: int | None = None, auth: AuthContext | None = None) -> list[RetrievedChunk]:
        return self.retrieve_with_trace(db=db, query=query, top_k=top_k, auth=auth).results

    def retrieve_with_trace(self, db: Session, query: str, top_k: int | None = None, auth: AuthContext | None = None) -> RetrievalTrace:
        query = query.strip()
        if not query:
            raise ValidationAppError("Query cannot be empty")
        auth = auth or AuthContext(user_id="system", groups=["admin"], role="admin")

        started = time.perf_counter()
        metrics = {"embedding_latency_ms": 0, "retrieval_latency_ms": 0}
        limit = top_k or settings.retrieval_top_k
        if settings.retrieval_mode == "vector":
            vector_results = self._vector_search(db, query, limit, auth, metrics)
            reranked = self._rerank(query, vector_results, limit)
            metrics["retrieval_latency_ms"] = _elapsed_ms(started)
            return RetrievalTrace(
                results=reranked,
                trace={
                    "rewritten_query": None,
                    "retrieval_mode": "vector",
                    "vector_chunks": _serialize_results(vector_results),
                    "keyword_chunks": [],
                    "fused_chunks": _serialize_results(vector_results),
                    "reranked_chunks": _serialize_results(reranked),
                },
                metrics=metrics,
            )

        try:
            vector_results = self._vector_search(db, query, limit * settings.hybrid_candidate_multiplier, auth, metrics)
            keyword_results = self._keyword_search(db, query, limit * settings.hybrid_candidate_multiplier, auth)
            fused = self._weighted_rrf(vector_results, keyword_results)
            filtered = [result for result in fused if result.score >= settings.min_retrieval_score]
            if filtered:
                reranked = self._rerank(query, filtered, limit)
                metrics["retrieval_latency_ms"] = _elapsed_ms(started)
                return RetrievalTrace(
                    results=reranked,
                    trace={
                        "rewritten_query": None,
                        "retrieval_mode": "hybrid",
                        "vector_chunks": _serialize_results(vector_results),
                        "keyword_chunks": _serialize_results(keyword_results),
                        "fused_chunks": _serialize_results(filtered),
                        "reranked_chunks": _serialize_results(reranked),
                    },
                    metrics=metrics,
                )
        except Exception:
            logger.exception("hybrid_search_failed_falling_back_to_vector", extra={"event": "hybrid_search_failed_falling_back_to_vector"})

        vector_results = self._vector_search(db, query, limit, auth, metrics)
        reranked = self._rerank(query, vector_results, limit)
        metrics["retrieval_latency_ms"] = _elapsed_ms(started)
        return RetrievalTrace(
            results=reranked,
            trace={
                "rewritten_query": None,
                "retrieval_mode": "vector_fallback",
                "vector_chunks": _serialize_results(vector_results),
                "keyword_chunks": [],
                "fused_chunks": _serialize_results(vector_results),
                "reranked_chunks": _serialize_results(reranked),
            },
            metrics=metrics,
        )

    def _vector_search(
        self,
        db: Session,
        query: str,
        limit: int,
        auth: AuthContext | None = None,
        metrics: dict[str, int] | None = None,
    ) -> list[RetrievedChunk]:
        auth = auth or AuthContext(user_id="system", groups=["admin"], role="admin")
        embedding_started = time.perf_counter()
        query_embedding = self.embedding_service.embed_query(query)
        if metrics is not None:
            metrics["embedding_latency_ms"] = metrics.get("embedding_latency_ms", 0) + _elapsed_ms(embedding_started)
        if _is_sqlite_session(db):
            return self._sqlite_vector_search(db, query_embedding, limit, auth)

        distance = Chunk.embedding.cosine_distance(query_embedding)

        rows = db.execute(
            select(Chunk, distance.label("distance"))
            .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(DocumentVersion.active.is_(True), DocumentVersion.status == "completed")
            .where(document_acl_filter(auth))
            .options(joinedload(Chunk.document))
            .order_by(distance)
            .limit(limit)
        ).all()

        results: list[RetrievedChunk] = []
        for chunk, raw_distance in rows:
            score = max(0.0, min(1.0, 1.0 - float(raw_distance)))
            if score >= settings.min_retrieval_score:
                results.append(RetrievedChunk(chunk=chunk, score=score, source="vector"))
        return results

    def _keyword_search(self, db: Session, query: str, limit: int, auth: AuthContext | None = None) -> list[RetrievedChunk]:
        auth = auth or AuthContext(user_id="system", groups=["admin"], role="admin")
        if _is_sqlite_session(db):
            return self._sqlite_keyword_search(db, query, limit, auth)

        ts_query = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(Chunk.search_vector, ts_query)

        rows = db.execute(
            select(Chunk, rank.label("rank"))
            .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(DocumentVersion.active.is_(True), DocumentVersion.status == "completed", Chunk.search_vector.op("@@")(ts_query))
            .where(document_acl_filter(auth))
            .options(joinedload(Chunk.document))
            .order_by(rank.desc())
            .limit(limit)
        ).all()

        max_rank = max((float(raw_rank) for _, raw_rank in rows), default=0.0)
        if max_rank <= 0:
            return []

        return [
            RetrievedChunk(chunk=chunk, score=max(0.0, min(1.0, float(raw_rank) / max_rank)), source="keyword")
            for chunk, raw_rank in rows
        ]

    def _sqlite_vector_search(self, db: Session, query_embedding: list[float], limit: int, auth: AuthContext) -> list[RetrievedChunk]:
        chunks = self._sqlite_accessible_chunks(db, auth)
        scored = [
            RetrievedChunk(chunk=chunk, score=max(0.0, min(1.0, _cosine_similarity(query_embedding, chunk.embedding))), source="vector")
            for chunk in chunks
        ]
        return [result for result in sorted(scored, key=lambda item: item.score, reverse=True)[:limit] if result.score >= settings.min_retrieval_score]

    def _sqlite_keyword_search(self, db: Session, query: str, limit: int, auth: AuthContext) -> list[RetrievedChunk]:
        query_terms = _tokens(query)
        if not query_terms:
            return []
        scored: list[RetrievedChunk] = []
        for chunk in self._sqlite_accessible_chunks(db, auth):
            text_terms = _tokens(chunk.text)
            score = len(query_terms & text_terms) / max(1, len(query_terms))
            if score > 0:
                scored.append(RetrievedChunk(chunk=chunk, score=score, source="keyword"))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

    def _sqlite_accessible_chunks(self, db: Session, auth: AuthContext) -> list[Chunk]:
        rows = db.execute(
            select(Chunk)
            .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(DocumentVersion.active.is_(True), DocumentVersion.status == "completed")
            .options(joinedload(Chunk.document))
        ).scalars()
        return [chunk for chunk in rows if can_access_document(chunk.document, auth)]

    def _weighted_rrf(
        self,
        vector_results: list[RetrievedChunk],
        keyword_results: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        fused: dict[int, dict] = {}
        self._add_rrf_scores(fused, vector_results, weight=settings.vector_search_weight, source="vector")
        self._add_rrf_scores(fused, keyword_results, weight=settings.keyword_search_weight, source="keyword")

        results = [
            RetrievedChunk(chunk=item["chunk"], score=min(1.0, item["score"]), source="+".join(sorted(item["sources"])))
            for item in fused.values()
        ]
        return sorted(results, key=lambda item: item.score, reverse=True)

    def _add_rrf_scores(self, fused: dict[int, dict], results: list[RetrievedChunk], weight: float, source: str) -> None:
        for rank, result in enumerate(results, start=1):
            chunk_id = result.chunk.id
            if chunk_id is None:
                continue
            item = fused.setdefault(chunk_id, {"chunk": result.chunk, "score": 0.0, "sources": set()})
            rrf_component = weight * ((settings.hybrid_rrf_k + 1) / (settings.hybrid_rrf_k + rank))
            item["score"] += rrf_component
            item["sources"].add(source)

    def _rerank(self, query: str, results: list[RetrievedChunk], limit: int) -> list[RetrievedChunk]:
        if not results:
            return []
        return self.reranker.rerank(query, results[: settings.rerank_top_k], top_k=limit)


def _serialize_results(results: list[RetrievedChunk]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
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


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _is_sqlite_session(db: Session) -> bool:
    bind = db.get_bind()
    return bind.dialect.name == "sqlite" or is_sqlite_url(str(bind.url))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", text)}
