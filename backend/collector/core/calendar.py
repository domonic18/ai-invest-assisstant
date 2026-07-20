"""A 股交易日历（新浪财经），进程内缓存，每日刷新。

网络失败时回退工作日启发式（周一~周五视为交易日），保证采集器可用性；
节假日误判风险由日期敏感型 spider 的数据源自身空结果兜底。
"""

from datetime import date, timedelta

_cache: tuple[frozenset[date], date, date] | None = None  # (dates, max_date, fetched_on)


def _fetch_trade_dates() -> frozenset[date]:
    import akshare as ak  # type: ignore[import-untyped]

    df = ak.tool_trade_date_hist_sina()
    return frozenset(v.date() if hasattr(v, "date") else v for v in df["trade_date"])


def _load() -> tuple[frozenset[date], date] | None:
    global _cache
    today = date.today()
    if _cache is None or _cache[2] < today:
        try:
            dates = _fetch_trade_dates()
        except Exception:  # noqa: BLE001
            return None
        _cache = (dates, max(dates), today)
    return _cache[0], _cache[1]


def is_trading_day(day: date) -> bool:
    """判断是否为 A 股交易日；日历缺失或超出范围时按工作日启发。"""
    loaded = _load()
    if loaded is None or day > loaded[1]:
        return day.weekday() < 5
    return day in loaded[0]


def latest_trading_day(today: date | None = None) -> date:
    """最近的（含当日的）交易日。"""
    day = today or date.today()
    loaded = _load()
    if loaded is None:
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        return day
    dates, max_date = loaded
    day = min(day, max_date)
    while day not in dates:
        day -= timedelta(days=1)
    return day
