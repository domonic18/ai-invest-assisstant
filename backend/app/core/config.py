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

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str | None = None
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "invest-files"
    minio_secure: bool = False
    minio_region: str = "us-east-1"
    # COS 等强制 virtual-host 寻址的 S3 兼容服务须开启（MinIO 保持关闭）
    minio_virtual_host: bool = False

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 天

    # 凭据加密（API key、token 等存储凭据）
    credential_encryption_key: str = ""

    # LLM HTTP 客户端超时
    # 控制所有通过 LangChain 模型发起的 LLM 调用的 HTTP 超时。
    # 读超时过小会导致长文本、结构化输出或 provider 拥堵时被异常截断；过大则会让
    # Agent 在 provider 偶发慢响应时长时间挂起。默认值兼顾正常响应与快速失败。
    llm_http_read_timeout: float = 300.0  # 等待响应首字节及后续数据的超时（秒）；非流式长文本生成常超 60s
    llm_max_retries: int = 2  # provider 默认重试次数

    # SPA 静态托管（web 镜像内烘 ENV STATIC_DIR=/app/static；为空则纯 API 模式）
    static_dir: Path | None = None
    # SCF 入口 HTTPS 但以 HTTP 转发容器且不带 X-Forwarded-Proto 时置 1，
    # 由 ForceForwardedHttpsMiddleware 强制 scheme=https（本地 http 访问必须保持 0）
    force_forwarded_https: bool = False

    # 路径
    base_dir: Path = Path(__file__).resolve().parent.parent
    prompts_dir: Path = base_dir / "prompts"
    skills_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "skills"


@lru_cache
def get_settings() -> Settings:
    return Settings()
