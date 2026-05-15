import os
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Mini RAG System"
    app_env: str = "local"
    log_level: str = "INFO"
    admin_api_keys: str = Field(default="", repr=False)
    user_api_keys: str = Field(default="", repr=False)
    auth_provider_placeholder: str = ""
    cors_allowed_origins: str = ""
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_backend: str = "memory"
    redis_url: str | None = None

    database_url: str = Field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./storage/local-rag.db"))
    storage_backend: str = "local"
    local_storage_path: str = "storage"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = Field(default=None, repr=False)
    s3_secret_access_key: str | None = Field(default=None, repr=False)

    openai_api_key: str = Field(default="", repr=False)
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-5.5"
    embedding_dimension: int = 1536
    estimated_input_cost_per_1m_tokens: float = 0.0
    estimated_output_cost_per_1m_tokens: float = 0.0

    max_upload_mb: int = 25
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 120
    retrieval_top_k: int = 6
    min_retrieval_score: float = 0.20
    retrieval_mode: str = "hybrid"
    vector_search_weight: float = 0.65
    keyword_search_weight: float = 0.35
    hybrid_rrf_k: int = 60
    hybrid_candidate_multiplier: int = 8
    reranking_enabled: bool = True
    reranker_provider: str = "local"
    rerank_top_k: int = 20
    local_reranker_lexical_weight: float = 0.35
    min_citation_score: float = 0.20
    request_timeout_seconds: int = 60
    upload_read_chunk_bytes: int = 1024 * 1024
    max_context_chars: int = 24000
    openai_max_retries: int = 3
    langfuse_enabled: bool = False
    langfuse_public_key: str = Field(default="", repr=False)
    langfuse_secret_key: str = Field(default="", repr=False)
    langfuse_host: str = "https://cloud.langfuse.com"
    allowed_pdf_content_types: set[str] = {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    }

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @field_validator(
        "embedding_dimension",
        "max_upload_mb",
        "chunk_size_tokens",
        "retrieval_top_k",
        "request_timeout_seconds",
        "hybrid_rrf_k",
        "hybrid_candidate_multiplier",
        "rerank_top_k",
        "rate_limit_requests",
        "rate_limit_window_seconds",
    )
    @classmethod
    def must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be positive")
        return value

    @field_validator("chunk_overlap_tokens")
    @classmethod
    def overlap_must_be_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("chunk overlap must be non-negative")
        return value

    @field_validator("min_retrieval_score", "vector_search_weight", "keyword_search_weight", "local_reranker_lexical_weight", "min_citation_score")
    @classmethod
    def score_must_be_probability(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("score settings must be between 0 and 1")
        return value

    @field_validator("estimated_input_cost_per_1m_tokens", "estimated_output_cost_per_1m_tokens")
    @classmethod
    def costs_must_be_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("cost estimates must be non-negative")
        return value

    @field_validator("retrieval_mode")
    @classmethod
    def retrieval_mode_must_be_supported(cls, value: str) -> str:
        allowed = {"hybrid", "vector"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"retrieval mode must be one of {sorted(allowed)}")
        return normalized

    @field_validator("reranker_provider")
    @classmethod
    def reranker_provider_must_be_supported(cls, value: str) -> str:
        allowed = {"local", "none"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"reranker provider must be one of {sorted(allowed)}")
        return normalized

    @field_validator("storage_backend")
    @classmethod
    def storage_backend_must_be_supported(cls, value: str) -> str:
        allowed = {"local", "s3"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"storage backend must be one of {sorted(allowed)}")
        return normalized

    @field_validator("rate_limit_backend")
    @classmethod
    def rate_limit_backend_must_be_supported(cls, value: str) -> str:
        allowed = {"memory", "redis"}
        normalized = value.lower()
        if normalized not in allowed:
            raise ValueError(f"rate limit backend must be one of {sorted(allowed)}")
        return normalized

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS")
        is_prod = self.app_env.lower() in {"prod", "production"}
        if is_prod and (not self.openai_api_key or self.openai_api_key in {"replace-me", "test-key"}):
            raise ValueError("A real OPENAI_API_KEY is required in production")
        if is_prod and (not self.admin_api_keys or "dev-" in self.admin_api_keys):
            raise ValueError("Non-dev ADMIN_API_KEYS are required in production")
        if is_prod and not self.user_api_keys and not self.auth_provider_placeholder:
            raise ValueError("USER_API_KEYS or AUTH_PROVIDER_PLACEHOLDER is required in production")
        if is_prod and ("dev-" in self.user_api_keys or "test" in self.user_api_keys):
            raise ValueError("USER_API_KEYS cannot contain dev/test placeholders in production")
        cors_origins = [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]
        if is_prod and (not cors_origins or "*" in cors_origins):
            raise ValueError("Strict CORS_ALLOWED_ORIGINS are required in production")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        if is_prod and self.storage_backend == "local":
            raise ValueError("STORAGE_BACKEND=s3 is required in production")
        if is_prod and not self.rate_limit_enabled:
            raise ValueError("Rate limiting must be enabled in production")
        if is_prod and self.rate_limit_backend != "redis":
            raise ValueError("RATE_LIMIT_BACKEND=redis is required in production")
        if self.rate_limit_backend == "redis" and not self.redis_url:
            raise ValueError("REDIS_URL is required when RATE_LIMIT_BACKEND=redis")
        if is_prod and self.max_upload_mb > 100:
            raise ValueError("MAX_UPLOAD_MB must be <= 100 in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
