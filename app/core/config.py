from functools import lru_cache
import logging
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    Security: All sensitive values (API keys, passwords, URLs) are loaded from
    environment variables, never hardcoded. Use SecretStr to prevent accidental
    logging of credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "TraceRAG"
    app_env: Literal["local", "test", "production"] = "local"
    log_level: str = "INFO"

    # Authentication & Authorization
    admin_api_keys: SecretStr = Field(default="", repr=False)
    user_api_keys: SecretStr = Field(default="", repr=False)
    auth_provider_placeholder: str = ""
    cors_allowed_origins: str = ""

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    redis_url: str | None = Field(default=None, repr=False)

    # Database (REQUIRED - no defaults)
    database_url: SecretStr = Field(
        default="",
        repr=False,
        description="PostgreSQL URL. Format: postgresql+psycopg://user:password@host:5432/database"
    )

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_path: str = "storage"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key_id: SecretStr | None = Field(default=None, repr=False)
    s3_secret_access_key: SecretStr | None = Field(default=None, repr=False)

    # LLM Configuration
    openai_api_key: SecretStr = Field(default="", repr=False)
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4-turbo"
    embedding_dimension: int = 1536
    estimated_input_cost_per_1m_tokens: float = 0.0
    estimated_output_cost_per_1m_tokens: float = 0.0

    # RAG Parameters
    max_upload_mb: int = 25
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 120
    retrieval_top_k: int = 6
    min_retrieval_score: float = 0.20
    retrieval_mode: Literal["hybrid", "vector"] = "hybrid"
    vector_search_weight: float = 0.65
    keyword_search_weight: float = 0.35
    hybrid_rrf_k: int = 60
    hybrid_candidate_multiplier: int = 8
    reranking_enabled: bool = True
    reranker_provider: Literal["local", "none"] = "local"
    rerank_top_k: int = 20
    local_reranker_lexical_weight: float = 0.35
    min_citation_score: float = 0.20

    # Performance
    request_timeout_seconds: int = 60
    upload_read_chunk_bytes: int = 1024 * 1024
    max_context_chars: int = 24000
    openai_max_retries: int = 3

    # Observability
    langfuse_enabled: bool = False
    langfuse_public_key: SecretStr = Field(default="", repr=False)
    langfuse_secret_key: SecretStr = Field(default="", repr=False)
    langfuse_host: str = "https://cloud.langfuse.com"

    # Content Type Validation
    allowed_pdf_content_types: set[str] = {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    }

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def database_url_str(self) -> str:
        """Get database URL as string (use when passing to SQLAlchemy)."""
        return self.database_url.get_secret_value() if self.database_url else ""

    @property
    def openai_api_key_str(self) -> str:
        """Get OpenAI API key as string."""
        return self.openai_api_key.get_secret_value() if self.openai_api_key else ""

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url_scheme(cls, value: str | SecretStr) -> SecretStr:
        """Normalize PostgreSQL URL schemes for psycopg3 compatibility."""
        if isinstance(value, SecretStr):
            value_str = value.get_secret_value()
        else:
            value_str = value or ""

        if value_str.startswith("postgresql://"):
            value_str = value_str.replace("postgresql://", "postgresql+psycopg://", 1)
        return SecretStr(value_str)

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

    @field_validator(
        "min_retrieval_score",
        "vector_search_weight",
        "keyword_search_weight",
        "local_reranker_lexical_weight",
        "min_citation_score",
    )
    @classmethod
    def score_must_be_probability(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("score settings must be between 0 and 1")
        return value

    @field_validator(
        "estimated_input_cost_per_1m_tokens",
        "estimated_output_cost_per_1m_tokens",
    )
    @classmethod
    def costs_must_be_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("cost estimates must be non-negative")
        return value

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """Validate settings consistency and production requirements."""
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError(
                "CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS"
            )

        is_prod = self.app_env.lower() in {"prod", "production"}

        # Database validation
        if not self.database_url_str:
            raise ValueError(
                "DATABASE_URL is required (e.g., postgresql+psycopg://user:pass@host:5432/db)"
            )
        if is_prod and not self.database_url_str.startswith("postgresql"):
            logger.warning("DATABASE_URL should use PostgreSQL in production")

        # OpenAI API Key validation
        if is_prod:
            openai_key = self.openai_api_key_str
            if not openai_key or openai_key in {"replace-me", "test-key", ""}:
                raise ValueError(
                    "A real OPENAI_API_KEY is required in production"
                )

        # Admin API Keys validation
        admin_keys = self.admin_api_keys.get_secret_value() if isinstance(self.admin_api_keys, SecretStr) else str(self.admin_api_keys)
        if is_prod:
            if not admin_keys or "dev-" in admin_keys:
                raise ValueError(
                    "Non-dev ADMIN_API_KEYS are required in production"
                )

        # User API Keys validation
        user_keys = self.user_api_keys.get_secret_value() if isinstance(self.user_api_keys, SecretStr) else str(self.user_api_keys)
        if is_prod:
            if not user_keys and not self.auth_provider_placeholder:
                raise ValueError(
                    "USER_API_KEYS or AUTH_PROVIDER_PLACEHOLDER is required in production"
                )
            if user_keys and ("dev-" in user_keys or "test" in user_keys):
                raise ValueError(
                    "USER_API_KEYS cannot contain dev/test placeholders in production"
                )

        # CORS validation
        cors_origins = [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]
        if is_prod and (not cors_origins or "*" in cors_origins):
            raise ValueError(
                "Strict CORS_ALLOWED_ORIGINS are required in production (comma-separated, no wildcards)"
            )

        # Storage validation
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")

        if is_prod and self.storage_backend == "local":
            logger.warning(
                "Using local storage in production. Consider S3 or similar for scalability."
            )

        # Rate limiting validation
        if is_prod and not self.rate_limit_enabled:
            raise ValueError("Rate limiting must be enabled in production")

        if self.rate_limit_backend == "redis" and not self.redis_url:
            raise ValueError(
                "REDIS_URL is required when RATE_LIMIT_BACKEND=redis"
            )

        # Upload size validation
        if is_prod and self.max_upload_mb > 100:
            raise ValueError("MAX_UPLOAD_MB must be <= 100 in production")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance. Use dependency injection in FastAPI."""
    try:
        return Settings()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise


# Global settings instance (used as fallback)
try:
    settings = get_settings()
except ValueError as e:
    logger.critical(f"Failed to load settings: {e}")
    raise SystemExit(1) from e
