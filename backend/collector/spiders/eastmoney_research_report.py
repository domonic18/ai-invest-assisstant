"""基于 reportapi HTTP 接口的东方财富研报采集器。

拉取东方财富个股研报列表（reportapi），下载原始 PDF，输出包含
``file_bytes`` 的标准化条目。``store`` 步骤由
``collector.stores.research_report_store`` 负责写入 news_announcement、
MinIO 与 file_metadata。
"""

import asyncio
from datetime import date, datetime
from typing import Any

import structlog

from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.parsing import to_float, to_int, to_optional_str

_str = to_optional_str

logger = structlog.get_logger()

_LIST_URL = "https://reportapi.eastmoney.com/report/list"
_PDF_URL_TEMPLATE = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
_PAGE_SIZE = 50
_DOWNLOAD_CONCURRENCY = 5

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class EastMoneyResearchReportCollector(BaseCollector):
    """东方财富个股研报采集器，写入 news_announcement(doc_type='research')。"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.list_url = config.get("list_url") or _LIST_URL
        self.timeout = float(config.get("timeout", 60))
        self.max_pages = int(config.get("max_pages", 20))

    async def collect(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """查询 reportapi 列表接口并下载研报 PDF。"""
        import httpx

        end = _parse_date(end_date) or date.today()
        start = _parse_date(start_date) or end
        if start > end:
            start = end

        logger.info(
            "eastmoney_research_report_collect_start",
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=True, headers=_HEADERS
        ) as client:
            entries = await self._fetch_list(client, start, end)
            await self._download_pdfs(client, entries)

        raw = [entry for entry in entries]
        logger.info(
            "eastmoney_research_report_collect_finished",
            total=len(raw),
            with_pdf=sum(1 for entry in raw if entry.get("file_bytes")),
        )
        return raw

    async def _fetch_list(
        self, client: Any, start: date, end: date
    ) -> list[dict[str, Any]]:
        """抓取日期范围内的全部研报列表页。"""
        entries: list[dict[str, Any]] = []
        page_no = 1
        total_pages = 1
        while page_no <= total_pages and page_no <= self.max_pages:
            params = {
                "pageSize": _PAGE_SIZE,
                "beginTime": start.strftime("%Y-%m-%d"),
                "endTime": end.strftime("%Y-%m-%d"),
                "pageNo": page_no,
                "qType": 0,
            }
            response = await client.get(self.list_url, params=params)
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") or []
            if not data:
                break
            for item in data:
                entry = _map_entry(item)
                if entry:
                    entries.append(entry)
            total_pages = int(payload.get("TotalPage") or 1)
            page_no += 1
        return entries

    async def _download_pdfs(
        self, client: Any, entries: list[dict[str, Any]]
    ) -> None:
        """并发下载研报 PDF；失败的条目保留元数据。"""
        semaphore = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)

        async def fetch_one(entry: dict[str, Any]) -> None:
            async with semaphore:
                try:
                    entry["file_bytes"] = await download_research_pdf(
                        entry["source_url"]
                    )
                    entry["file_size"] = len(entry["file_bytes"])
                except Exception as exc:  # noqa: BLE001
                    entry["file_bytes"] = None
                    entry["file_size"] = None
                    logger.warning(
                        "eastmoney_research_report_pdf_download_failed",
                        source_url=entry["source_url"],
                        error=str(exc),
                    )

        await asyncio.gather(*(fetch_one(entry) for entry in entries))

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_code": str(raw["stock_code"]),
            "doc_type": "research",
            "title": raw.get("title"),
            "source": "eastmoney",
            "source_url": raw.get("source_url"),
            "publish_date": raw.get("publish_date"),
            "industry_tags": raw.get("industry_tags"),
            "extra": raw.get("extra"),
            "file_bytes": raw.get("file_bytes"),
            "file_size": raw.get("file_size"),
        }

    async def validate(self, item: dict[str, Any]) -> bool:
        return bool(
            item.get("stock_code")
            and item.get("title")
            and item.get("publish_date")
            and item.get("source_url")
        )

    async def store(self, items: list[dict[str, Any]]) -> int:
        """通过 store 层把元数据写入数据库、PDF 写入 MinIO。"""
        if not items:
            return 0
        count, _ = await self._save_items(items)
        return count

    async def _save_items(
        self, items: list[dict[str, Any]]
    ) -> tuple[int, list[str]]:
        from app.services.common.minio_service import get_minio_service
        from collector.stores.research_report_store import ResearchReportStore

        store = ResearchReportStore(minio=get_minio_service())
        return await store.save_many(items)

    async def run(self, **kwargs: Any) -> CollectResult:
        """运行完整流程，把存储警告体现在结果的 errors 中。"""
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


async def download_research_pdf(url: str, timeout: float = 60) -> bytes:
    """用 Chrome TLS 指纹下载单份研报 PDF。

    pdf.dfcfw.com 的 WAF 按 TLS 指纹拦截：httpx/OpenSSL 会返回 JS 反爬挑战，
    curl_cffi 的 Chrome 指纹可正常取回 PDF。非 PDF 内容（反爬页面）视为失败。
    """
    from curl_cffi.requests import AsyncSession

    async with AsyncSession(impersonate="chrome", timeout=timeout) as session:
        response = await session.get(url)
    if response.status_code != 200:
        raise ValueError(f"unexpected status {response.status_code} for {url}")
    data = bytes(response.content)
    if not data.startswith(b"%PDF-"):
        raise ValueError(f"not a PDF payload ({len(data)} bytes) for {url}")
    return data


def _map_entry(item: dict[str, Any]) -> dict[str, Any] | None:
    """把单条 reportapi 列表项映射为原始条目；关键字段缺失返回 None。"""
    info_code = _str(item.get("infoCode"))
    stock_code = _str(item.get("stockCode"))
    title = _str(item.get("title"))
    publish_date = _parse_datetime(_str(item.get("publishDate")))
    if not (info_code and stock_code and title and publish_date):
        return None

    industry = _str(item.get("indvInduName"))
    return {
        "stock_code": stock_code,
        "title": title,
        "publish_date": publish_date,
        "source_url": _PDF_URL_TEMPLATE.format(info_code=info_code),
        "industry_tags": [industry] if industry else None,
        "extra": {
            "stock_name": _str(item.get("stockName")),
            "broker": _str(item.get("orgSName")),
            "rating": _str(item.get("emRatingName")),
            "rating_change": to_int(item.get("ratingChange")),
            "author": _str(item.get("researcher")),
            "eps_forecast": {
                "this_year": to_float(item.get("predictThisYearEps")),
                "next_year": to_float(item.get("predictNextYearEps")),
            },
            "pe_forecast": {
                "this_year": to_float(item.get("predictThisYearPe")),
                "next_year": to_float(item.get("predictNextYearPe")),
            },
            "aim_price_high": to_float(item.get("indvAimPriceT")),
            "aim_price_low": to_float(item.get("indvAimPriceL")),
            "pages": to_int(item.get("attachPages")),
            "info_code": info_code,
        },
        "file_bytes": None,
        "file_size": None,
    }


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
