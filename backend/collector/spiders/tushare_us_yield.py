"""Tushare 美债收益率采集器（us_tycr）。

us_tycr 无 ts_code 参数，单次调用返回全量历史（date/y1..y30 列，单位 %）。
按 :data:`GLOBAL_INDEX_CODES` 中 tushare 源的 field 映射展开（y2→US2Y、
y10→US10Y）写入 quote_global_index_daily。收益率为单点报价（无 OHLC），
仅写 close；change_pct 存相邻交易日涨跌幅（%），与表内其他来源口径一致。
"""

from typing import Any, ClassVar

from app.core.constants import GLOBAL_INDEX_CODES
from collector.core.base import PostgresCollector
from collector.core.parsing import parse_date, to_float


class TushareUsYieldCollector(PostgresCollector):
    """Tushare 美债收益率采集器，写入 quote_global_index_daily。"""

    table = "quote_global_index_daily"
    conflict_key = "index_code, trade_date"
    update_columns: ClassVar[list[str]] = ["close", "change_pct", "source"]
    # 全历史重跑时保留已有值：个别十档当日缺数不回填 NULL
    update_skip_null = True
    normalize = False
    key_fields: ClassVar[list[str]] = ["index_code", "trade_date"]
    required_fields: ClassVar[list[str]] = ["index_code", "trade_date", "close"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import tushare as ts

        if not self.api_key:
            raise ValueError("tushare channel api_key (token) is required")

        field_map = {
            code: meta["field"]
            for code, meta in GLOBAL_INDEX_CODES.items()
            if meta["data_source"] == "tushare"
        }
        if symbols:
            requested = set(symbols)
            field_map = {c: f for c, f in field_map.items() if c in requested}
        if not field_map:
            return []

        pro = ts.pro_api(self.api_key)
        df = pro.us_tycr()
        if df is None or df.empty:
            return []
        df = df.sort_values("date")

        items: list[dict[str, Any]] = []
        for code, field in field_map.items():
            if field not in df.columns:
                raise ValueError(f"us_tycr 返回缺少字段 {field}（{code}）")
            prev: float | None = None
            for _, row in df.iterrows():
                trade_date = parse_date(str(row.get("date"))[:10])
                if trade_date is None:
                    continue
                close = to_float(row.get(field))
                if close is None:
                    # 个别十档当日缺数：断开涨跌幅连差基准
                    prev = None
                    continue
                change_pct = (
                    round((close - prev) / prev * 100, 4) if prev is not None else None
                )
                items.append(
                    {
                        "index_code": code,
                        "trade_date": trade_date,
                        "close": close,
                        "change_pct": change_pct,
                        "source": "tushare",
                    }
                )
                prev = close
        return items
