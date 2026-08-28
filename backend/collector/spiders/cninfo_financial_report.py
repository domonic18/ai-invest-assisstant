"""CNINFO 定期财报文件采集器。

爬取巨潮资讯（cninfo.com.cn）的财报公告并下载原始 PDF 文件。产出的条目
交给存储层处理：文件持久化到 MinIO、记录元数据并写入知识库索引。
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog

from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.parsing import clean_stock_code, to_optional_str

_str = to_optional_str

logger = structlog.get_logger()

DEFAULT_REPORT_TYPES = ["年报", "半年报", "一季报", "三季报"]

_REPORT_CATEGORY_MAP: dict[str, str] = {
    "年报": "category_ndbg_szsh",
    "半年报": "category_bndbg_szsh",
    "一季报": "category_yjdbg_szsh",
    "三季报": "category_sjdbg_szsh",
}

_REPORT_TYPE_KEY: dict[str, str] = {
    "年报": "annual",
    "半年报": "semi_annual",
    "一季报": "q1",
    "三季报": "q3",
}

# 管理后台/CLI 传英文枚举，巨潮 category 用中文名——两边都要能收
_REPORT_TYPE_ALIASES: dict[str, str] = {
    "annual": "年报",
    "年报": "年报",
    "semi": "半年报",
    "semi_annual": "半年报",
    "半年报": "半年报",
    "中报": "半年报",
    "q1": "一季报",
    "一季报": "一季报",
    "q3": "三季报",
    "三季报": "三季报",
}

_CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
_CNINFO_TOPSEARCH_URL = "http://www.cninfo.com.cn/new/information/topSearch/query"
_CNINFO_DOWNLOAD_BASE = "http://static.cninfo.com.cn/"


class CninfoFinancialReportCollector(BaseCollector):
    """巨潮资讯个股财报文件采集器。

    通过巨潮资讯公开 API 查询定期报告列表，下载原始 PDF 文件，输出包含
    ``file_bytes`` 的标准化条目。后续 ``store`` 步骤负责写入 MinIO、
    ``file_metadata`` 表和知识库。
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.report_types = _normalize_report_types(
            config.get("report_types")
        ) or list(DEFAULT_REPORT_TYPES)
        self.base_url = config.get("base_url") or _CNINFO_QUERY_URL
        self.api_key = config.get("api_key")
        self.timeout = float(config.get("timeout", 60))
        self.max_pages = int(config.get("max_pages", 10))

    async def collect(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """查询 CNINFO 并下载财报 PDF 文件。"""
        import httpx

        if end_date is None:
            end = date.today()
        else:
            end = _parse_date(end_date) or date.today()
        if start_date is None:
            start = end - timedelta(days=365)
        else:
            start = _parse_date(start_date) or (end - timedelta(days=365))

        se_date = f"{start.strftime('%Y-%m-%d')}~{end.strftime('%Y-%m-%d')}"
        symbols = symbols or ["000001"]

        raw: list[dict[str, Any]] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        logger.info(
            "cninfo_financial_report_collect_start",
            symbols=symbols,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            report_types=self.report_types,
        )
        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=True, headers=headers
        ) as client:
            for symbol in symbols:
                code = clean_stock_code(symbol)
                plate = _plate_for_code(code)
                if not plate:
                    continue

                org_id = await _resolve_org_id(client, code)
                if not org_id:
                    continue
                stock_param = f"{code},{org_id}"

                for category_name in self.report_types:
                    category_code = _REPORT_CATEGORY_MAP.get(category_name)
                    if not category_code:
                        continue

                    announcements = await _query_announcements(
                        client=client,
                        base_url=self.base_url,
                        stock_param=stock_param,
                        plate=plate,
                        category=category_code,
                        se_date=se_date,
                        max_pages=self.max_pages,
                    )

                    for announcement in announcements:
                        pdf_url = _pdf_url(announcement)
                        if not pdf_url:
                            continue

                        try:
                            file_bytes = await _download(client, pdf_url)
                        except Exception:  # noqa: BLE001
                            continue

                        if not file_bytes:
                            continue

                        report_type = _REPORT_TYPE_KEY.get(category_name)
                        if report_type is None:
                            continue

                        raw.append(
                            {
                                "stock_code": code,
                                "title": _str(announcement.get("announcementTitle")),
                                "publish_date": _parse_date(_str(announcement.get("announcementTime"))),
                                "report_type": report_type,
                                "report_category": category_name,
                                "source_url": pdf_url,
                                "announcement_id": _str(announcement.get("announcementId")),
                                "org_id": _str(announcement.get("orgId")),
                                "file_bytes": file_bytes,
                                "file_size": len(file_bytes),
                                "file_type": "pdf",
                                "source": "cninfo",
                            }
                        )

        logger.info(
            "cninfo_financial_report_collect_finished",
            symbols=symbols,
            total_collected=len(raw),
        )
        return raw

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "title": raw.get("title"),
            "publish_date": raw.get("publish_date"),
            "report_type": raw.get("report_type"),
            "report_category": raw.get("report_category"),
            "source_url": raw.get("source_url"),
            "announcement_id": raw.get("announcement_id"),
            "org_id": raw.get("org_id"),
            "file_bytes": raw.get("file_bytes"),
            "file_size": raw.get("file_size"),
            "file_type": raw.get("file_type"),
            "source": raw.get("source"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("stock_code")
            and item.get("title")
            and item.get("publish_date")
            and item.get("source_url")
            and item.get("file_bytes")
            and len(item.get("file_bytes", b"")) > 0
        )

    async def store(self, items: list[dict[str, Any]]) -> int:
        """把下载的 PDF 持久化到 MinIO、元数据写入数据库并索引到知识库。

        本方法只是薄编排层；具体 exporter 惰性导入，使采集器在单元测试中
        无需运行 MinIO 集群即可使用。
        """
        if not items:
            return 0

        count, _ = await self._save_items(items)
        return count

    async def _save_items(
        self, items: list[dict[str, Any]]
    ) -> tuple[int, list[str]]:
        from app.services.common.knowledge_base_service import get_knowledge_base_service
        from app.services.common.minio_service import get_minio_service
        from collector.stores.financial_report_store import FinancialReportStore

        minio = get_minio_service()
        kb = get_knowledge_base_service()
        store = FinancialReportStore(minio=minio, kb=kb)
        return await store.save_many(items)

    async def run(self, **kwargs: Any) -> CollectResult:
        """运行完整的 collect/transform/validate/store 流程。

        覆写基类模板，使存储层警告（如 MinIO 或知识库不可用）体现在结果的
        errors 中而不是被静默吞掉。
        """
        started_at = datetime.utcnow()
        try:
            raw_data = await self.collect(**kwargs)
            transformed: list[dict[str, Any]] = []
            errors: list[str] = []

            for idx, item in enumerate(raw_data):
                try:
                    standardized = await self.transform(item)
                    if await self.validate(standardized):
                        transformed.append(standardized)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"item {idx}: {exc}")

            stored_count, store_errors = await self._save_items(transformed)
            errors.extend(store_errors)

            status = CollectStatus.SUCCESS if not errors else CollectStatus.PARTIAL
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=status,
                items_collected=len(raw_data),
                items_stored=stored_count,
                errors=errors,
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                items_collected=0,
                items_stored=0,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )


async def _resolve_org_id(client: Any, code: str) -> str | None:
    """通过 ``topSearch/query`` 解析股票代码对应的 CNINFO ``orgId``。"""
    try:
        response = await client.post(
            _CNINFO_TOPSEARCH_URL, data={"keyWord": code, "maxNum": 10}
        )
        response.raise_for_status()
        items = response.json()
    except Exception:  # noqa: BLE001
        return None

    for item in items if isinstance(items, list) else []:
        if str(item.get("code", "")).lstrip("0") == code.lstrip("0"):
            org_id = _str(item.get("orgId"))
            if org_id:
                return org_id
    return None


async def _query_announcements(
    client: Any,
    base_url: str,
    stock_param: str,
    plate: str,
    category: str,
    se_date: str,
    max_pages: int,
) -> list[dict[str, Any]]:
    """查询 CNINFO ``hisAnnouncement/query`` 并返回全部公告。"""
    results: list[dict[str, Any]] = []
    page_num = 1

    while page_num <= max_pages:
        payload = {
            "pageNum": page_num,
            "pageSize": 30,
            "tabName": "fulltext",
            "column": f"{plate}se",
            "stock": stock_param,
            "searchkey": "",
            "secid": "",
            "plate": plate,
            "category": category,
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "limit": "",
            "showTitle": "",
            "isHLtitle": "true",
        }

        try:
            response = await client.post(base_url, data=payload)
            response.raise_for_status()
            data = response.json()
        except Exception:  # noqa: BLE001
            break

        announcements = data.get("announcements") or []
        if not announcements:
            break

        results.extend(announcements)

        total_pages = int(data.get("totalPages") or 1)
        if page_num >= total_pages:
            break
        page_num += 1

    return results


def _pdf_url(announcement: dict[str, Any]) -> str | None:
    adjunct_url = _str(announcement.get("adjunctUrl"))
    if not adjunct_url:
        return None
    return f"{_CNINFO_DOWNLOAD_BASE}{adjunct_url.lstrip('/')}"


async def _download(client: Any, url: str) -> bytes:
    response = await client.get(url)
    response.raise_for_status()
    return bytes(response.content)


def _plate_for_code(code: str) -> str | None:
    if code.startswith("6"):
        return "sh"
    if code.startswith(("0", "2", "3")):
        return "sz"
    if code.startswith(("4", "8", "9")):
        return "bj"
    return None


def _normalize_report_types(values: list[str] | None) -> list[str]:
    """英文枚举/中文别名统一为中文名，未知值原样保留由 category 映射跳过。"""
    normalized: list[str] = []
    for value in values or []:
        name = _REPORT_TYPE_ALIASES.get(str(value).strip()) or str(value).strip()
        if name and name not in normalized:
            normalized.append(name)
    return normalized


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if text.isdigit():
        ts = int(text)
        if ts > 10_000_000_000:  # CNINFO 返回的是毫秒级时间戳
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
