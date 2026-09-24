"""collector_log_service 单测（mock repository，不触库）。"""

from datetime import date, datetime, time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import clock
from app.core.exceptions import BadRequestError
from app.services.collector.collector_log_service import CollectorLogService


@pytest.mark.unit
class TestCollectorLogService:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_row(self) -> None:
        row = MagicMock()
        service = CollectorLogService(MagicMock())
        service.repo.get_by_id = AsyncMock(return_value=row)

        assert await service.get_by_id(7) is row
        service.repo.get_by_id.assert_awaited_once_with(7)

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_missing(self) -> None:
        service = CollectorLogService(MagicMock())
        service.repo.get_by_id = AsyncMock(return_value=None)

        assert await service.get_by_id(999) is None

    @pytest.mark.asyncio
    async def test_list_recent_paginates_with_filters(self) -> None:
        rows = [MagicMock()]
        service = CollectorLogService(MagicMock())
        service.repo.list_recent = AsyncMock(return_value=(1, rows))

        total, result = await service.list_recent(
            2, 10, task_name="kline", source="sina", status="failed"
        )

        assert total == 1
        assert result == rows
        service.repo.list_recent.assert_awaited_once_with(
            2,
            10,
            task_name="kline",
            source="sina",
            status="failed",
            started_after=None,
            started_before=None,
        )

    @pytest.mark.asyncio
    async def test_list_recent_rejects_unknown_status(self) -> None:
        service = CollectorLogService(MagicMock())

        with pytest.raises(BadRequestError):
            await service.list_recent(1, 20, status="nope")

    @pytest.mark.asyncio
    async def test_list_recent_converts_dates_to_cn_boundaries(self) -> None:
        """日期区间按 Asia/Shanghai 日历日换算为 [当日零点, 次日零点) 边界。"""
        service = CollectorLogService(MagicMock())
        service.repo.list_recent = AsyncMock(return_value=(0, []))

        await service.list_recent(
            1, 20, start_date=date(2026, 9, 1), end_date=date(2026, 9, 17)
        )

        (_, _), kwargs = service.repo.list_recent.await_args
        started_after = kwargs["started_after"]
        started_before = kwargs["started_before"]
        assert started_after == datetime(2026, 9, 1, tzinfo=clock.CN_TZ)
        assert started_before == datetime(2026, 9, 18, tzinfo=clock.CN_TZ)

    @pytest.mark.asyncio
    async def test_list_recent_rejects_inverted_date_range(self) -> None:
        service = CollectorLogService(MagicMock())
        service.repo.list_recent = AsyncMock()

        with pytest.raises(BadRequestError):
            await service.list_recent(
                1, 20, start_date=date(2026, 9, 17), end_date=date(2026, 9, 1)
            )
        service.repo.list_recent.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_today_summary_counts_by_status(self) -> None:
        service = CollectorLogService(MagicMock())
        service.repo.count_by_status_since = AsyncMock(
            return_value={"success": 5, "failed": 2, "running": 1}
        )

        summary = await service.get_today_summary()

        assert summary.date == clock.today_cn().isoformat()
        assert summary.success_count == 5
        assert summary.failed_count == 2
        assert summary.running_count == 1
        assert summary.partial_count == 0
        assert summary.pending_count == 0

        (since,), kwargs = service.repo.count_by_status_since.await_args
        assert not kwargs
        # 今日零点必须是 Asia/Shanghai 意义：tzinfo 为 CN_TZ 且时间为 00:00
        assert since.tzinfo is clock.CN_TZ
        assert since.timetz().replace(tzinfo=None) == time.min
        assert since.date() == clock.today_cn()

    @pytest.mark.asyncio
    async def test_get_today_summary_missing_statuses_default_zero(self) -> None:
        service = CollectorLogService(MagicMock())
        service.repo.count_by_status_since = AsyncMock(return_value={})

        summary = await service.get_today_summary()

        assert summary.date == datetime.now(clock.CN_TZ).date().isoformat()
        assert summary.success_count == 0
        assert summary.failed_count == 0

    @pytest.mark.asyncio
    async def test_list_dead_letters_returns_total_and_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        service = CollectorLogService(MagicMock())
        service.dead_letter_repo.list_paginated = AsyncMock(return_value=(2, rows))

        total, result = await service.list_dead_letters(page=3, page_size=2)

        assert total == 2
        assert result == rows
        service.dead_letter_repo.list_paginated.assert_awaited_once_with(4, 2)
