"""LLM 主备切换（failover）：失败分类、健康标记与备用解析。

失败按类分档处理（2026-11-11 主备下沉到选择点）：

- ``quota``：额度耗尽/限流（402/429/额度类文案）→ 长冷却
  （``llm_failover_cooldown_seconds``，默认 600s）。
- ``connect``：连接类失败（超时/断流/连接重置）→ 短冷却
  （``llm_failover_connect_cooldown_seconds``，默认 300s），瞬时抖动
  不应长罚（2026-11-10 生产 mimo 断流无兜底事故的回应）。

健康标记按 config 粒度写 redis（``llm:health:{config_id}``，TTL 即冷却），
切换决策在**选择点**：``resolve_healthy`` 接收显式备用 id（任务槽位的
backup_config_id / KB 角色备列等），主冷却或失效期内走备用；TTL 过期
自愈式重探。Redis 不可达时 fail-open：视为健康，不阻塞主路径。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Final, Literal

import anthropic
import httpx
import openai
import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_delete, cache_exists, cache_set, cache_ttl
from app.core.config import get_settings
from app.models.llm_config import LLMConfig

logger = structlog.get_logger(__name__)

LLM_HEALTH_KEY_TEMPLATE: Final = "llm:health:{config_id}"

FailureClass = Literal["quota", "connect"]

# SDK 异常类之外的文案兜底（各家措辞不一，宽匹配只放大识别面：误标的最坏
# 结果是冷却期内走备用，与真实失败的降级行为一致）
_QUOTA_KEYWORDS: Final = (
    "quota",
    "usage limit",
    "rate limit",
    "insufficient",
    "额度",
    "余额",
    "限流",
)
_CONNECT_KEYWORDS: Final = (
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "connection error",
    "connection closed",
    # httpx.RemoteProtocolError 断流的真实文案（2026-11-10 生产 mimo 事故形态）
    "peer closed connection",
    "server disconnected",
    "remote protocol error",
    "stream disconnected",
    "断流",
    "连接超时",
)


def _health_key(config_id: int) -> str:
    return LLM_HEALTH_KEY_TEMPLATE.format(config_id=config_id)


def classify_llm_failure(status_code: int | None, message: str) -> FailureClass | None:
    """按状态码与文案分类失败（embedding 直连路径共用）。

    Returns:
        ``"quota"`` 额度/限流类、``"connect"`` 连接类，其余 ``None``（不触发切换）。
    """
    if status_code in (402, 429):
        return "quota"
    lowered = (message or "").lower()
    if any(keyword in lowered for keyword in _QUOTA_KEYWORDS):
        return "quota"
    if any(keyword in lowered for keyword in _CONNECT_KEYWORDS):
        return "connect"
    return None


def classify_llm_error(exc: BaseException) -> FailureClass | None:
    """分类 LangChain 透传的模型调用异常（quota/connect/None）。

    连接类优先按 SDK 异常类型识别（文案兜底误报面大）：openai 的超时是
    ``APITimeoutError``（``APIConnectionError`` 子类）、anthropic 同构；
    httpx 直连路径（embedding 等）的超时/断流/连接重置同理。
    """
    if isinstance(exc, (openai.RateLimitError, anthropic.RateLimitError)):
        return "quota"
    if isinstance(
        exc,
        (
            openai.APITimeoutError,
            openai.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ),
    ):
        return "connect"
    status = getattr(exc, "status_code", None)
    return classify_llm_failure(
        status if isinstance(status, int) else None, str(exc)
    )


def _cooldown_for(failure_class: FailureClass | None) -> int:
    settings = get_settings()
    if failure_class == "connect":
        return settings.llm_failover_connect_cooldown_seconds
    return settings.llm_failover_cooldown_seconds


async def mark_unhealthy(
    config_id: int, *, failure_class: FailureClass | None = None
) -> None:
    """标记配置不可用（TTL 冷却按失败类分档，fail-open：写失败仅告警）。

    负数 config_id 是 BYOK 哨兵（-user_id），不参与系统级 failover。
    """
    if config_id <= 0:
        return
    cooldown = _cooldown_for(failure_class)
    await cache_set(_health_key(config_id), "1", ex=cooldown)
    logger.warning(
        "llm_failover_marked",
        config_id=config_id,
        failure_class=failure_class,
        cooldown_seconds=cooldown,
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


async def resolve_healthy(
    session: AsyncSession, config: LLMConfig, backup_id: int | None = None
) -> LLMConfig:
    """解析层出口的健康门：主配置冷却期内切到显式指定的备用配置。

    备用来自选择点（任务槽位 backup_config_id / KB 角色备列等），写入时
    已校验；此处仍防御性核验存在/启用/purpose 一致，失配则维持原配置并
    告警（单级，不下钻）。
    """
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
        if self.config_id <= 0:
            return
        failure_class = classify_llm_error(error)
        if failure_class is None:
            return
        await mark_unhealthy(self.config_id, failure_class=failure_class)
