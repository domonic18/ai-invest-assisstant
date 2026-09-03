"""基于 akshare 的新浪个股分钟 K 线采集器。

抓取 1 分钟线写入 quote_kline_stock_minute 超表，涨停复盘行与自选股行情卡的
全天分时缩略图只读该表。新浪接口返回最近约 8 个交易日，运行时只保留目标
交易日（默认当日）。symbols 缺省时取目标日涨停池 ∪ 全部自选股（去重）。
"""

import contextlib
import io
from datetime import date, datetime
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.pool_limit_up_stock import LimitUpPool
from app.models.watchlist import UserWatchlist
from collector.core.base import PostgresCollector, get_engine
from collector.core.parsing import to_float, to_int

_CN_TZ = ZoneInfo("Asia/Shanghai")


def _to_sina_symbol(code: str) -> str | None:
    """纯 6 位代码转新浪 symbol（6→sh、0/3→sz）；北交所（4/8 开头）不支持返回 None。"""
    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    return None


async def _fetch_default_codes(target: date) -> list[str]:
    """默认采集范围：目标日涨停池 ∪ 全部自选股，去重升序。"""
    session_maker = async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        pool = await session.execute(
            select(LimitUpPool.stock_code)
            .where(LimitUpPool.trade_date == target)
            .order_by(LimitUpPool.stock_code)
        )
        watchlist = await session.execute(
            select(UserWatchlist.stock_code).distinct().order_by(UserWatchlist.stock_code)
        )
        return sorted({row[0] for row in pool.all()} | {row[0] for row in watchlist.all()})


class SinaStockMinuteCollector(PostgresCollector):
    """新浪财经个股分钟线采集器，写入 quote_kline_stock_minute。"""

    table = "quote_kline_stock_minute"
    conflict_key = "stock_code, trade_time"
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "trade_time"]
    required_fields: ClassVar[list[str]] = ["stock_code", "trade_time", "close"]

    async def collect(
        self,
        symbols: list[str] | None = None,
        trade_date: date | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        target = trade_date or datetime.now(_CN_TZ).date()
        codes = symbols or await _fetch_default_codes(target)

        raw: list[dict[str, Any]] = []
        for code in codes:
            symbol = _to_sina_symbol(code)
            if symbol is None:
                continue
            try:
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    df = ak.stock_zh_a_minute(symbol=symbol, period="1", adjust="")
            except Exception:  # noqa: BLE001 - 单票失败不拖垮整批
                continue
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                trade_time = datetime.strptime(str(row["day"]), "%Y-%m-%d %H:%M:%S")
                if trade_time.date() != target:
                    continue
                raw.append(
                    {
                        "stock_code": code,
                        "trade_time": trade_time.replace(tzinfo=_CN_TZ),
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "amount": row.get("amount"),
                    }
                )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "trade_time": raw["trade_time"],
            "open": to_float(raw.get("open")),
            "high": to_float(raw.get("high")),
            "low": to_float(raw.get("low")),
            "close": to_float(raw.get("close")),
            "volume": to_int(raw.get("volume")),
            "amount": to_float(raw.get("amount")),
        }
