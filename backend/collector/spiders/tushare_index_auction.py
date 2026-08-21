"""Tushare index call-auction amount collector.

指数 9:25 集合竞价成交额 = 成分范围个股 stk_auction（纯 9:25 撮合）合计，
已与同花顺手工记录核对（误差 <0.6%）：

- sh000001 上证指数 = 全部沪市 A 股（60/68 开头）合计
- sh000688 科创50   = 50 只成分股（中证指数官网名单）合计
- sz399006 创业板指 = 全部创业板股票（300/301/302 开头）合计

stk_auction 历史数据自 2025-01 起，盘中 9:26 后可查当日，盘后稳定可查，
是本任务的唯一数据源（新浪分钟线首根 bar 会被盘后立即修订，不可用）。
"""

from datetime import date, datetime
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from collector.core.base import PostgresCollector
from collector.core.parsing import to_float

_CN_TZ = ZoneInfo("Asia/Shanghai")

_CYB_PREFIXES = ("300", "301", "302")
_SSE_PREFIXES = ("60", "68")


class TushareIndexAuctionCollector(PostgresCollector):
    """Tushare 指数集合竞价成交额采集器（成分聚合口径），写入 quote_auction_index。"""

    table = "quote_auction_index"
    conflict_key = "trade_date, index_code"
    # 早间 9:26 拉取时 tushare 可能只返回部分市场（深市滞后），
    # 冲突时覆盖旧值，让 9:27-9:29 重试与 16:35 兜底能纠正不完整数据
    update_columns: ClassVar[list[str]] = ["auction_amount", "source"]
    normalize = False
    key_fields: ClassVar[list[str]] = ["trade_date", "index_code"]
    required_fields: ClassVar[list[str]] = [
        "trade_date",
        "index_code",
        "auction_amount",
    ]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")

    async def collect(
        self,
        symbols: list[str] | None = None,
        trade_date: date | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]
        import tushare as ts

        if not self.api_key:
            raise ValueError("tushare channel api_key (token) is required")

        target = trade_date or datetime.now(_CN_TZ).date()
        requested = set(symbols) if symbols else {"sh000001", "sz399006", "sh000688"}

        pro = ts.pro_api(self.api_key)
        df = pro.stk_auction(trade_date=target.strftime("%Y%m%d"))
        if df is None or df.empty:
            return []
        df = df.assign(amount=df["amount"].map(to_float))

        amounts: dict[str, float | None] = {}
        if "sh000001" in requested:
            mask = df["ts_code"].str[:2].isin(_SSE_PREFIXES)
            amounts["sh000001"] = self._bucket_amount(df, mask)
        if "sz399006" in requested:
            mask = df["ts_code"].str[:3].isin(_CYB_PREFIXES)
            amounts["sz399006"] = self._bucket_amount(df, mask)
        if "sh000688" in requested:
            cons = ak.index_stock_cons_csindex(symbol="000688")
            codes = set(cons["成分券代码"].astype(str))
            mask = df["ts_code"].str[:6].isin(codes)
            amounts["sh000688"] = self._bucket_amount(df, mask)

        return [
            {
                "trade_date": target,
                "index_code": code,
                "auction_amount": amount,
                "source": "tushare",
            }
            for code, amount in amounts.items()
            if amount is not None
        ]

    @staticmethod
    def _bucket_amount(df: Any, mask: Any) -> float | None:
        """聚合桶成交额；桶为空或合计为 0 时返回 None，跳过写入留给后续重试。

        9:26 早间拉取时 tushare 可能只返回部分市场（深市竞价数据滞后），
        空桶求和为 0，若直接写入会被冲突键挡住、重试无法修复。
        """
        if not bool(mask.any()):
            return None
        total = float(df.loc[mask, "amount"].sum())
        return total if total > 0 else None
