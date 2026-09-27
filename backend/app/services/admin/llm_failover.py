"""LLM 主备切换（failover）：上游额度耗尽的健康标记与备用解析。

主模型上游额度耗尽（限流 429 / 402 / 额度类文案）时按 config 粒度写
redis 健康键（TTL 冷却），解析层（``resolve_*`` / ``build_embedding_client``）
经 ``resolve_healthy`` 门自动切到该配置指定的备用模型；TTL 过期自愈式
重探（过期后首调失败会再标记，代价一次失败调用）。Redis 不可达时
fail-open：视为健康，不阻塞主路径。

冷却为单一档位（``settings.llm_failover_cooldown_seconds``）：不解析各家
5 小时/周窗口的精确重置时间，各家响应形状不一且维护成本高。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Final

import anthropic
import openai
import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_delete, cache_exists, cache_set, cache_ttl
from app.core.config import get_settings
from app.models.llm_config import LLMConfig

logger = structlog.get_logger(__name__)

LLM_HEALTH_KEY_TEMPLATE: Final = "llm:health:{config_id}"

# SDK 异常类之外的文案兜底（各家措辞不一，宽匹配只放大识别面：误标的最坏
# 结果是冷却期内走备用，与额度耗尽的行为一致）
_QUOTA_KEYWORDS: Final = (
    "quota",
    "usage limit",
    "rate limit",
    "insufficient",
    "额度",
    "余额",
    "限流",
)


def _health_key(config_id: int) -> str:
    return LLM_HEALTH_KEY_TEMPLATE.format(config_id=config_id)


def classify_llm_failure(status_code: int | None, message: str) -> bool:
    """按状态码与文案判断是否为额度/限流类失败（embedding 直连路径共用）。"""
    if status_code in (402, 429):
        return True
    lowered = (message or "").lower()
    return any(keyword in lowered for keyword in _QUOTA_KEYWORDS)


def classify_llm_error(exc: BaseException) -> bool:
    """判断 LangChain 透传的模型调用异常是否触发主备切换。"""
    if isinstance(exc, (openai.RateLimitError, anthropic.RateLimitError)):
        return True
    status = getattr(exc, "status_code", None)
    return classify_llm_failure(
        status if isinstance(status, int) else None, str(exc)
    )


async def mark_unhealthy(config_id: int) -> None:
    """标记配置不可用（TTL 冷却，fail-open：写失败仅告警）。

    负数 config_id 是 BYOK 哨兵（-user_id），不参与系统级 failover。
    """
    if config_id <= 0:
        return
    cooldown = get_settings().llm_failover_cooldown_seconds
    await cache_set(_health_key(config_id), "1", ex=cooldown)
    logger.warning(
        "llm_failover_marked", config_id=config_id, cooldown_seconds=cooldown
    )


async def clear_unhealthy(config_id: int) -> None:
    """清除不可用标记（管理端测试连接成功时调用）。"""
    await cache_delete(_health_key(config_id))


async def is_unhealthy(config_id: int) -> bool:
    """配置是否处于冷却期（redis 不可达 → False，不阻塞主路径）。"""
    return await cache_exists(_health_key(config_id))


async def degraded_until(config_id: int) -> datetime | None:
    """冷却截止时间（管理端展示用；无标记或 redis 不可达 → None）。"""
    ttl = await cache_ttl(_health_key(config_id))
    if ttl is None or ttl <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=ttl)


async def resolve_healthy(session: AsyncSession, config: LLMConfig) -> LLMConfig:
    """解析层出口的健康门：主配置冷却期内切到其备用配置。

    备用须存在、启用且 purpose 相同，否则维持原配置并告警（单级，
    不下钻备用自身的备用）。
    """
    backup_id = config.backup_config_id
    if not backup_id or not await is_unhealthy(config.id):
        return config
    backup = await session.get(LLMConfig, backup_id)
    if (
        backup is None
        or not backup.is_active
        or backup.id == config.id
        or backup.purpose != config.purpose
    ):
        logger.warning(
            "llm_failover_backup_invalid",
            config_id=config.id,
            backup_config_id=backup_id,
        )
        return config
    logger.warning(
        "llm_failover_switched",
        config_id=config.id,
        backup_config_id=backup.id,
        backup_name=backup.name,
    )
    return backup


class FailoverHealthCallback(AsyncCallbackHandler):
    """模型调用失败时按分类标记配置不可用（随模型实例构造，携带 config_id）。

    与 UsageMeterCallback 并列挂在 ``build_langchain_model`` 唯一出口上，
    助手循环/单轮结构化/系统任务全覆盖。``run_structured`` 的当次重试
    路径会再确定性补一次标记（幂等）。
    """

    def __init__(self, config_id: int) -> None:
        self.config_id = config_id

    async def on_llm_error(
        self, error: BaseException, *, run_id: Any = None, **kwargs: Any
    ) -> None:
        # BYOK 走负数哨兵 config_id（-user_id），不参与系统级 failover
        if self.config_id <= 0 or not classify_llm_error(error):
            return
        await mark_unhealthy(self.config_id)
