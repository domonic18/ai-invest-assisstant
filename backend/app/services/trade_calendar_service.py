"""交易日历：以指数日 K 为权威判定交易日。

被指数行情 / 涨跌统计 / 涨停池 / 板块 / 自选股 / 补采 / AI 复盘 / 涨停归因 共同依赖，
故单独抽出，避免循环引用。所有函数只读 ``quote_kline_stock_daily`` 与 ``market_breadth``。
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_breadth import MarketBreadth
from app.repositories.kline_repository import fetch_max_daily_date, has_daily_bar

_INDEX_BENCHMARK = "sh000001"


async def resolve_latest_trade_date(session: AsyncSession) -> date:
    """最近交易日：以指数日 K 为权威。

    盘中日 K 未出时，若当日已有涨跌统计（采集器盘中写入）则取当日；
    否则回退到最近一根指数日 K 的日期。避免被涨停池等
    可能被非交易日污染表的 max(trade_date) 带偏。
    """
    today = date.today()
    kline_max = await fetch_max_daily_date(session, _INDEX_BENCHMARK)
    if kline_max is None:
        return today
    if today > kline_max and today.weekday() < 5:
        has_breadth = await session.scalar(
            select(func.count())
            .select_from(MarketBreadth)
            .where(MarketBreadth.trade_date == today)
        )
        if has_breadth:
            return today
    return kline_max


async def is_trading_day(session: AsyncSession, day: date) -> bool:
    """以指数日 K 为准判断交易日；日 K 未覆盖的近期工作日按交易日放行。"""
    if day.weekday() >= 5:
        return False
    kline_max = await fetch_max_daily_date(session, _INDEX_BENCHMARK)
    if kline_max is None or day > kline_max:
        return True
    return await has_daily_bar(session, _INDEX_BENCHMARK, day)
