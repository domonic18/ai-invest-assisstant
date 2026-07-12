import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "AI Invest Assistant"
    debug: bool = False
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # Database
    database_url: PostgresDsn = PostgresDsn("postgresql+asyncpg://user:password@localhost:5432/invest")
    database_echo: bool = False

    # Redis
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "invest-files"
    minio_secure: bool = False

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # AI Model defaults
    default_model_provider: Literal["openai", "anthropic"] = "openai"
    default_model: str = "gpt-4o"
    openai_api_key: str = ""
    openai_base_url: str | None = None
    anthropic_api_key: str = ""

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    prompts_dir: Path = base_dir / "app" / "prompts"
    skills_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "skills"

    @property
    def default_model_config(self) -> dict:
        return {
            "provider": self.default_model_provider,
            "model": self.default_model,
            "api_key": self.openai_api_key if self.default_model_provider == "openai" else self.anthropic_api_key,
            "base_url": self.openai_base_url,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
