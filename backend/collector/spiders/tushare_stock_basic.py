"""Tushare 股本数据采集器。

新浪交易所名单不含沪市股本（SSE 接口无股本列），沪市股票 total_shares
长期为 NULL，导致行情快照市值无法计算。tushare ``stock_basic`` 不含股本
字段，股本取自 ``daily_basic`` 每日指标（total_share/float_share，单位：
万股），按最近交易日取全市场快照回写，接口无数据时向前回退交易日。
"""

from datetime import timedelta
from typing import Any, ClassVar

import structlog

from collector.core.base import PostgresCollector
from collector.core.calendar import latest_trading_day

logger = structlog.get_logger(__name__)

_MARKET_BY_SUFFIX = {".SH": "sh", ".SZ": "sz", ".BJ": "bj"}
# tushare 股本单位为万股
_SHARE_UNIT = 10000
# daily_basic 当日数据可能延迟发布，按交易日向前回退的最大次数
_MAX_LOOKBACK_DAYS = 5


class TushareStockBasicCollector(PostgresCollector):
    """Tushare 全市场股本采集器，回写 stock_basic 的 total_shares/circulating_shares。"""

    table = "stock_basic"
    conflict_key = "stock_code, market"
    update_skip_null = True
    update_columns: ClassVar[list[str]] = ["total_shares", "circulating_shares"]
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "market"]
    required_fields: ClassVar[list[str]] = ["stock_code", "stock_name", "market"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import tushare as ts  # type: ignore[import-untyped]

        if not self.api_key:
            raise ValueError("tushare channel api_key (token) is required")

        pro = ts.pro_api(self.api_key)
        requested = None
        if symbols:
            requested = {code.strip().zfill(6) for code in symbols}

        df = await self._fetch_daily_basic(pro)
        if df is None or df.empty:
            return []

        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code") or "")
            stock_code = ts_code[:6]
            if requested and stock_code not in requested:
                continue
            market = _MARKET_BY_SUFFIX.get(ts_code[-3:])
            if market is None:
                continue
            raw.append(
                {
                    "stock_code": stock_code,
                    # daily_basic 无名称列；此字段仅为过 required_fields 校验，
                    # 不在 update_columns 中，不会覆盖库中已有名称
                    "stock_name": stock_code,
                    "market": market,
                    "total_shares": _to_shares(row.get("total_share")),
                    "circulating_shares": _to_shares(row.get("float_share")),
                }
            )
        return raw

    async def _fetch_daily_basic(self, pro: Any) -> Any:
        """按最近交易日拉全市场股本快照；当日未发布时向前回退。"""
        day = latest_trading_day()
        df = None
        for _ in range(_MAX_LOOKBACK_DAYS):
            df = pro.daily_basic(
                trade_date=day.strftime("%Y%m%d"),
                fields="ts_code,total_share,float_share",
            )
            if df is not None and not df.empty:
                return df
            day = latest_trading_day(day - timedelta(days=1))
        return df


def _to_shares(value: Any) -> int | None:
    """万股 → 股；缺失返回 None（update_skip_null 保留库中原值）。"""
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
        return int(float(value) * _SHARE_UNIT)
    except (TypeError, ValueError):
        return None
