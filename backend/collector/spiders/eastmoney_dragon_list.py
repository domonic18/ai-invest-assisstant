"""EastMoney dragon list (lhb) collector via akshare."""

from datetime import date
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.parsing import (
    parse_cn_amount,
    parse_date,
    to_float,
    to_optional_str,
)


class EastMoneyDragonListCollector(PostgresCollector):
    """东方财富龙虎榜采集器，写入 dragon_list。"""

    table = "dragon_list"
    conflict_key = "trade_date, stock_code, rank_reason"
    key_fields: ClassVar[list[str]] = ["trade_date", "stock_code", "rank_reason"]
    required_fields: ClassVar[list[str]] = ["trade_date", "stock_code"]

    async def collect(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        end = parse_date(end_date) or date.today()
        start = parse_date(start_date) or end
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        df = ak.stock_lhb_detail_em(start_date=start_str, end_date=end_str)
        raw: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            reason = to_optional_str(_find_col(row, ["解读", "上榜原因", "异动原因"]))
            if reason and len(reason) > 500:
                reason = reason[:500]
            raw.append(
                {
                    "trade_date": parse_date(_find_col(row, ["上榜日", "交易日期"])),
                    "stock_code": to_optional_str(_find_col(row, ["代码", "股票代码"])),
                    "stock_name": to_optional_str(_find_col(row, ["名称", "股票简称"])),
                    "rank_reason": reason,
                    "close_price": to_float(_find_col(row, ["收盘价"])),
                    "change_pct": to_float(_find_col(row, ["涨跌幅"])),
                    "net_buy_amount": parse_cn_amount(
                        _find_col(row, ["龙虎榜净买额", "净买额"])
                    ),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "trade_date": raw["trade_date"],
            "stock_code": str(raw["stock_code"]),
            "stock_name": raw.get("stock_name"),
            "rank_reason": raw.get("rank_reason"),
            "close_price": raw.get("close_price"),
            "change_pct": raw.get("change_pct"),
            "net_buy_amount": raw.get("net_buy_amount"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(item.get("trade_date") and item.get("stock_code"))


def _find_col(row: Any, candidates: list[str]) -> Any:
    for col in candidates:
        try:
            return row[col]
        except KeyError:
            continue
    return None
