import pytest

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.services.storage import LocalStorageBackend


def test_local_storage_backend_round_trip(tmp_path):
    storage = LocalStorageBackend(root=tmp_path)

    uri = storage.put_bytes("raw/test.pdf", b"%PDF-data", "application/pdf")

    assert uri.startswith("local://")
    assert storage.get_bytes(uri) == b"%PDF-data"


def test_missing_artifact_raises_not_found(tmp_path):
    storage = LocalStorageBackend(root=tmp_path)

    with pytest.raises(NotFoundError):
        storage.get_bytes(f"local://{tmp_path.as_posix()}/missing.pdf")


def test_production_config_requires_non_local_storage(monkeypatch):
    import os

    from app.core import config as config_mod

    # Settings() reads env vars even when fields are passed explicitly,
    # so clear RATE_LIMIT_ENABLED to ensure the production validation
    # under test is not short-circuited by the local test environment.
    # pydantic-settings reads env vars even when fields are passed explicitly,
    # so neutralize the local test environment before constructing Settings.
    for key in (
        "RATE_LIMIT_ENABLED",
        "ADMIN_API_KEYS",
        "USER_API_KEYS",
        "OPENAI_API_KEY",
        "CORS_ALLOWED_ORIGINS",
        "STORAGE_BACKEND",
        "RATE_LIMIT_BACKEND",
        "REDIS_URL",
        "S3_BUCKET",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config_mod.settings, "rate_limit_enabled", True)
    with pytest.raises(ValueError, match="STORAGE_BACKEND=s3"):
        Settings(
            app_env="production",
            **{"openai_api_key": "test-openai-key"},
            admin_api_keys="admin-real",
            user_api_keys="user-real:user-1:default",
            cors_allowed_origins="https://rag.example.com",
            rate_limit_backend="redis",
            redis_url="redis://localhost:6379/0",
            storage_backend="local",
        )


def test_s3_config_requires_bucket():
    with pytest.raises(ValueError, match="S3_BUCKET"):
        Settings(storage_backend="s3")
