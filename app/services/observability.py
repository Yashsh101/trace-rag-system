import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryObservation:
    trace_id: str
    query: str
    answer: str | None
    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    metrics: dict[str, Any]
    validation: dict[str, Any]
    model_usage: dict[str, Any]


class LangfuseTracer:
    def __init__(self):
        self.enabled = settings.langfuse_enabled
        self.client = None
        if not self.enabled:
            return
        try:
            from langfuse import Langfuse

            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        except Exception:
            self.enabled = False
            logger.exception("langfuse_initialization_failed", extra={"event": "langfuse_initialization_failed"})

    def trace_query(self, observation: QueryObservation) -> None:
        if not self.enabled or self.client is None:
            return
        try:
            trace = self.client.trace(
                id=observation.trace_id,
                name="rag_query",
                input=observation.query,
                output=observation.answer,
                metadata={
                    "metrics": observation.metrics,
                    "validation": observation.validation,
                    "model_usage": observation.model_usage,
                    "citations": observation.citations,
                },
            )
            if hasattr(trace, "span"):
                trace.span(
                    name="retrieval",
                    input=observation.query,
                    output=observation.retrieved_chunks,
                    metadata={"latency_ms": observation.metrics.get("retrieval_latency_ms")},
                )
            if hasattr(self.client, "flush"):
                self.client.flush()
        except Exception:
            logger.exception("langfuse_trace_failed", extra={"event": "langfuse_trace_failed", "trace_id": observation.trace_id})


def estimate_cost(prompt_tokens: int | None, completion_tokens: int | None) -> float:
    input_tokens = prompt_tokens or 0
    output_tokens = completion_tokens or 0
    return round(
        (input_tokens / 1_000_000 * settings.estimated_input_cost_per_1m_tokens)
        + (output_tokens / 1_000_000 * settings.estimated_output_cost_per_1m_tokens),
        8,
    )

