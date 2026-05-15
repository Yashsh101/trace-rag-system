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


def test_production_config_requires_non_local_storage():
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
