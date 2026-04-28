import hashlib
import math
import re

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.errors import ExternalServiceError


class EmbeddingService:
    def __init__(self, client: OpenAI | None = None):
        self._client = client

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key, timeout=settings.request_timeout_seconds)
        return self._client

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(settings.openai_max_retries), reraise=True)
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._client is None and _use_local_ai():
            return [_local_embedding(text) for text in texts]
        try:
            response = self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=texts,
                dimensions=settings.embedding_dimension,
            )
        except Exception as exc:
            raise ExternalServiceError("Embedding provider request failed") from exc

        vectors = [item.embedding for item in response.data]
        if len(vectors) != len(texts):
            raise ExternalServiceError("Embedding provider returned an unexpected number of vectors")
        if any(len(vector) != settings.embedding_dimension for vector in vectors):
            raise ExternalServiceError("Embedding provider returned vectors with an unexpected dimension")
        return vectors

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _use_local_ai() -> bool:
    return settings.app_env.lower() == "local" and settings.openai_api_key in {"", "replace-me", "test-key"}


def _local_embedding(text: str) -> list[float]:
    vector = [0.0] * settings.embedding_dimension
    for token in TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % settings.embedding_dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
