"""TongHuaShun K-line collector via akshare."""

from typing import Any

from collector.spiders.kline_base import BaseKlineCollector


class ThsKlineCollector(BaseKlineCollector):
    """同花顺日 K / 分钟 K 数据采集器。"""

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        symbols = symbols or ["000001"]
        raw: list[dict[str, Any]] = []

        for symbol in symbols:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="20240101",
                end_date="20251231",
                adjust="qfq",
            )
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                raw.append(
                    {
                        "stock_code": symbol,
                        "trade_date": row["日期"],
                        "open": row["开盘"],
                        "high": row["最高"],
                        "low": row["最低"],
                        "close": row["收盘"],
                        "volume": row["成交量"],
                        "amount": row["成交额"],
                        "amplitude": row["振幅"],
                        "change_pct": row["涨跌幅"],
                        "turnover_rate": row.get("换手率"),
                    }
                )

        return raw
