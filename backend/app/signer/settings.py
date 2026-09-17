"""签名 sidecar 服务配置：env 驱动的冻结快照。

独立于 ``app.core.config``：本服务不持有数据库/Redis 语义，
env 前缀 ``DOUYIN_SIGNER_`` 自成边界（容器内唯一进程读取一次）。
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SignerSettings(BaseSettings):
    """签名服务运行参数（全部有安全默认值，容器内零配置可跑）。"""

    model_config = SettingsConfigDict(env_prefix="DOUYIN_SIGNER_", frozen=True)

    bind_host: str = "0.0.0.0"
    bind_port: int = 8010
    signing_page_url: str = "https://www.douyin.com/"
    headless: bool = True
    log_level: str = "info"

    # 生命周期（实测参数来源见 docs/arch/11-social-sentiment.md）
    warm_slots: int = 2
    warm_refresh_seconds: float = 1800.0
    max_concurrent_signs: int = 2
    sign_timeout_seconds: float = 8.0
    context_open_timeout_seconds: float = 45.0
    sdk_ready_timeout_seconds: float = 25.0
    sign_attempts_per_request: int = Field(default=2, ge=1, le=3)

    @field_validator(
        "warm_slots",
        "warm_refresh_seconds",
        "max_concurrent_signs",
        "sign_timeout_seconds",
        "context_open_timeout_seconds",
        "sdk_ready_timeout_seconds",
    )
    @classmethod
    def _positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be positive")
        return value
