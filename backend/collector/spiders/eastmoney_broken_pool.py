"""基于 akshare 的东财炸板池采集器。

抓取东财炸板池（stock_zt_pool_zbgc_em），将炸板家数按交易日 upsert 到
``market_breadth.broken_limit_count``——与 sina_market_breadth 共写一张表，
各自更新不同列子集。无数据即抛错的接口，异常时返回空列表。
"""

from datetime import date
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.calendar import is_trading_day, latest_trading_day


class EastmoneyBrokenPoolCollector(PostgresCollector):
    """东财炸板池采集器，写 market_breadth.broken_limit_count。"""

    table = "market_breadth"
    conflict_key = "trade_date"
    update_columns: ClassVar[list[str]] = ["broken_limit_count"]
    update_skip_null = True
    key_fields: ClassVar[list[str]] = ["trade_date"]
    required_fields: ClassVar[list[str]] = ["trade_date", "broken_limit_count"]

    async def collect(
        self, trade_date: date | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        target = trade_date or latest_trading_day()
        if not is_trading_day(target):
            # 非交易日接口会返回最近交易日数据，直接落库会把日期张冠李戴
            return []
        try:
            df = ak.stock_zt_pool_zbgc_em(date=target.strftime("%Y%m%d"))
        except Exception:  # noqa: BLE001 - 非交易日/无数据时接口抛错
            return []
        if df is None:
            return []
        return [{"trade_date": target, "broken_limit_count": len(df)}]
