from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_rate_limiter_rejects_when_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests", 0)

    response = TestClient(app).post("/api/v1/query", headers={"X-API-Key": "anything"}, json={"question": "hello?"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limit_exceeded"


def test_health_endpoint_includes_trace_id_header():
    response = TestClient(app).get("/api/v1/health", headers={"X-Trace-ID": "trace-release"})

    assert response.status_code == 200
    assert response.headers["x-trace-id"] == "trace-release"

