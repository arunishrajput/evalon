"""Pydantic Settings loaded from environment variables (.env)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration. All values come from the environment —
    no hardcoded config lives outside this class."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://evalon:evalon@localhost:5432/evalon",
        alias="DATABASE_URL",
    )

    # --- Redis ---
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    # --- JWT ---
    jwt_secret: str = Field(
        default="change-me-to-a-long-random-string-before-any-real-deployment",
        alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(
        default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS"
    )

    # --- Ollama / Model Queue ---
    ollama_base_url: str = Field(
        default="http://host.docker.internal:11434", alias="OLLAMA_BASE_URL"
    )
    inference_model: str = Field(default="qwen2.5-coder:7b", alias="INFERENCE_MODEL")
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    model_lock_timeout_seconds: int = Field(
        default=600, alias="MODEL_LOCK_TIMEOUT_SECONDS"
    )

    # --- Repository ingestion limits ---
    workspace_dir: str = Field(default="/workspace/repos", alias="WORKSPACE_DIR")
    max_repo_size_mb: int = Field(default=50, alias="MAX_REPO_SIZE_MB")
    max_file_count: int = Field(default=5000, alias="MAX_FILE_COUNT")
    clone_timeout_seconds: int = Field(default=120, alias="CLONE_TIMEOUT_SECONDS")

    # --- GitHub API ---
    github_api_token: str = Field(default="", alias="GITHUB_API_TOKEN")

    # --- CORS ---
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost", alias="CORS_ORIGINS"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
