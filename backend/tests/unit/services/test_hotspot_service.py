"""Unit tests for hotspot service."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import hotspot_service


def _result_mock(items=None, scalar=None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.mark.unit
class TestHotspotService:
    @pytest.mark.asyncio
    async def test_list_sectors_returns_items_and_total(self) -> None:
        session = AsyncMock()
        mock_sector = MagicMock()
        session.execute.return_value = _result_mock([mock_sector])
        session.scalar.return_value = 10

        items, total = await hotspot_service.list_sectors(
            session, sector_type="industry", page=1, page_size=10
        )

        assert items == [mock_sector]
        assert total == 10
        session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_list_sectors_with_trade_date(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _result_mock([])
        session.scalar.return_value = 0

        items, total = await hotspot_service.list_sectors(
            session, trade_date=date(2024, 1, 1)
        )

        assert items == []
        assert total == 0
