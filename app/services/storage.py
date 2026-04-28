from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings
from app.core.errors import NotFoundError


class StorageBackend(ABC):
    name: str

    @abstractmethod
    def put_bytes(self, key: str, content: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_bytes(self, uri: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, uri: str) -> None:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    name = "local"

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.local_storage_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, content: bytes, content_type: str | None = None) -> str:
        path = self.root / _safe_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return f"local://{path.as_posix()}"

    def get_bytes(self, uri: str) -> bytes:
        path = _local_uri_to_path(uri)
        if not path.exists():
            raise NotFoundError(f"Artifact not found: {uri}")
        return path.read_bytes()

    def delete(self, uri: str) -> None:
        path = _local_uri_to_path(uri)
        if path.exists():
            path.unlink()


class S3StorageBackend(StorageBackend):
    name = "s3"

    def __init__(self):
        import boto3

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def put_bytes(self, key: str, content: bytes, content_type: str | None = None) -> str:
        extra_args = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, **extra_args)
        return f"s3://{self.bucket}/{key}"

    def get_bytes(self, uri: str) -> bytes:
        prefix = f"s3://{self.bucket}/"
        if not uri.startswith(prefix):
            raise NotFoundError(f"Artifact URI does not belong to configured bucket: {uri}")
        key = uri[len(prefix) :]
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise NotFoundError(f"Artifact not found: {uri}") from exc
        return response["Body"].read()

    def delete(self, uri: str) -> None:
        prefix = f"s3://{self.bucket}/"
        if not uri.startswith(prefix):
            raise NotFoundError(f"Artifact URI does not belong to configured bucket: {uri}")
        self.client.delete_object(Bucket=self.bucket, Key=uri[len(prefix) :])


def build_storage_backend() -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3StorageBackend()
    return LocalStorageBackend()


def _safe_key(key: str) -> Path:
    clean = key.replace("\\", "/").lstrip("/")
    if ".." in Path(clean).parts:
        raise ValueError("storage key cannot contain parent directory traversal")
    return Path(clean)


def _local_uri_to_path(uri: str) -> Path:
    if not uri.startswith("local://"):
        raise NotFoundError(f"Unsupported local artifact URI: {uri}")
    return Path(uri[len("local://") :])
