"""Collector global settings."""

import os


class CollectorSettings:
    """采集模块配置。"""

    def __init__(self) -> None:
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_user = os.getenv("DB_USER", "user")
        self.db_password = os.getenv("DB_PASSWORD", "password")
        self.db_name = os.getenv("DB_NAME", "invest")

        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.es_url = os.getenv("ES_URL", "http://localhost:9200")
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.milvus_host = os.getenv("MILVUS_HOST", "localhost")
        self.milvus_port = int(os.getenv("MILVUS_PORT", "19530"))

        self.proxy_pool_url = os.getenv("PROXY_POOL_URL")
        self.cninfo_accounts = os.getenv("CNINFO_ACCOUNTS", "[]")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = CollectorSettings()
