"""自选股实时行情：Redis 快照优先，缺失时回退最近 K 线收盘。"""

import json
import re
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.models.stock import StockBasic
from app.models.watchlist import UserWatchlist, UserWatchlistGroup
from app.repositories.market.kline_repository import (
    fetch_daily_bars,
    fetch_minute_bars_multi,
)
from app.repositories.review import ai_analysis_repository
from app.schemas.market import WatchlistQuoteItem
from app.schemas.workbench import WorkbenchWatchlistGroup, WorkbenchWatchlistStock
from app.services.market import trade_calendar_service
from app.services.market.intraday_utils import downsample


async def _load_stock_names(
    session: AsyncSession, codes: list[str]
) -> dict[str, str]:
    """stock_basic 批量取股票名称（Redis 快照缺失时的兜底）。"""
    rows = await session.execute(
        select(StockBasic.stock_code, StockBasic.stock_name).where(
            StockBasic.stock_code.in_(codes)
        )
    )
    return {code: name for code, name in rows.all()}


async def _load_minute_trend(
    session: AsyncSession, codes: list[str]
) -> dict[str, list[float]]:
    """最近交易日分钟收盘价降采样（≤60 点），无数据返回空数组。"""
    resolved = await trade_calendar_service.resolve_latest_trade_date(session)
    bars = await fetch_minute_bars_multi(session, codes, resolved)
    closes_by_code: dict[str, list[float]] = {}
    for bar in bars:
        if bar.close is None:
            continue
        closes_by_code.setdefault(bar.stock_code, []).append(float(bar.close))
    return {code: downsample(closes) for code, closes in closes_by_code.items() if closes}


async def get_watchlist_quotes(
    session: AsyncSession, user_id: int
) -> list[WatchlistQuoteItem]:
    """自选股实时行情：优先 Redis 快照，缺失时回退最近 K 线收盘价。"""
    stmt = (
        select(UserWatchlist)
        .where(UserWatchlist.user_id == user_id)
        .order_by(UserWatchlist.created_at.desc())
    )
    watch_items = list((await session.execute(stmt)).scalars().all())
    if not watch_items:
        return []
    return await _build_quote_items(session, watch_items)


async def _build_quote_items(
    session: AsyncSession, watch_items: list[UserWatchlist]
) -> list[WatchlistQuoteItem]:
    """为自选记录批量组装行情（Redis 快照 → 日 K 兜底）。"""
    codes = [item.stock_code for item in watch_items]
    redis = get_redis()
    quotes: dict[str, dict[str, Any]] = {}
    for item in watch_items:
        raw = await redis.get(f"quote:{item.stock_code}")
        if raw:
            quotes[item.stock_code] = json.loads(raw)

    names = await _load_stock_names(session, codes)
    trends = await _load_minute_trend(session, codes)

    results: list[WatchlistQuoteItem] = []
    for item in watch_items:
        trend = trends.get(item.stock_code, [])
        cached = quotes.get(item.stock_code)
        if cached:
            results.append(
                WatchlistQuoteItem(
                    code=item.stock_code,
                    name=cached.get("stock_name") or names.get(item.stock_code),
                    price=cached.get("price"),
                    change_pct=cached.get("change_pct"),
                    amount=cached.get("amount"),
                    tags=list(item.tags or []),
                    updated_at=cached.get("updated_at"),
                    trend=trend,
                )
            )
            continue

        daily = [
            bar
            for bar in await fetch_daily_bars(session, item.stock_code, limit=2)
            if bar.close is not None
        ]
        latest = daily[0] if daily else None
        prev = daily[1] if len(daily) > 1 else None
        # 日 K 渠道多缺 change_pct 字段，缺省时按前收盘推算（与 get_stock_quote 同口径）
        price: float | None = None
        change_pct: float | None = None
        amount: float | None = None
        if latest is not None and latest.close is not None:
            price = float(latest.close)
            if latest.change_pct is not None:
                change_pct = float(latest.change_pct)
            elif prev is not None and prev.close:
                change_pct = (price - float(prev.close)) / float(prev.close) * 100
            if latest.amount is not None:
                amount = float(latest.amount)
        results.append(
            WatchlistQuoteItem(
                code=item.stock_code,
                name=names.get(item.stock_code),
                price=price,
                change_pct=change_pct,
                amount=amount,
                tags=list(item.tags or []),
                updated_at=latest.trade_date.isoformat() if latest is not None else None,
                trend=trend,
            )
        )
    return results


_AI_SUMMARY_SECTION_KEY = "intraday_review"
_AI_SUMMARY_MAX_CHARS = 120
_AiStatus = Literal["off", "pending", "ready"]
_MD_CHARS = re.compile(r"[#*`>\[\]]")
_WHITESPACE = re.compile(r"\s+")


def _strip_markdown(text: str) -> str:
    cleaned = _MD_CHARS.sub("", text)
    return _WHITESPACE.sub(" ", cleaned).strip()


async def _load_ai_analysis(
    session: AsyncSession, codes: list[str]
) -> dict[str, tuple[_AiStatus, str | None]]:
    """开启 AI 复盘的股票：查最近交易日已生成分析，返回 code -> (status, 盘面解读摘要)。"""
    from app.services.review import stock_daily_analysis_service

    if not codes:
        return {}

    resolved = await trade_calendar_service.resolve_latest_trade_date(session)
    sections = stock_daily_analysis_service.load_prompt_config().sections
    code_by_hash = {
        stock_daily_analysis_service.input_hash(code, resolved, sections): code
        for code in codes
    }
    rows = await ai_analysis_repository.load_success_by_hashes(
        session,
        skill_id=stock_daily_analysis_service.SKILL_ID,
        input_hashes=list(code_by_hash),
    )

    results: dict[str, tuple[_AiStatus, str | None]] = {}
    for row in rows:  # created_at 倒序，首个命中即最新
        code = code_by_hash.get(row.input_hash or "")
        if code is None or code in results:
            continue
        output_sections = (row.structured_output or {}).get("sections") or {}
        summary = _strip_markdown(
            str(output_sections.get(_AI_SUMMARY_SECTION_KEY, ""))
        )
        results[code] = (
            "ready",
            summary[:_AI_SUMMARY_MAX_CHARS] or None,
        )
    return results


async def get_watchlist_groups(
    session: AsyncSession, user_id: int
) -> list[WorkbenchWatchlistGroup]:
    """自选股按分组组织：行情 + 分组级 AI 复盘状态与盘面解读摘要（工作台概览）。"""
    group_stmt = (
        select(UserWatchlistGroup)
        .where(UserWatchlistGroup.user_id == user_id)
        .order_by(UserWatchlistGroup.sort_order, UserWatchlistGroup.id)
    )
    groups = list((await session.execute(group_stmt)).scalars().all())
    if not groups:
        return []

    item_stmt = (
        select(UserWatchlist)
        .where(UserWatchlist.user_id == user_id)
        .order_by(UserWatchlist.created_at.desc())
    )
    watch_items = list((await session.execute(item_stmt)).scalars().all())

    group_by_id = {group.id: group for group in groups}
    enabled_codes = [
        item.stock_code
        for item in watch_items
        if (group := group_by_id.get(item.group_id)) is not None
        and group.ai_review_enabled
    ]
    ai_results = await _load_ai_analysis(session, enabled_codes)

    quotes = {
        quote.code: quote
        for quote in await _build_quote_items(session, watch_items)
    }

    results: list[WorkbenchWatchlistGroup] = []
    for group in groups:
        items: list[WorkbenchWatchlistStock] = []
        for item in watch_items:
            if item.group_id != group.id:
                continue
            quote = quotes.get(item.stock_code)
            if quote is None:
                continue
            ai_status: _AiStatus = "pending"
            ai_summary: str | None = None
            if not group.ai_review_enabled:
                ai_status = "off"
            elif (fetched := ai_results.get(item.stock_code)) is not None:
                ai_status, ai_summary = fetched
            items.append(
                WorkbenchWatchlistStock(
                    **quote.model_dump(), ai_status=ai_status, ai_summary=ai_summary
                )
            )
        results.append(
            WorkbenchWatchlistGroup(
                id=group.id,
                name=group.name,
                is_default=group.is_default,
                ai_review_enabled=group.ai_review_enabled,
                items=items,
            )
        )
    return results
