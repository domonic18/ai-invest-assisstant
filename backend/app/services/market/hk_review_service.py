"""港股复盘卡片数据：恒生系指数收盘 + 港股涨幅榜。

每日复盘的港股扩展卡。港股行情延时 15 分钟且收盘晚于 A 股，不复盘中
实时取数：恒生系取不晚于复盘日的最新收盘（EM 渠道断供期间数据停更时
字段留空）；涨幅榜按复盘日精确匹配日 K，A/H 假日不一致导致的港股休市
日自然返回空态（实时视图例外：自动归位最近港股交易日）。
"""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.constants import GLOBAL_INDEX_CODES, INDEX_TREND_DAYS
from app.repositories.market import (
    global_index_repository,
    kline_repository,
    trade_calendar_repository,
)
from app.schemas.market import GlobalIndexQuoteResponse, HkGainerItem

# 复盘卡固定展示的恒生系指数（随 GLOBAL_INDEX_CODES 同源维护）
_HK_REVIEW_INDEX_CODES = ("HSI", "HSTECH", "HSCEI")

# 涨幅榜流动性门槛：0.5 港元以下仙股与日内成交额不足 1000 万港元的不进榜
_MIN_CLOSE = 0.5
_MIN_AMOUNT = 10_000_000

# 实时视图归位回看窗口（自然日）：覆盖春节+国庆最长连休
_SESSION_LOOKBACK_DAYS = 30


async def get_hk_review_indices(
    session: AsyncSession, trade_date: date | None = None
) -> list[GlobalIndexQuoteResponse]:
    """恒生系指数收盘卡：不晚于复盘日的最新收盘 + 近 N 日收盘趋势。"""
    codes = [c for c in _HK_REVIEW_INDEX_CODES if c in GLOBAL_INDEX_CODES]
    if not codes:
        return []
    on_or_before = trade_date or today_cn()
    latest = await global_index_repository.map_latest_closes(
        session, codes, on_or_before=on_or_before
    )
    trends = await global_index_repository.map_recent_closes(
        session, codes, INDEX_TREND_DAYS, on_or_before=on_or_before
    )
    results: list[GlobalIndexQuoteResponse] = []
    for code in codes:
        close, change_pct, index_date = latest.get(code, (None, None, None))
        results.append(
            GlobalIndexQuoteResponse(
                index_code=code,
                index_name=GLOBAL_INDEX_CODES[code]["name"],
                close=float(close) if close is not None else None,
                change_pct=float(change_pct) if change_pct is not None else None,
                trade_date=index_date,
                trend=trends.get(code, []),
            )
        )
    return results


async def get_hk_gainers(
    session: AsyncSession,
    trade_date: date | None = None,
    limit: int = 10,
) -> list[HkGainerItem]:
    """港股涨幅榜：指定交易日精确匹配，流动性门槛过滤仙股/低成交额。

    显式复盘日（含港股休市日）精确匹配，休市日空列表由前端展示休市态；
    实时视图（未传日期）归位最近港股交易日，避免盘前/休市日整天空榜。
    """
    day = trade_date or today_cn()
    if trade_date is None:
        day = await _latest_hk_session(session, day)
    rows = await kline_repository.list_hk_gainers(
        session, day, limit=limit, min_close=_MIN_CLOSE, min_amount=_MIN_AMOUNT
    )
    return [
        HkGainerItem(
            stock_code=stock_code,
            stock_name=stock_name,
            close=float(close) if close is not None else None,
            change_pct=float(change_pct) if change_pct is not None else None,
            amount=float(amount) if amount is not None else None,
            trade_date=day,
        )
        for stock_code, stock_name, close, change_pct, amount in rows
    ]


async def _latest_hk_session(session: AsyncSession, day: date) -> date:
    """不晚于 day 的最近港股交易日（日历权威；无覆盖原样返回 → 空态）。"""
    rows = await trade_calendar_repository.get_range(
        session, day - timedelta(days=_SESSION_LOOKBACK_DAYS), day, market="hk"
    )
    trading = [row.calendar_date for row in rows if row.is_trading]
    return max(trading) if trading else day
