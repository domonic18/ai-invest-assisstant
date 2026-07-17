import secrets
from functools import lru_cache
from pathlib import Path

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
    collector_queue_key: str = "collector:queue"

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str | None = None
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "invest-files"
    minio_secure: bool = False
    minio_region: str = "us-east-1"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Encryption for stored credentials (API keys, tokens)
    credential_encryption_key: str = ""

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    prompts_dir: Path = base_dir / "prompts"
    skills_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "skills"


@lru_cache
def get_settings() -> Settings:
    return Settings()
