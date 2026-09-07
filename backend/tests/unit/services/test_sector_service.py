"""板块概览服务（sector_service）契约测试。"""


from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import (
    limit_pool_service,
    market_service,
)


def _scalars_result(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _sector_row(sector_name, change_pct=None, main_net_inflow=None):
    return MagicMock(
        sector_name=sector_name,
        change_pct=Decimal(str(change_pct)) if change_pct is not None else None,
        main_net_inflow=(
            Decimal(str(main_net_inflow)) if main_net_inflow is not None else None
        ),
    )


@pytest.mark.unit
class TestGetSectorOverview:
    @pytest.mark.asyncio
    async def test_builds_heatmap_and_top_lists(self) -> None:
        def _sector(name, pct, inflow, top_stock=None):
            row = MagicMock()
            row.sector_name = name
            row.change_pct = Decimal(str(pct)) if pct is not None else None
            row.main_net_inflow = Decimal(str(inflow))
            row.top_stock_name = top_stock
            return row

        rows = [_sector(f"板块{i}", 5 - i, (10 - i) * 1e8, f"龙头{i}") for i in range(12)]
        rows.append(_sector("弱势板块", -3.0, -5e8))

        session = AsyncMock()
        session.execute.return_value = _scalars_result(rows)

        limit_up = MagicMock()
        limit_up.items = [
            MagicMock(industry="板块0", stock_name="涨停股A"),
            MagicMock(industry="板块0", stock_name="涨停股B"),
        ]
        with patch.object(
            limit_pool_service, "get_limit_up", AsyncMock(return_value=limit_up)
        ):
            overview = await market_service.get_sector_overview(
                session, date(2026, 7, 17)
            )

        assert len(overview.heatmap) == 15
        assert overview.heatmap[0].sector_name == "板块0"
        assert overview.top_inflow[0].sector_name == "板块0"
        assert overview.top_outflow[0].sector_name == "弱势板块"
        assert overview.leading[0].limit_up_count == 2
        assert "涨停股A" in overview.leading[0].top_stock_names
