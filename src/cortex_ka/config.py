"""Configuration management using pydantic-settings.

All runtime configuration (e.g., Qdrant, Redis, Ollama) is loaded from environment
variables. This enables twelve-factor compliance and secure secret injection.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        qdrant_url: Base URL for Qdrant HTTP API. Configurable via CKA_QDRANT_URL;
            defaults to http://localhost:6333 for local development.
        qdrant_api_key: API key for Qdrant (leave blank for dev if not enforced).
        redis_host: Hostname for Redis.
        redis_port: Port for Redis.
        ollama_url: Base URL for Ollama server.
        ollama_model: Identifier for the LLM model served by Ollama.
        embedding_model: Sentence-transformers model for local embedding generation.
    """

    # Qdrant base URL. Overridable via CKA_QDRANT_URL. For local/dev environments,
    # we default to the localhost mapping exposed by the qdrant-banco container.
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = Field(default=None)
    qdrant_collection_docs: str = Field(default="corporate_docs")
    qdrant_top_k: int = Field(default=5)
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    ollama_url: str = Field(default="http://ollama:11434")
    ollama_model: str = Field(default="llama3.2:3b")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    rate_limit_qpm: int = Field(default=120, description="Queries per minute allowed per process")
    conversation_max_turns: int = Field(default=5, description="Max previous turns to include in prompt context")
    api_key: str | None = Field(default=None, description="API key to protect endpoints; disabled if empty")
    cors_origins: str = Field(default="*", description="Comma-separated list of allowed CORS origins")
    https_enabled: bool = Field(default=False, description="Enable HTTPS-only headers (CSP/HSTS)")
    csp_policy: str = Field(
        default="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'",
        description="Content Security Policy applied when https_enabled=true",
    )
    llm_provider: str = Field(default="Fake", description="LLM provider: Fake|HF")
    hf_api_key: str | None = Field(default=None, description="Hugging Face API key")
    hf_model: str | None = Field(
        default=None,
        description="Hugging Face model id (e.g., TinyLlama/TinyLlama-1.1B-Chat-v1.0)",
    )
    hf_wait_for_model: bool = Field(
        default=True,
        description="Send X-Wait-For-Model header in health probe to reduce transient 503",
    )
    enable_streaming: bool = Field(default=False, description="Enable SSE /chat/stream endpoint")
    log_level: str = Field(default="INFO", description="Log level: DEBUG|INFO|WARNING|ERROR")
    max_input_tokens: int = Field(default=2048, description="Max input tokens per request")
    max_output_tokens: int = Field(default=512, description="Max output tokens per request")
    rate_limit_burst: int = Field(default=0, description="Additional burst capacity per key")
    rate_limit_window_seconds: int = Field(default=60, description="Sliding window in seconds")
    confidential_retrieval_only: bool = Field(
        default=False,
        description=(
            "When true, enforce stricter runtime posture: disallow fake LLMs "
            "and unsafe providers in banking-like deployments."
        ),
    )

    model_config = SettingsConfigDict(env_prefix="CKA_", case_sensitive=False)


settings = Settings()  # Singleton-style instance
