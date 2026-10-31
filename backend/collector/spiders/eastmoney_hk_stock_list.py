"""东方财富港股全市场列表采集器。

push2 clist 分页拉取港股全市场代码/名称/行业，upsert 到
``stock_basic``（market='hk'，代码为 5 位零填充）。fs 取 ``m:116+t:3``
（东财「港股」页签口径，约 2600 只正股，含 RMB 柜台）；不带 t:3 的
``m:116`` 会混入 1.5 万+ 权证/牛熊证，污染搜索联想。只增不删：退市/改名
不影响既有行；``update_skip_null`` 确保不用 NULL 覆盖已有值。
"""

import math
import time
from typing import Any, ClassVar

import structlog
from curl_cffi.requests import exceptions as cffi_exceptions

from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.http_client import eastmoney_get_chrome
from collector.core.parsing import to_optional_str
from collector.spiders.eastmoney_common import push2_base_url

logger = structlog.get_logger(__name__)

_CLIST_PATH = "/api/qt/clist/get"
_PAGE_SIZE = 100
_FS_HK_STOCKS = "m:116+t:3"
# f12 代码（5 位零填充） f14 名称 f100 东财行业
_FIELDS = "f12,f14,f100"
# push2 clist 分页连发会触发主机级限流（curl 56 连接被重置）：页间留额外间隔，
# 单页失败按指数退避重试，避免一页抖动整轮全市场拉取作废
_PAGE_INTERVAL_SECONDS = 0.5
_PAGE_RETRY_ATTEMPTS = 3
_PAGE_RETRY_BACKOFF_SECONDS = 2.0


class EastmoneyHkStockListCollector(PostgresCollector):
    """港股全市场列表采集器，回写 stock_basic（market='hk'）。"""

    table = "stock_basic"
    conflict_key = "stock_code, market"
    update_skip_null = True
    update_columns: ClassVar[list[str]] = ["stock_name", "industry_level_1"]
    required_fields: ClassVar[list[str]] = ["stock_code", "stock_name", "market"]

    def _request_page(self, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{push2_base_url(self.config)}{_CLIST_PATH}"
        last_exc: Exception | None = None
        for attempt in range(_PAGE_RETRY_ATTEMPTS):
            try:
                response = eastmoney_get_chrome(url, params=params)
                return response.json().get("data") or {}
            except cffi_exceptions.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "hk_stock_list_page_retry",
                    page=params.get("pn"),
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt + 1 < _PAGE_RETRY_ATTEMPTS:
                    time.sleep(_PAGE_RETRY_BACKOFF_SECONDS * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    def _fetch_all(self) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "pn": 1,
            "pz": _PAGE_SIZE,
            "po": 1,
            "np": 1,
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "fltt": 2,
            "invt": 2,
            "fid": "f12",
            "fs": _FS_HK_STOCKS,
            "fields": _FIELDS,
            "_": int(time.time() * 1000),
        }
        data = self._request_page(params)
        total = int(data.get("total") or 0)
        rows = list(data.get("diff") or [])
        for page in range(2, math.ceil(total / _PAGE_SIZE) + 1):
            time.sleep(_PAGE_INTERVAL_SECONDS)
            params["pn"] = page
            rows.extend(self._request_page(params).get("diff") or [])
        return rows

    async def collect(
        self, symbols: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        requested = {str(s).strip().zfill(5) for s in symbols} if symbols else None
        rows = await run_in_thread(self._fetch_all, timeout=180)

        seen: set[str] = set()
        raw: list[dict[str, Any]] = []
        for row in rows:
            code = to_optional_str(row.get("f12"))
            if not code:
                continue
            code = code.zfill(5)
            if requested and code not in requested:
                continue
            if code in seen:
                continue
            seen.add(code)
            raw.append(
                {
                    "stock_code": code,
                    "stock_name": to_optional_str(row.get("f14")) or code,
                    "market": "hk",
                    "industry_level_1": to_optional_str(row.get("f100")),
                }
            )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "stock_name": str(raw["stock_name"]),
            "market": "hk",
            "industry_level_1": raw.get("industry_level_1"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("stock_code") and item.get("stock_name") and item.get("market")
        )
