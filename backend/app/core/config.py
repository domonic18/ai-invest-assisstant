"""应用配置（Pydantic Settings，从 .env 读取）。"""

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

    # 应用
    app_name: str = "AI Invest Assistant"
    debug: bool = False
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # 数据库
    database_url: PostgresDsn = PostgresDsn("postgresql+asyncpg://user:password@localhost:5432/invest")
    database_echo: bool = False

    # Redis
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_default_queue: str = "collector.batch"
    celery_result_expires: int = 3600

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
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 天

    # 凭据加密（API key、token 等存储凭据）
    credential_encryption_key: str = ""

    # LLM HTTP 客户端超时
    # 控制所有通过 pydantic-ai / httpx 发起的 LLM 调用的 HTTP 超时。
    # 读超时过小会导致长文本、结构化输出或 provider 拥堵时被异常截断；过大则会让
    # Agent 在 provider 偶发慢响应时长时间挂起。默认值兼顾正常响应与快速失败。
    llm_http_connect_timeout: float = 5.0  # TCP 连接建立超时（秒）
    llm_http_read_timeout: float = 60.0  # 等待响应首字节及后续数据的超时（秒）
    llm_http_write_timeout: float = 60.0  # 请求体发送超时（秒）
    llm_http_pool_timeout: float = 60.0  # 从连接池获取连接的超时（秒）
    llm_max_retries: int = 2  # provider 默认重试次数

    # 路径
    base_dir: Path = Path(__file__).resolve().parent.parent
    prompts_dir: Path = base_dir / "prompts"
    skills_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "skills"


@lru_cache
def get_settings() -> Settings:
    return Settings()
