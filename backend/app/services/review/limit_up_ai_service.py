"""AI 涨停归因（题材分组 + 涨停原因 + 个股题材标签）服务。

生成结果按 (skill_id, input_hash=trade_date) 缓存在 ai_analysis_result 表，
支持强制重新生成。本模块顶层不依赖 market_service（供其顶层 import），
生成路径在函数内延迟 import 以打破循环。
"""

import hashlib
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Date, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.core.config import get_settings
from app.models.news_announcement import NewsAnnouncement
from app.repositories.review import ai_analysis_repository

SKILL_ID = "limit-up-review"

_MAX_NEWS_ITEMS = 30
_NEWS_SUMMARY_CHARS = 200


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


def _format_amount(amount: float | None) -> str:
    if amount is None:
        return "未知"
    return f"{amount / 1e8:.1f} 亿元"


async def _fetch_news_context(session: AsyncSession, trade_date: date) -> str:
    stmt = (
        select(NewsAnnouncement.title, NewsAnnouncement.summary)
        .where(
            sa_cast(NewsAnnouncement.publish_date, Date).in_(
                [trade_date, trade_date - timedelta(days=1)]
            )
        )
        .order_by(NewsAnnouncement.publish_date.desc())
        .limit(_MAX_NEWS_ITEMS)
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        return "当日无相关新闻入库"
    lines = []
    for title, summary in rows:
        line = title or ""
        if summary:
            line += f" — {summary[:_NEWS_SUMMARY_CHARS]}"
        lines.append(line)
    return "\n".join(lines)


async def generate_attribution(
    session: AsyncSession,
    trade_date: date | None = None,
    regenerate: bool = False,
) -> LimitUpAttributionContent:
    """生成（或读取缓存的）AI 涨停归因。

    Raises:
        NonTradingDayError: 指定日期不是交易日
        ValueError: 当日无涨停数据，无法归因
        LLMConfigNotConfiguredError: 未配置默认 LLM
    """
    # 延迟 import 打破 limit_pool_service → limit_up_ai_service → limit_pool_service 循环
    from app.services import (
        limit_pool_service,
        sector_service,
        trade_calendar_service,
    )
    from app.services.review.market_review_service import NonTradingDayError

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
        raise ValueError(f"{resolved_date.isoformat()} 无涨停数据，无法归因")

    sectors = await sector_service.get_sector_overview(session, resolved_date)
    news_context = await _fetch_news_context(session, resolved_date)

    limit_up_context = "\n".join(
        f"{item.stock_name}（{item.stock_code}）{item.industry or '未分类'}"
        f" {item.consecutive_boards or 1}板"
        f" {item.seal_type or '普通'} 首次封板 {item.first_seal_time or '未知'}"
        for item in limit_up.items
    )
    sector_context = "；".join(
        f"{item.sector_name}（{item.change_pct:+.2f}%，涨停 {item.limit_up_count} 家，"
        f"主力净流入 {_format_amount(item.main_net_inflow)}）"
        for item in sectors.leading
        if item.change_pct is not None
    ) or "无数据"

    prompt_loader = PromptLoader(get_settings().prompts_dir)
    prompt_config = prompt_loader.load("skills", SKILL_ID)
    user_prompt = PromptRenderer.render(
        prompt_config.user_prompt_template,
        trade_date=resolved_date.isoformat(),
        pool_count=str(len(limit_up.items)),
        limit_up_context=limit_up_context,
        sector_context=sector_context,
        news_context=news_context,
    )

    # 延迟导入：app.agent.runtime 顶层依赖 services，避免 services 聚合时环导入
    from app.agent.runtime import run_structured_agent_with_metrics

    content, latency_ms, model_name = await run_structured_agent_with_metrics(
        session,
        prompt_config=prompt_config,
        user_prompt=user_prompt,
        result_type=LimitUpAttributionContent,
    )

    valid_codes = {item.stock_code for item in limit_up.items}
    content = _validate(content, valid_codes)

    await _persist(session, input_hash, model_name, content, latency_ms)
    return content
