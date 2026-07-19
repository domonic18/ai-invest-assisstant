"""EastMoney sector fund flow collector.

东财 push2 接口要求携带 Referer 头（缺失时直接断开连接），akshare 的请求
未携带会被拒绝，因此这里直接请求接口，字段口径与
akshare.stock_sector_fund_flow_rank（indicator="今日"）一致。
"""

import math
import time
from datetime import date
from typing import Any, ClassVar

from collector.core.base import PostgresCollector
from collector.core.http_client import eastmoney_get
from collector.core.parsing import parse_cn_amount, to_optional_str

_PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"
_PAGE_SIZE = 100
# f12 板块代码 f14 名称 f3 涨跌幅 f62 主力净额 f66 超大单 f72 大单
# f78 中单 f84 小单 f204 主力净流入最大股 f205 最大股代码
_FIELDS = "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124"

_UPDATE_COLUMNS = [
    "sector_name",
    "change_pct",
    "main_net_inflow",
    "super_large_net",
    "large_net",
    "medium_net",
    "small_net",
    "top_stock_code",
    "top_stock_name",
]


class EastMoneySectorFundFlowCollector(PostgresCollector):
    """东方财富板块资金流向采集器，写入 sector_fund_flow。"""

    SECTOR_TYPE_MAP: dict[str, str] = {
        "industry": "2",
        "concept": "3",
        "region": "1",
    }

    table = "sector_fund_flow"
    conflict_key = "sector_code, sector_type, trade_date"
    update_skip_null = True
    update_columns: ClassVar[list[str]] = _UPDATE_COLUMNS
    key_fields: ClassVar[list[str]] = ["sector_code", "sector_type", "trade_date"]
    required_fields: ClassVar[list[str]] = ["sector_code", "sector_name", "trade_date"]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.sector_type = config.get("sector_type", "industry")

    def _request_page(self, params: dict[str, Any]) -> dict[str, Any]:
        response = eastmoney_get(_PUSH2_URL, params=params)
        return response.json().get("data") or {}

    def _fetch_rank(self, sector_type: str) -> list[dict[str, Any]]:
        """分页拉取板块资金流排名（今日）。"""
        params: dict[str, Any] = {
            "pn": 1,
            "pz": _PAGE_SIZE,
            "po": 1,
            "np": 1,
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "fltt": 2,
            "invt": 2,
            "fid0": "f62",
            "fs": f"m:90 t:{self.SECTOR_TYPE_MAP.get(sector_type, '2')}",
            "stat": 1,
            "fields": _FIELDS,
            "rt": 52975239,
            "_": int(time.time() * 1000),
        }
        data = self._request_page(params)
        total = int(data.get("total") or 0)
        rows = list(data.get("diff") or [])
        for page in range(2, math.ceil(total / _PAGE_SIZE) + 1):
            params["pn"] = page
            rows.extend(self._request_page(params).get("diff") or [])
        return rows

    async def collect(
        self, sector_type: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        sector_type = sector_type or self.sector_type
        rows = self._fetch_rank(sector_type)
        trade_date = date.today()
        raw: list[dict[str, Any]] = []
        for row in rows:
            sector_name = to_optional_str(row.get("f14"))
            raw.append(
                {
                    "sector_code": to_optional_str(row.get("f12")) or sector_name,
                    "sector_name": sector_name,
                    "sector_type": sector_type,
                    "trade_date": trade_date,
                    "change_pct": parse_cn_amount(row.get("f3")),
                    "main_net_inflow": parse_cn_amount(row.get("f62")),
                    "super_large_net": parse_cn_amount(row.get("f66")),
                    "large_net": parse_cn_amount(row.get("f72")),
                    "medium_net": parse_cn_amount(row.get("f78")),
                    "small_net": parse_cn_amount(row.get("f84")),
                    "top_stock_code": to_optional_str(row.get("f205")),
                    "top_stock_name": to_optional_str(row.get("f204")),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "sector_code": str(raw["sector_code"]),
            "sector_name": raw.get("sector_name"),
            "sector_type": raw.get("sector_type"),
            "trade_date": raw["trade_date"],
            "change_pct": raw.get("change_pct"),
            "main_net_inflow": raw.get("main_net_inflow"),
            "super_large_net": raw.get("super_large_net"),
            "large_net": raw.get("large_net"),
            "medium_net": raw.get("medium_net"),
            "small_net": raw.get("small_net"),
            "top_stock_code": raw.get("top_stock_code"),
            "top_stock_name": raw.get("top_stock_name"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("sector_code")
            and item.get("sector_name")
            and item.get("trade_date")
        )


# 兼容别名：具体实现见 collector/core/parsing.py
_str = to_optional_str
_parse_amount = parse_cn_amount
