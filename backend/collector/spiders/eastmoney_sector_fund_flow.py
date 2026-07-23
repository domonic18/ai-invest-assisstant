"""EastMoney sector fund flow collector.

东财 push2 接口要求携带 Referer 头（缺失时直接断开连接），akshare 的请求
未携带会被拒绝，因此这里直接请求接口，字段口径与
akshare.stock_sector_fund_flow_rank（indicator="今日"）一致。
"""

import math
import time
from datetime import date
from typing import Any, ClassVar

from collector.core.calendar import is_trading_day, latest_trading_day
from collector.core.http_client import eastmoney_get
from collector.core.parsing import parse_cn_amount, to_float, to_optional_str
from collector.spiders.sector_fund_flow_base import BaseSectorFundFlowCollector

_PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"
_PAGE_SIZE = 100
# f12 板块代码 f14 名称 f3 涨跌幅 f62 主力净额 f66 超大单 f72 大单
# f78 中单 f84 小单 f204 主力净流入最大股 f205 最大股代码
_FIELDS = "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124"

# 单板块资金流日 K（历史补采）：f51 日期 f52 主力净额 f53 小单 f54 中单
# f55 大单 f56 超大单 f63 涨跌幅（字段顺序即 klines CSV 列顺序）
_DAYKLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
_DAYKLINE_FIELDS = "f51,f52,f53,f54,f55,f56,f63"


class EastMoneySectorFundFlowCollector(BaseSectorFundFlowCollector):
    """东方财富板块资金流向采集器，写入 capital_fund_flow_sector。"""

    SECTOR_TYPE_MAP: ClassVar[dict[str, str]] = {
        "industry": "2",
        "concept": "3",
        "region": "1",
    }

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
        self,
        sector_type: str | None = None,
        trade_date: date | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        sector_type = sector_type or self.sector_type
        if trade_date is not None:
            return self._collect_history(sector_type, trade_date)
        rows = self._fetch_rank(sector_type)
        trade_date = latest_trading_day()
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

    def _fetch_daykline(self, sector_code: str) -> list[str]:
        """单板块资金流日 K（CSV 行，列序见 _DAYKLINE_FIELDS）。"""
        response = eastmoney_get(
            _DAYKLINE_URL,
            params={
                "secid": f"90.{sector_code}",
                "fields1": "f1,f2,f3,f7",
                "fields2": _DAYKLINE_FIELDS,
                "lmt": 0,
            },
        )
        data = response.json().get("data") or {}
        return list(data.get("klines") or [])

    def _collect_history(
        self, sector_type: str, trade_date: date
    ) -> list[dict[str, Any]]:
        """补采历史交易日：逐板块取资金流日 K 中目标日期的一行。

        领涨股（top_stock_*）无历史来源，置 None；upsert 的 update_skip_null
        保证不会覆盖快照已写入的值。
        """
        if not is_trading_day(trade_date):
            return []
        target = trade_date.isoformat()
        raw: list[dict[str, Any]] = []
        for row in self._fetch_rank(sector_type):
            sector_code = to_optional_str(row.get("f12"))
            sector_name = to_optional_str(row.get("f14"))
            if not sector_code or not sector_name:
                continue
            for kline in self._fetch_daykline(sector_code):
                parts = kline.split(",")
                if len(parts) < 7 or parts[0] != target:
                    continue
                raw.append(
                    {
                        "sector_code": sector_code,
                        "sector_name": sector_name,
                        "sector_type": sector_type,
                        "trade_date": trade_date,
                        "change_pct": to_float(parts[6]),
                        "main_net_inflow": to_float(parts[1]),
                        "super_large_net": to_float(parts[5]),
                        "large_net": to_float(parts[4]),
                        "medium_net": to_float(parts[3]),
                        "small_net": to_float(parts[2]),
                        "top_stock_code": None,
                        "top_stock_name": None,
                    }
                )
                break
        return raw
