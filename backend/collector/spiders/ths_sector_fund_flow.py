"""THS (10jqka) sector fund flow collector — 东财板块资金流的备用渠道。

同花顺行业资金流（data.10jqka.com.cn/funds/hyzjl）与东财口径不同：
无板块代码（以行业名代替）、无超/大/中/小单拆分（写 NULL）、仅支持行业
板块。通过 akshare.stock_fund_flow_industry 获取（hexin-v 签名由 akshare
内置处理）。写入与东财采集器相同的 sector_fund_flow 表。
"""

from datetime import date
from decimal import Decimal
from typing import Any

from collector.core.parsing import is_nan, parse_cn_amount, to_optional_str
from collector.spiders.sector_fund_flow_base import BaseSectorFundFlowCollector


class ThsSectorFundFlowCollector(BaseSectorFundFlowCollector):
    """同花顺行业资金流向采集器（备用渠道），写入 sector_fund_flow。"""

    async def collect(
        self, sector_type: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        sector_type = sector_type or self.sector_type
        if sector_type != "industry":
            raise ValueError(f"同花顺渠道仅支持行业板块资金流，不支持: {sector_type}")

        import akshare as ak  # type: ignore[import-untyped]

        df = ak.stock_fund_flow_industry(symbol="即时")
        if df is None or df.empty:
            return []
        trade_date = date.today()
        raw: list[dict[str, Any]] = []
        for row in df.to_dict(orient="records"):
            sector_name = to_optional_str(row.get("行业"))
            raw.append(
                {
                    "sector_code": sector_name,
                    "sector_name": sector_name,
                    "sector_type": "industry",
                    "trade_date": trade_date,
                    "change_pct": _parse_pct(row.get("行业-涨跌幅")),
                    "main_net_inflow": _parse_net_amount(row.get("净额")),
                    "super_large_net": None,
                    "large_net": None,
                    "medium_net": None,
                    "small_net": None,
                    "top_stock_code": None,
                    "top_stock_name": to_optional_str(row.get("领涨股")),
                }
            )
        return raw


def _parse_pct(value: Any) -> float | None:
    """同花顺涨跌幅：数值或带 % 的字符串。"""
    if value is None or is_nan(value):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return parse_cn_amount(str(value).strip().rstrip("%"))


def _parse_net_amount(value: Any) -> float | None:
    """同花顺净额：数值单位为亿元（需换算为元），字符串可能带中文单位。"""
    if value is None or is_nan(value):
        return None
    if isinstance(value, Decimal):
        return float(value) * 100_000_000
    if isinstance(value, (int, float)):
        return float(value) * 100_000_000
    return parse_cn_amount(value)
