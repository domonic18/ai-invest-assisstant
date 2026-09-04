"""东方财富概念板块成分股采集器。

直连东财 clist ``/api/qt/clist/get`` 获取概念列表与每个概念的成分股，写入
mapping_stock_concept 表，供个股详情页展示"包含的概念"。

说明：
- akshare 1.14.17 移除了同花顺概念成分接口后改用东财；东财 WAF 按 TLS
  指纹拦截 requests/httpx，故须走 :func:`eastmoney_get_chrome`。
- 主机用镜像节点 push2delay：push2 对短时高频 clist 连发会按主机封禁
  （连接直接被断开），push2delay 是独立限流桶；其行情 15 分钟延迟对
  成分股映射无影响。
- 单个概念的成员拉取失败不做静默跳过：残缺的成分映射会误导下游
  （个股"包含的概念"缺失），统一抛错让任务重试。
"""

from typing import Any, ClassVar

import structlog

from collector.core.async_helpers import run_in_thread
from collector.core.base import PostgresCollector
from collector.core.http_client import eastmoney_get_chrome
from collector.core.parsing import clean_stock_code, to_optional_str

logger = structlog.get_logger(__name__)

_CLIST_URL = "https://push2delay.eastmoney.com/api/qt/clist/get"
_CONCEPT_FS = "m:90+t:3"  # t:3 = 概念板块
_PAGE_SIZE = 1000


def _fetch_clist(fs: str, fields: str) -> list[dict[str, Any]]:
    """按页拉取 clist 全量记录（单页 pz 足够大时通常仅 1 页）。"""
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
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
                "fields": fields,
            },
        )
        data = response.json().get("data") or {}
        diff: list[dict[str, Any]] = data.get("diff") or []
        rows.extend(diff)
        total = int(data.get("total") or 0)
        if not diff or len(rows) >= total:
            return rows
        page += 1


class EastmoneyConceptConstituentCollector(PostgresCollector):
    """东方财富概念成分股采集器，写入 mapping_stock_concept。"""

    table = "mapping_stock_concept"
    conflict_key = "stock_code, concept_code"
    update_columns: ClassVar[list[str]] = [
        "concept_name",
        "source",
        "updated_at",
    ]
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "concept_code"]
    required_fields: ClassVar[list[str]] = [
        "stock_code",
        "concept_code",
        "concept_name",
    ]

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = await run_in_thread(self._collect_sync)
        return items

    def _collect_sync(self) -> list[dict[str, Any]]:
        try:
            concept_rows = _fetch_clist(_CONCEPT_FS, "f12,f14")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"获取东方财富概念列表失败: {exc}") from exc

        failed: list[str] = []
        all_items: list[dict[str, Any]] = []
        for concept_row in concept_rows:
            concept_code = to_optional_str(concept_row.get("f12"))
            concept_name = to_optional_str(concept_row.get("f14"))
            if not concept_code or not concept_name:
                continue

            try:
                member_rows = _fetch_clist(f"b:{concept_code}", "f12,f14")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "concept_constituents_fetch_failed",
                    concept_code=concept_code,
                    concept_name=concept_name,
                    error=str(exc),
                )
                failed.append(concept_code)
                continue

            for member_row in member_rows:
                raw_code = member_row.get("f12")
                if raw_code is None:
                    continue
                stock_code = clean_stock_code(to_optional_str(raw_code) or "")
                if not stock_code or not stock_code.isdigit():
                    continue
                all_items.append(
                    {
                        "stock_code": stock_code,
                        "concept_code": concept_code,
                        "concept_name": concept_name,
                        "source": "eastmoney",
                    }
                )

        if failed:
            raise RuntimeError(
                f"概念成分拉取失败 {len(failed)}/{len(concept_rows)} 个"
                f"（如 {failed[:3]}），拒绝写入残缺映射"
            )
        return all_items
