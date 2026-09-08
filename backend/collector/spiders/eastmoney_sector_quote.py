"""东方财富行业/概念板块行情快照采集器。

push2delay clist（行业 ``m:90+t:2`` / 概念 ``m:90+t:3``）收盘后快照自积累：
价格/涨跌幅/成交额/换手率/涨跌家数/领涨股。WAF 约束同
``eastmoney_concept_constituents``（Chrome 指纹 + push2delay 镜像，
行情 15 分钟延迟对收盘快照无影响）。
"""

import math
import time
from datetime import date
from typing import Any, ClassVar

import structlog

from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.calendar import latest_trading_day
from collector.core.http_client import eastmoney_get_chrome
from collector.core.parsing import to_float, to_int, to_optional_str

logger = structlog.get_logger(__name__)

_CLIST_URL = "https://push2delay.eastmoney.com/api/qt/clist/get"
# f12 代码 f14 名称 f2 最新价 f3 涨跌幅 f6 成交额 f8 换手率
# f104 上涨家数 f105 下跌家数 f128 领涨股
_FIELDS = "f12,f14,f2,f3,f6,f8,f104,f105,f128"
_PAGE_SIZE = 500
_SECTOR_FS: dict[str, str] = {"industry": "m:90+t:2", "concept": "m:90+t:3"}


def fetch_sector_page(fs: str, page: int) -> dict[str, Any]:
    """拉取一页板块 clist（data 节点，含 total/diff）。"""
    response = eastmoney_get_chrome(
        _CLIST_URL,
        params={
            "pn": str(page),
            "pz": str(_PAGE_SIZE),
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f12",
            "fs": fs,
            "fields": _FIELDS,
            "_": int(time.time() * 1000),
        },
    )
    return response.json().get("data") or {}


def fetch_sector_rows(fs: str) -> list[dict[str, Any]]:
    """分页拉取板块全量记录。"""
    data = fetch_sector_page(fs, 1)
    rows: list[dict[str, Any]] = list(data.get("diff") or [])
    total = int(data.get("total") or 0)
    for page in range(2, math.ceil(total / _PAGE_SIZE) + 1):
        rows.extend(fetch_sector_page(fs, page).get("diff") or [])
    return rows


def transform_sector_row(
    row: dict[str, Any], sector_type: str, trade_date: date
) -> dict[str, Any] | None:
    """clist 行 -> quote_sector_daily 行；代码/名称缺失跳过，`-` 置 None。"""
    sector_code = to_optional_str(row.get("f12"))
    sector_name = to_optional_str(row.get("f14"))
    if not sector_code or not sector_name:
        return None
    leader = to_optional_str(row.get("f128"))
    return {
        "sector_type": sector_type,
        "sector_code": sector_code,
        "sector_name": sector_name,
        "trade_date": trade_date,
        "close": to_float(row.get("f2")),
        "change_pct": to_float(row.get("f3")),
        "amount": to_float(row.get("f6")),
        "turnover_rate": to_float(row.get("f8")),
        "up_count": to_int(row.get("f104")),
        "down_count": to_int(row.get("f105")),
        "leader_stock_name": None if leader == "-" else leader,
        "source": "eastmoney",
    }


class EastmoneySectorQuoteCollector(PostgresCollector):
    """行业/概念板块收盘快照，写入 quote_sector_daily。"""

    table = "quote_sector_daily"
    conflict_key = "sector_type, sector_code, trade_date"
    update_columns: ClassVar[list[str]] = [
        "sector_name",
        "close",
        "change_pct",
        "amount",
        "turnover_rate",
        "up_count",
        "down_count",
        "leader_stock_name",
        "source",
    ]
    normalize = False
    key_fields: ClassVar[list[str]] = ["sector_type", "sector_code", "trade_date"]
    required_fields: ClassVar[list[str]] = [
        "sector_type",
        "sector_code",
        "sector_name",
        "trade_date",
    ]

    async def collect(
        self, trade_date: date | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        target = trade_date or latest_trading_day()
        return await run_in_thread(self._collect_sync, target)

    def _collect_sync(self, trade_date: date) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for sector_type, fs in _SECTOR_FS.items():
            fetched = fetch_sector_rows(fs)
            rows.extend(
                transformed
                for row in fetched
                if (transformed := transform_sector_row(row, sector_type, trade_date))
            )
            logger.info(
                "eastmoney_sector_quote_fetched",
                sector_type=sector_type,
                count=len(fetched),
            )
        return rows
