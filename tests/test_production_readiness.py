import pytest

from app.core.config import Settings
from app.core.rate_limit import RedisRateLimiter
from app.services.readiness import readiness_check


def test_production_config_requires_admin_keys():
    with pytest.raises(ValueError, match="ADMIN_API_KEYS"):
        Settings(
            app_env="production",
            **{"openai_api_key": "test-openai-key"},
            user_api_keys="user-real:user-1:default",
            cors_allowed_origins="https://rag.example.com",
            storage_backend="s3",
            s3_bucket="bucket",
            rate_limit_backend="redis",
            redis_url="redis://localhost:6379/0",
        )


def test_production_config_rejects_wildcard_cors():
    with pytest.raises(ValueError, match="Strict CORS"):
        Settings(
            app_env="production",
            **{"openai_api_key": "test-openai-key"},
            admin_api_keys="admin-real",
            user_api_keys="user-real:user-1:default",
            cors_allowed_origins="*",
            storage_backend="s3",
            s3_bucket="bucket",
            rate_limit_backend="redis",
            redis_url="redis://localhost:6379/0",
        )


def test_redis_limiter_uses_redis_client_mock(monkeypatch):
    calls = []

    class FakeClient:
        def ping(self):
            calls.append("ping")

        def incr(self, key):
            calls.append(("incr", key))
            return 1

        def expire(self, key, ttl):
            calls.append(("expire", key, ttl))

    class FakeRedis:
        @staticmethod
        def from_url(url, decode_responses=True):
            calls.append(("from_url", url, decode_responses))
            return FakeClient()

    monkeypatch.setitem(__import__("sys").modules, "redis", type("RedisModule", (), {"Redis": FakeRedis}))

    limiter = RedisRateLimiter("redis://localhost:6379/0")
    limiter.check("user-key")

    assert "ping" in calls
    assert ("incr", "rate-limit:user-key") in calls


def test_readiness_failure_when_db_unavailable():
    class BadDB:
        def execute(self, statement):
            raise RuntimeError("db down")

    result = readiness_check(BadDB())

    assert result["ready"] is False
    assert result["checks"]["db"]["ok"] is False
