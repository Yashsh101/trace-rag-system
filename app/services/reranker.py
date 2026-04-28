import re
from abc import ABC, abstractmethod

from app.core.config import settings
from app.services.citation_formatter import RetrievedChunk

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, results: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        raise NotImplementedError


class NoOpReranker(Reranker):
    def rerank(self, query: str, results: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        return results[:top_k]


class LocalReranker(Reranker):
    def rerank(self, query: str, results: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        query_terms = _tokens(query)
        if not query_terms:
            return results[:top_k]

        lexical_weight = settings.local_reranker_lexical_weight
        semantic_weight = 1.0 - lexical_weight

        scored: list[RetrievedChunk] = []
        for result in results:
            text_terms = _tokens(result.chunk.text)
            lexical_score = len(query_terms & text_terms) / max(1, len(query_terms))
            phrase_bonus = 0.05 if query.lower() in result.chunk.text.lower() else 0.0
            rerank_score = min(1.0, (semantic_weight * result.score) + (lexical_weight * lexical_score) + phrase_bonus)
            scored.append(RetrievedChunk(chunk=result.chunk, score=rerank_score, source=f"{result.source}+rerank"))

        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]


def build_reranker() -> Reranker:
    if not settings.reranking_enabled or settings.reranker_provider == "none":
        return NoOpReranker()
    return LocalReranker()


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}

