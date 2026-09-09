"""基于 akshare 的新浪 K 线采集器。"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.watchlist import UserWatchlist
from collector.core.base import get_engine
from collector.core.parsing import clean_stock_code
from collector.spiders.kline_base import BaseKlineCollector


async def _fetch_watchlist_codes() -> list[str]:
    """默认采集范围：全部自选股代码去重升序；空集返回空列表（跳过采集）。"""
    session_maker = async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        rows = await session.execute(
            select(UserWatchlist.stock_code)
            .distinct()
            .order_by(UserWatchlist.stock_code)
        )
        return [row[0] for row in rows.all()]


class SinaKlineCollector(BaseKlineCollector):
    """新浪财经日 K / 分钟 K 数据采集器。"""

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or await _fetch_watchlist_codes()
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            sina_symbol = self._to_sina_symbol(symbol)
            if self.period == "minute":
                df = ak.stock_zh_a_minute(symbol=sina_symbol, period="1")
                date_col = "day"
            else:
                df = ak.stock_zh_a_daily(symbol=sina_symbol)
                date_col = "date"

            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": symbol,
                        "trade_date": row[date_col],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "amount": row.get("amount"),
                        "amplitude": None,
                        "change_pct": None,
                        "turnover_rate": row.get("turnover"),
                    }
                )

        return raw

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        """将 6 位股票代码转换为 Sina 格式（sh/sz）。"""
        code = clean_stock_code(symbol)
        prefix = "sh" if code.startswith("6") else "sz"
        return f"{prefix}{code}"
