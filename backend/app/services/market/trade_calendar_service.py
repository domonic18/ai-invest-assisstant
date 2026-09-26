"""交易日历：market_trade_calendar 权威日历 + 指数日 K 兜底判定交易日。

被指数行情 / 涨跌统计 / 涨停池 / 板块 / 自选股 / 补采 / AI 复盘 / 涨停归因 共同依赖，
故单独抽出，避免循环引用。判定顺序：DB 日历行（seed=新浪自动生成 / manual=人工覆盖）
为权威；无日历覆盖时回退指数日 K 推断（种子未初始化的兜底，已知近似）。
"""

from datetime import date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.exceptions import BadRequestError
from app.repositories.market import market_stats_repository, trade_calendar_repository
from app.repositories.market.kline_repository import (
    fetch_max_daily_date,
    fetch_max_daily_date_on_or_before,
    has_daily_bar,
)

logger = structlog.get_logger(__name__)

_INDEX_BENCHMARK = "sh000001"

# 调度预检三态：trading 可调度 / non_trading 拒绝 / unknown 日历未覆盖（拒绝并提示）
SCHEDULE_TRADING = "trading"
SCHEDULE_NON_TRADING = "non_trading"
SCHEDULE_UNKNOWN = "unknown"

# 归位查询回看窗口：日历覆盖范围内找不到交易日时落到指数日 K 兜底
_LOOKBACK_WINDOW_DAYS = 30


class NonTradingDayError(BadRequestError):
    """指定日期不是交易日（本语义唯一来源；补采/复盘/涨停归因共用）。"""


async def resolve_latest_trade_date(session: AsyncSession) -> date:
    """最近交易日：以指数日 K 为权威。

    盘中日 K 未出时，若当日已有涨跌统计（采集器盘中写入）则取当日；
    否则回退到最近一根指数日 K 的日期。避免被涨停池等
    可能被非交易日污染表的 max(trade_date) 带偏。
    """
    today = today_cn()
    kline_max = await fetch_max_daily_date(session, _INDEX_BENCHMARK)
    if kline_max is None:
        return today
    if today > kline_max and today.weekday() < 5:
        if await market_stats_repository.has_breadth_on(session, today):
            return today
    return kline_max


async def resolve_default_view_date(session: AsyncSession) -> date:
    """复盘视图缺省日：当天按交易日放行口径取当天（数据未就绪由各查询
    返回空态，不回退旧数据）；非交易日回退最近交易日。

    日历表覆盖当日时判定准确（节假日归位上一交易日）；
    未覆盖时按指数日 K 放行近似（种子未初始化的兜底）。
    """
    today = today_cn()
    if await is_trading_day(session, today):
        return today
    return await resolve_trade_date_on_or_before(session, today)


async def is_trading_day(session: AsyncSession, day: date) -> bool:
    """判断交易日：日历行权威；无覆盖回退指数日 K 推断（近期工作日放行）。"""
    row = await trade_calendar_repository.get_one(session, day)
    if row is not None:
        return row.is_trading
    if day.weekday() >= 5:
        return False
    kline_max = await fetch_max_daily_date(session, _INDEX_BENCHMARK)
    if kline_max is None or day > kline_max:
        return True
    return await has_daily_bar(session, _INDEX_BENCHMARK, day)


async def classify_schedule_day(session: AsyncSession, day: date) -> str:
    """调度预检口径：DB 日历行为权威，无行返回 unknown（拒绝调度，不静默回退周末启发）。"""
    row = await trade_calendar_repository.get_one(session, day)
    if row is None:
        return SCHEDULE_UNKNOWN
    return SCHEDULE_TRADING if row.is_trading else SCHEDULE_NON_TRADING


async def next_trading_day(session: AsyncSession, day: date) -> date | None:
    """day 之后最近的下一个交易日（按 DB 日历行权威）；无覆盖返回 None。"""
    row = await trade_calendar_repository.get_next_trading_day(session, day)
    return row.calendar_date if row is not None else None


async def regenerate_from_sina(
    session: AsyncSession, years: list[int] | None = None
) -> int:
    """用新浪交易日历重建种子行（覆盖整年，含周末；人工覆盖行不回改）。

    Args:
        session: 数据库会话。
        years: 生成哪几年的日历，缺省当年 + 下一年。

    Returns:
        实际写入（新增或更新）的行数。

    Raises:
        BadRequestError: 新浪日历为空或拉取失败。
    """
    if years is None:
        this_year = today_cn().year
        years = [this_year, this_year + 1]
    trading_dates = await _fetch_sina_trade_dates()
    rows: list[dict[str, Any]] = []
    for year in years:
        day = date(year, 1, 1)
        while day <= date(year, 12, 31):
            rows.append(
                {"calendar_date": day, "is_trading": day in trading_dates}
            )
            day += timedelta(days=1)
    written = await trade_calendar_repository.upsert_seed_rows(session, rows)
    await session.commit()
    logger.info("trade_calendar_regenerated", years=years, written=written)
    return written


async def set_day_manual(
    session: AsyncSession,
    day: date,
    is_trading: bool,
    remark: str | None = None,
) -> Any:
    """人工覆盖单日日历口径（限今天及未来，防历史口径篡改），返回覆盖后的行。"""

    if day < today_cn():
        raise BadRequestError("不可修改历史日期的日历口径")
    row = await trade_calendar_repository.upsert_manual_day(
        session, day, is_trading, remark
    )
    await session.commit()
    return row


async def _fetch_sina_trade_dates() -> set[date]:
    """拉取新浪全量交易日序列（akshare 延迟导入，失败不静默）。"""
    import akshare as ak  # type: ignore[import-untyped]

    try:
        df = ak.tool_trade_date_hist_sina()
    except Exception as exc:  # noqa: BLE001 - 上游异常统一转域错误
        raise BadRequestError(f"新浪交易日历拉取失败：{exc}") from exc
    if df is None or df.empty or "trade_date" not in df.columns:
        raise BadRequestError("新浪交易日历返回为空")
    result: set[date] = set()
    for raw in df["trade_date"].tolist():
        result.add(_coerce_date(raw))
    return result


def _coerce_date(raw: Any) -> date:
    """新浪日历的日期元素可能是 date / Timestamp（datetime 子类）/ str，统一收敛为 date。"""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(str(raw)[:10])


async def resolve_trade_date_on_or_before(session: AsyncSession, day: date) -> date:
    """不晚于 day 的最近交易日（非交易日查询归位用）。

    日历覆盖范围内按日历回退；未覆盖（含部分覆盖断档）落到
    指数日 K 权威，早于日 K 覆盖范围时按工作日近似回退，
    与 is_trading_day 的放行口径保持一致。
    """
    start = day - timedelta(days=_LOOKBACK_WINDOW_DAYS)
    rows = await trade_calendar_repository.get_range(session, start, day)
    if rows:
        by_date = {row.calendar_date: row.is_trading for row in rows}
        candidate = day
        while candidate >= start:
            verdict = by_date.get(candidate)
            if verdict is True:
                return candidate
            if verdict is None:
                break  # 日历断档：交由指数日 K 兜底
            candidate -= timedelta(days=1)
    kline_max = await fetch_max_daily_date_on_or_before(session, _INDEX_BENCHMARK, day)
    if kline_max is not None:
        return kline_max
    candidate = day
    for _ in range(7):
        if candidate.weekday() < 5:
            return candidate
        candidate -= timedelta(days=1)
    return day
