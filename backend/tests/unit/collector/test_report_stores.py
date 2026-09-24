"""研报/财报存储编排单测：PDF 全文抽取写入 file_metadata.content。"""

import datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.stores.financial_report_store import FinancialReportStore
from collector.stores.research_report_store import ResearchReportStore


class _Result:
    def __init__(self, row=None):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _Session:
    """覆盖 save_many/_save_one 所需的最小 AsyncSession 表面。"""

    def __init__(self, results: list):
        self._results = list(results)
        self.added: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def execute(self, stmt):
        return self._results.pop(0)

    def add(self, obj):
        self.added.append(obj)

    @asynccontextmanager
    async def begin_nested(self):
        yield

    async def commit(self):
        pass

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


def _minio() -> MagicMock:
    minio = MagicMock()
    minio.upload_file = AsyncMock()
    minio.get_presigned_url = AsyncMock(return_value="http://minio/presigned")
    return minio


def _financial_item() -> dict:
    return {
        "stock_code": "000001",
        "title": "2023年年度报告",
        "publish_date": datetime.date(2024, 3, 15),
        "report_type": "annual",
        "source_url": "http://static.cninfo.com.cn/finalpage/2024-03-15/test.PDF",
        "file_bytes": b"%PDF-1.4 fake",
        "file_type": "pdf",
    }


@pytest.mark.unit
class TestFinancialReportStore:
    async def test_new_record_writes_content(self) -> None:
        session = _Session(results=[_Result(None)])
        with (
            patch(
                "collector.stores.financial_report_store.get_engine",
                MagicMock(),
            ),
            patch(
                "collector.stores.financial_report_store.async_sessionmaker",
                MagicMock(return_value=lambda: session),
            ),
            patch(
                "collector.stores.financial_report_store.extract_pdf_text",
                AsyncMock(return_value="营业收入全文"),
            ),
        ):
            stored, errors = await FinancialReportStore(minio=_minio()).save_many(
                [_financial_item()]
            )

        assert stored == 1
        assert errors == []
        assert len(session.added) == 1
        record = session.added[0]
        assert record.file_type == "financial_report"
        assert record.content == "营业收入全文"

    async def test_existing_record_keeps_content_on_extract_failure(self) -> None:
        existing = MagicMock()
        existing.content = "旧全文"
        session = _Session(results=[_Result(existing)])
        with (
            patch(
                "collector.stores.financial_report_store.get_engine",
                MagicMock(),
            ),
            patch(
                "collector.stores.financial_report_store.async_sessionmaker",
                MagicMock(return_value=lambda: session),
            ),
            patch(
                "collector.stores.financial_report_store.extract_pdf_text",
                AsyncMock(return_value=None),
            ),
        ):
            stored, errors = await FinancialReportStore(minio=_minio()).save_many(
                [_financial_item()]
            )

        assert stored == 1
        assert errors == []
        assert existing.content == "旧全文"


@pytest.mark.unit
class TestResearchReportStore:
    async def test_new_record_writes_content(self) -> None:
        session = _Session(results=[_Result(None), _Result(None)])
        item = {
            "stock_code": "600703",
            "title": "光模块行业深度",
            "publish_date": datetime.datetime(
                2026, 8, 1, tzinfo=datetime.timezone.utc
            ),
            "source_url": "https://pdf.dfcfw.com/pdf/H3_abc.pdf",
            "extra": {"info_code": "AP20260801", "broker": "某券商"},
            "file_bytes": b"%PDF-1.4 fake",
        }
        with (
            patch(
                "collector.stores.research_report_store.get_engine",
                MagicMock(),
            ),
            patch(
                "collector.stores.research_report_store.async_sessionmaker",
                MagicMock(return_value=lambda: session),
            ),
            patch(
                "collector.stores.research_report_store.extract_pdf_text",
                AsyncMock(return_value="800G 光模块放量"),
            ),
        ):
            stored, errors = await ResearchReportStore(minio=_minio()).save_many(
                [item]
            )

        assert stored == 1
        assert errors == []
        assert [type(r).__name__ for r in session.added] == [
            "NewsDocument",
            "FileMetadata",
        ]
        record = session.added[1]
        assert record.file_type == "research_report"
        assert record.content == "800G 光模块放量"
