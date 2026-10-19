"""东方财富港股日 K 采集器。

push2his ``/api/qt/stock/kline/get``（secid=116.{code}，klt=101，fqt=1 前复权）
逐股拉取日 K，写 quote_kline_stock_daily。缺省宇宙 = stock_basic 全部
market='hk' 股票；全市场约 2600 股 × 全局限速 1s，单轮约 45 分钟，
走 heavy 队列。push2his 无公开镜像（见 eastmoney_common.py）。
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.stock import StockBasic
from collector.core.async_helpers import run_in_thread
from collector.core.base import get_engine
from collector.core.http_client import eastmoney_get_chrome
from collector.core.parsing import parse_date
from collector.spiders.kline_base import BaseKlineCollector

_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
# klines CSV 列序：f51 日期 f52 开 f53 收 f54 高 f55 低 f56 成交量
# f57 成交额 f58 振幅 f59 涨跌幅 f60 换手率
_KLINE_FIELDS = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60"


async def _fetch_hk_codes() -> list[str]:
    """缺省采集范围：stock_basic 全部港股代码去重升序。"""
    session_maker = async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        rows = await session.execute(
            select(StockBasic.stock_code)
            .where(StockBasic.market == "hk")
            .distinct()
            .order_by(StockBasic.stock_code)
        )
        return [row[0] for row in rows.all()]


class EastmoneyHkKlineCollector(BaseKlineCollector):
    """东方财富港股日 K 采集器（前复权）。"""

    async def collect(
        self,
        symbols: list[str] | None = None,
        lookback_days: int | None = 5,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        symbols = symbols or await _fetch_hk_codes()
        beg = _beg_date(lookback_days)
        raw: list[dict[str, Any]] = []
        for symbol in symbols:
            code = str(symbol).strip().zfill(5)
            rows = await run_in_thread(self._fetch_kline, code, beg)
            raw.extend(rows)
        return raw

    def _fetch_kline(self, code: str, beg: str) -> list[dict[str, Any]]:
        response = eastmoney_get_chrome(
            _KLINE_URL,
            params={
                "secid": f"116.{code}",
                "klt": 101,
                "fqt": 1,
                "beg": beg,
                "end": 20500101,
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": _KLINE_FIELDS,
            },
        )
        data = response.json().get("data") or {}
        rows: list[dict[str, Any]] = []
        for line in data.get("klines") or []:
            parts = str(line).split(",")
            if len(parts) < len(_KLINE_FIELDS.split(",")):
                continue
            rows.append(
                {
                    "stock_code": code,
                    "trade_date": parse_date(parts[0]),
                    "open": parts[1],
                    "close": parts[2],
                    "high": parts[3],
                    "low": parts[4],
                    "volume": parts[5],
                    "amount": parts[6],
                    "amplitude": parts[7],
                    "change_pct": parts[8],
                    "turnover_rate": parts[9],
                }
            )
        return rows


def _beg_date(lookback_days: int | None) -> str:
    """lookback 换算为 beg 日期串（YYYYMMDD）；None/非法值回退 5 天。"""
    try:
        days = max(int(lookback_days), 1)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        days = 5
    now = datetime.now(timezone.utc).date()
    return (now - timedelta(days=days)).strftime("%Y%m%d")
