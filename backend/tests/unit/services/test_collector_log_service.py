"""collector_log_service 单测（mock repository，不触库）。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

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
    async def test_list_dead_letters_returns_total_and_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        service = CollectorLogService(MagicMock())
        service.dead_letter_repo.list_paginated = AsyncMock(return_value=(2, rows))

        total, result = await service.list_dead_letters(page=3, page_size=2)

        assert total == 2
        assert result == rows
        service.dead_letter_repo.list_paginated.assert_awaited_once_with(4, 2)
