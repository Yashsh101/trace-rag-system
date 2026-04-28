import sys
from types import SimpleNamespace

from app.core.config import settings
from app.services.observability import LangfuseTracer, QueryObservation, estimate_cost


def test_tracing_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_enabled", False)

    tracer = LangfuseTracer()
    tracer.trace_query(
        QueryObservation(
            trace_id="trace-disabled",
            query="question",
            answer="answer",
            retrieved_chunks=[],
            citations=[],
            metrics={},
            validation={},
            model_usage={},
        )
    )

    assert tracer.enabled is False
    assert tracer.client is None


def test_tracing_enabled_uses_langfuse_client_mock(monkeypatch):
    calls = []

    class FakeTrace:
        def span(self, **kwargs):
            calls.append(("span", kwargs))

    class FakeLangfuse:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def trace(self, **kwargs):
            calls.append(("trace", kwargs))
            return FakeTrace()

        def flush(self):
            calls.append(("flush", {}))

    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(Langfuse=FakeLangfuse))
    monkeypatch.setattr(settings, "langfuse_enabled", True)
    monkeypatch.setattr(settings, "langfuse_public_key", "pk")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk")

    tracer = LangfuseTracer()
    tracer.trace_query(
        QueryObservation(
            trace_id="trace-enabled",
            query="question",
            answer="answer",
            retrieved_chunks=[{"chunk_id": 1, "score": 0.9}],
            citations=[{"label": "S1"}],
            metrics={"retrieval_latency_ms": 5},
            validation={"support_ok": True},
            model_usage={"total_tokens": 10},
        )
    )

    assert ("trace", next(payload for name, payload in calls if name == "trace")) in calls
    assert any(name == "span" for name, _ in calls)
    assert any(name == "flush" for name, _ in calls)


def test_estimate_cost_uses_configured_rates(monkeypatch):
    monkeypatch.setattr(settings, "estimated_input_cost_per_1m_tokens", 2.0)
    monkeypatch.setattr(settings, "estimated_output_cost_per_1m_tokens", 10.0)

    assert estimate_cost(1_000_000, 500_000) == 7.0

