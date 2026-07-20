"""EastMoney limit-up pool collector via akshare.

Fetches the daily 涨停股池 (stock_zt_pool_em) and stores it into
``limit_up_pool`` for the daily-review dashboard (涨停板 / 连板天梯).
"""

from datetime import date
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.calendar import is_trading_day, latest_trading_day
from collector.core.parsing import to_float, to_optional_str

_UPDATE_COLUMNS = [
    "stock_name",
    "change_pct",
    "latest_price",
    "turnover_rate",
    "sealed_amount",
    "first_seal_time",
    "last_seal_time",
    "break_count",
    "limit_stat",
    "consecutive_boards",
    "industry",
    "source",
]


class EastMoneyLimitUpPoolCollector(PostgresCollector):
    """东方财富涨停股池采集器，写入 limit_up_pool。"""

    table = "limit_up_pool"
    conflict_key = "trade_date, stock_code"
    update_skip_null = True
    update_columns: ClassVar[list[str]] = _UPDATE_COLUMNS
    key_fields: ClassVar[list[str]] = ["trade_date", "stock_code"]
    required_fields: ClassVar[list[str]] = ["trade_date", "stock_code"]

    async def collect(
        self, trade_date: date | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        target = trade_date or latest_trading_day()
        if not is_trading_day(target):
            # 非交易日接口会返回最近交易日数据，直接落库会把日期张冠李戴
            return []
        try:
            df = ak.stock_zt_pool_em(date=target.strftime("%Y%m%d"))
        except Exception:  # noqa: BLE001
            # 非交易日或接口无数据时 akshare 可能直接抛错，视为空结果
            return []
        if df is None or df.empty:
            return []

        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            raw.append(
                {
                    "trade_date": target,
                    "stock_code": to_optional_str(row.get("代码")),
                    "stock_name": to_optional_str(row.get("名称")),
                    "change_pct": to_float(row.get("涨跌幅")),
                    "latest_price": to_float(row.get("最新价")),
                    "turnover_rate": to_float(row.get("换手率")),
                    "sealed_amount": to_float(row.get("封板资金")),
                    "first_seal_time": to_optional_str(row.get("首次封板时间")),
                    "last_seal_time": to_optional_str(row.get("最后封板时间")),
                    "break_count": _to_int(row.get("炸板次数")),
                    "limit_stat": to_optional_str(row.get("涨停统计")),
                    "consecutive_boards": _to_int(row.get("连板数")),
                    "industry": to_optional_str(row.get("所属行业")),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "trade_date": raw["trade_date"],
            "stock_code": str(raw["stock_code"]),
            "stock_name": raw.get("stock_name"),
            "change_pct": raw.get("change_pct"),
            "latest_price": raw.get("latest_price"),
            "turnover_rate": raw.get("turnover_rate"),
            "sealed_amount": raw.get("sealed_amount"),
            "first_seal_time": raw.get("first_seal_time"),
            "last_seal_time": raw.get("last_seal_time"),
            "break_count": raw.get("break_count"),
            "limit_stat": raw.get("limit_stat"),
            "consecutive_boards": raw.get("consecutive_boards"),
            "industry": raw.get("industry"),
            "source": "eastmoney",
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(item.get("trade_date") and item.get("stock_code"))


def _to_int(value: Any) -> int | None:
    """容错转 int（兼容 float 形式），失败返回 None。"""
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
