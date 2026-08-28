"""基于 akshare 的沪深交易所官方成交额采集器。

上交所 stock_sse_deal_daily（成交金额单位：亿元）+ 深交所 stock_szse_summary
（成交金额单位：元）合并为两市成交额（元），按交易日 upsert 到
``market_amount``。官方数据盘后发布，调度在 15:40/16:40/17:40 多次重试；
数据未发布或非交易日返回空列表。
"""

from datetime import date, datetime
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from collector.core.base import PostgresCollector

_CN_TZ = ZoneInfo("Asia/Shanghai")


class ExchangeMarketAmountCollector(PostgresCollector):
    """沪深交易所官方成交额采集器，写入 market_amount（每交易日一行）。"""

    table = "market_amount"
    conflict_key = "trade_date"
    update_columns: ClassVar[list[str]] = ["amount", "source"]
    update_skip_null = True
    key_fields: ClassVar[list[str]] = ["trade_date"]
    required_fields: ClassVar[list[str]] = ["trade_date", "amount"]

    async def collect(
        self, trade_date: date | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        target = trade_date or datetime.now(_CN_TZ).date()
        day = target.strftime("%Y%m%d")
        try:
            sse = ak.stock_sse_deal_daily(date=day)
            szse = ak.stock_szse_summary(date=day)
            sse_amount = float(sse.loc[sse["单日情况"] == "成交金额", "股票"].iloc[0])
            szse_amount = float(
                szse.loc[szse["证券类别"] == "股票", "成交金额"].iloc[0]
            )
        except Exception:  # noqa: BLE001 - 官方数据未发布时接口抛错/返回空
            return []

        return [
            {
                "trade_date": target,
                "amount": sse_amount * 1e8 + szse_amount,
                "source": "exchange",
            }
        ]
