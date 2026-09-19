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
    # 连接/读写超时（秒）：网络不可达时快速失败进入降级路径，避免每请求挂 25s+
    redis_socket_timeout: float = 2.0

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_default_queue: str = "collector.batch"
    celery_result_expires: int = 3600

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"

    # 后台服务状态探测（GET /admin/system/status）单服务超时（秒）
    status_probe_timeout: float = 3.0

    # 渠道调试采集（POST /admin/collector/channels/{id}/debug）单次超时（秒）
    collector_debug_timeout_seconds: float = 30.0

    # 采集健康监测判定阈值（需求 02-monitoring §4.1；检测任务每日一次）
    # 连续 N 个应成功计划窗口无 success 判 critical
    health_consecutive_windows_critical: int = 2
    # 自最近成功起连续失败 N 次判 degraded
    health_consecutive_failures_degraded: int = 3
    # 7 天成功率低于该值判 degraded（skipped 剔除口径）
    health_success_rate_7d_threshold: float = 0.90
    # 高频任务（单日场次>=48）只看当日成功率，低于该值判 degraded
    health_high_freq_daily_rate_threshold: float = 0.80
    # 超过 N 天无成功（含从未成功）判 silent
    health_silent_days: int = 7
    # 计划窗口宽限系数：窗口间隔 * 该系数内完成仍算按期
    health_schedule_grace_factor: float = 1.5
    # 连续 N 个计划窗口 skipped（且有历史成功）判 degraded（产出停滞）
    health_skipped_stall_windows: int = 3
    # 异常候选实例回查的最近运行明细条数（连败/最近错误取数）
    health_recent_runs_per_instance: int = 20
    # 快照陈旧判定倍数：checked_at 距今超过 N 倍检测间隔提示"检测延迟"
    health_stale_after_multiplier: int = 2

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

    # KB 分片直传：超过阈值的文件走 multipart，分片大小与分片 URL 有效期
    kb_multipart_threshold_bytes: int = 64 * 1024 * 1024
    kb_part_size_bytes: int = 16 * 1024 * 1024
    kb_part_presign_ttl_seconds: int = 86400

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

    # AI 用量治理（F-ACCT，arch/10）
    # 配额预扣时为 completion 预留的 token 数（结束按实际 usage 结算回补）
    quota_completion_reserve_tokens: int = 1024
    # 助手 agent 按模型出口指纹缓存的实例数上界（BYOK 用户各自独立实例）
    quota_agent_cache_size: int = 8
    # 注册接口单 IP 每日提交上限（防滥用；Redis fail-open）
    auth_register_ip_limit: int = 5

    # Skill 包文件浏览（GET /skills/{id}/files）：只读文本小文件，超过上限的文件跳过
    skill_file_max_bytes: int = 64 * 1024
    skill_files_max_count: int = 20
    # 自定义技能压缩包上传（POST /skills/analyze）大小上限
    skill_upload_max_mb: int = 10

    # 问财 NL2Data 网关（AI 选股 screen_stocks 工具）
    iwencai_api_key: str = ""
    iwencai_timeout_seconds: float = 30.0

    # 抖音签名 sidecar（compose 服务名；空 = 禁用，回退本地 a_bogus）
    douyin_signer_url: str = ""

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
