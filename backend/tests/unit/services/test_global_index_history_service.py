"""全球指标历史走势服务单测：US2Y10S 利差对齐求差与参数校验。"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.core.clock import today_cn
from app.core.exceptions import BadRequestError
from app.services.market.global_index_service import get_index_history


@pytest.mark.unit
class TestGetIndexHistory:
    async def test_us2y10s_aligned_by_trade_date(self) -> None:
        """利差 = US10Y − US2Y，仅取两腿共同的交易日。"""
        us2y = [
            (date(2026, 9, 1), Decimal("3.70")),
            (date(2026, 9, 2), Decimal("3.72")),
            (date(2026, 9, 3), Decimal("3.75")),  # US10Y 缺 9/3
        ]
        us10y = [
            (date(2026, 9, 1), Decimal("3.80")),
            (date(2026, 9, 2), Decimal("3.82")),
            (date(2026, 9, 4), Decimal("3.90")),  # US2Y 缺 9/4
        ]

        async def fake_list_closes(session, code, since):
            return us2y if code == "US2Y" else us10y

        with patch(
            "app.services.market.global_index_service.global_index_repository.list_closes",
            new=fake_list_closes,
        ):
            points = await get_index_history(None, "US2Y10S", months=12)  # type: ignore[arg-type]

        assert [(p.trade_date, p.close) for p in points] == [
            (date(2026, 9, 1), pytest.approx(0.10)),
            (date(2026, 9, 2), pytest.approx(0.10)),
        ]

    async def test_unknown_code_rejected(self) -> None:
        with pytest.raises(BadRequestError, match="未知全球指标代码"):
            await get_index_history(None, "NOPE", months=12)  # type: ignore[arg-type]

    async def test_tracked_code_passes_through(self) -> None:
        with patch(
            "app.services.market.global_index_service.global_index_repository.list_closes",
            new=AsyncMock(return_value=[(date(2026, 9, 1), Decimal("2650.5"))]),
        ) as mock_list:
            points = await get_index_history(None, "GC00Y", months=6)  # type: ignore[arg-type]

        assert len(points) == 1
        assert points[0].close == 2650.5
        since = mock_list.call_args.args[2]
        assert since == today_cn() - timedelta(days=6 * 31)
