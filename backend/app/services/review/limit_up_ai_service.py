"""AI 涨停归因（题材分组 + 涨停原因 + 个股题材标签）服务。

生成结果按 (skill_id, input_hash=trade_date) 缓存在 ai_analysis_result 表，
支持强制重新生成。本模块顶层不依赖 market_service（供其顶层 import），
生成路径在函数内延迟 import 以打破循环。LLM 交互由 deepagents 执行器
``app.agent.skills.limit_up_review_agent`` 承担，本模块负责缓存/加锁/后置校验/落库。
"""

import hashlib
from datetime import date
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptLoader
from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.core.locking import redis_lock
from app.repositories.review import ai_analysis_repository

SKILL_ID = "limit-up-review"


class LimitUpAttributionLockedError(ConflictError):
    """其他实例正在生成同一交易日的涨停归因。"""

    default_message = "涨停归因正在生成中，请稍后重试"


class AttributionGroup(BaseModel):
    """单个题材分组：题材名 + 涨停原因 + 组内股票代码。"""

    theme: str
    reason: str
    stock_codes: list[str]


class LimitUpAttributionContent(BaseModel):
    """LLM 结构化输出（校验后持久化）。"""

    groups: list[AttributionGroup]
    stock_themes: dict[str, list[str]] = {}


def _input_hash(trade_date: date) -> str:
    return hashlib.sha256(f"{SKILL_ID}:{trade_date.isoformat()}".encode()).hexdigest()


async def _load_cached(
    session: AsyncSession, input_hash: str
) -> LimitUpAttributionContent | None:
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=SKILL_ID, input_hash=input_hash
    )
    if row is None or not row.structured_output:
        return None
    return LimitUpAttributionContent.model_validate(row.structured_output)


async def get_cached_attribution(
    session: AsyncSession, trade_date: date
) -> LimitUpAttributionContent | None:
    """只读取已生成的 AI 涨停归因，不存在时返回 None（绝不触发 LLM 生成）。"""
    return await _load_cached(session, _input_hash(trade_date))


def _validate(
    content: LimitUpAttributionContent, valid_codes: set[str]
) -> LimitUpAttributionContent:
    """后置校验：剔除幻觉代码、跨组去重（一股一组）。"""
    seen: set[str] = set()
    groups: list[AttributionGroup] = []
    for group in content.groups:
        codes = [
            code
            for code in group.stock_codes
            if code in valid_codes and code not in seen
        ]
        seen.update(codes)
        if codes:
            groups.append(
                AttributionGroup(
                    theme=group.theme, reason=group.reason, stock_codes=codes
                )
            )
    stock_themes = {
        code: themes
        for code, themes in content.stock_themes.items()
        if code in valid_codes
    }
    return LimitUpAttributionContent(groups=groups, stock_themes=stock_themes)


async def _persist(
    session: AsyncSession,
    input_hash: str,
    model: str,
    content: LimitUpAttributionContent,
    latency_ms: int,
) -> None:
    structured: dict[str, Any] = content.model_dump()
    await ai_analysis_repository.insert_result(
        session,
        skill_id=SKILL_ID,
        input_hash=input_hash,
        prompt_id=SKILL_ID,
        model=model,
        structured=structured,
        latency_ms=latency_ms,
        status="success",
    )
    await session.commit()


async def persist_attribution_result(
    session: AsyncSession,
    trade_date: date,
    content: LimitUpAttributionContent,
    *,
    model: str,
    latency_ms: int = 0,
) -> LimitUpAttributionContent:
    """持久化助手对话路径产出的归因（校验代码后写 ai_analysis_result 最新行）。

    Raises:
        ReviewInputDataNotReadyError: 涨停池数据尚未落库，无法校验与落库。
    """
    from app.services.market import limit_pool_service
    from app.services.review.market_review_service import ReviewInputDataNotReadyError

    limit_up = await limit_pool_service.get_limit_up(session, trade_date)
    if not limit_up.items:
        raise ReviewInputDataNotReadyError(
            f"{trade_date.isoformat()} 涨停池数据尚未就绪，无法归因"
        )
    content = _validate(content, {item.stock_code for item in limit_up.items})
    await _persist(session, _input_hash(trade_date), model, content, latency_ms)
    return content


async def generate_attribution(
    session: AsyncSession,
    trade_date: date | None = None,
    regenerate: bool = False,
) -> LimitUpAttributionContent:
    """生成（或读取缓存的）AI 涨停归因。

    Raises:
        NonTradingDayError: 指定日期不是交易日
        ReviewInputDataNotReadyError: 涨停池数据尚未落库（由 Celery 定时任务退避重试）
        LimitUpAttributionLockedError: 其他实例正在生成同一交易日的归因
        LLMConfigNotConfiguredError: 未配置默认 LLM
    """
    # 延迟 import 打破 limit_pool_service → limit_up_ai_service → limit_pool_service 循环
    from app.services.market import limit_pool_service, trade_calendar_service
    from app.services.review.market_review_service import (
        NonTradingDayError,
        ReviewInputDataNotReadyError,
    )

    if trade_date is not None and not await trade_calendar_service.is_trading_day(
        session, trade_date
    ):
        raise NonTradingDayError(
            f"{trade_date.isoformat()} 不是交易日，涨停归因只对交易日有效"
        )
    resolved_date = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    input_hash = _input_hash(resolved_date)

    if not regenerate:
        cached = await _load_cached(session, input_hash)
        if cached:
            return cached

    limit_up = await limit_pool_service.get_limit_up(session, resolved_date)
    if not limit_up.items:
        raise ReviewInputDataNotReadyError(
            f"{resolved_date.isoformat()} 涨停池数据尚未就绪，无法归因"
        )

    async with redis_lock(f"{SKILL_ID}:{resolved_date.isoformat()}", ttl=300) as acquired:
        if not acquired:
            cached = await _load_cached(session, input_hash)
            if cached:
                return cached
            raise LimitUpAttributionLockedError(
                f"其他实例正在生成 {resolved_date.isoformat()} 的涨停归因"
            )

        if not regenerate:
            cached = await _load_cached(session, input_hash)
            if cached:
                return cached

        prompt_loader = PromptLoader(get_settings().prompts_dir)
        prompt_config = prompt_loader.load("skills", SKILL_ID)

        # 延迟导入：agent 执行器反向依赖本模块的输出模型，避免 services 聚合时环导入
        from app.agent.skills.limit_up_review_agent import run_skill

        content, model_name, latency_ms = await run_skill(
            session,
            trade_date=resolved_date,
            pool_count=len(limit_up.items),
            prompt_config=prompt_config,
        )

        valid_codes = {item.stock_code for item in limit_up.items}
        content = _validate(content, valid_codes)

        await _persist(session, input_hash, model_name, content, latency_ms)
        return content
