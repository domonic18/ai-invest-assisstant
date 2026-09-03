"""全球指标快照服务单测：启用过滤、排序、无数据字段留空。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.market import global_index_service


def _scalars_result(rows: list) -> MagicMock:
    return MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )


def _config(code: str, name: str, sort_order: int, enabled: bool = True) -> MagicMock:
    cfg = MagicMock()
    cfg.index_code = code
    cfg.index_name = name
    cfg.sort_order = sort_order
    cfg.is_enabled = enabled
    return cfg


@pytest.mark.unit
class TestGetGlobalIndexQuotes:
    @pytest.mark.asyncio
    async def test_enabled_only_ordered_with_latest_bars(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(
                [
                    _config("GC00Y", "COMEX黄金", 1),
                    _config("UDI", "美元指数", 2),
                ]
            ),
            MagicMock(
                all=MagicMock(
                    return_value=[
                        ("GC00Y", 2650.5, 0.83, date(2026, 9, 2)),
                        ("UDI", 98.2, -0.12, date(2026, 9, 2)),
                    ]
                )
            ),
        ]

        quotes = await global_index_service.get_global_index_quotes(session)

        assert [q.index_code for q in quotes] == ["GC00Y", "UDI"]
        assert quotes[0].index_name == "COMEX黄金"
        assert quotes[0].close == 2650.5
        assert quotes[0].change_pct == 0.83
        assert quotes[0].trade_date == date(2026, 9, 2)

    @pytest.mark.asyncio
    async def test_disabled_configs_excluded(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result([_config("GC00Y", "COMEX黄金", 1)]),
            MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ]

        quotes = await global_index_service.get_global_index_quotes(session)

        assert len(quotes) == 1
        assert quotes[0].index_code == "GC00Y"
        assert quotes[0].close is None
        assert quotes[0].change_pct is None
        assert quotes[0].trade_date is None

    @pytest.mark.asyncio
    async def test_no_configs_returns_empty(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([])

        quotes = await global_index_service.get_global_index_quotes(session)

        assert quotes == []
        assert session.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_decimal_close_coerced(self) -> None:
        from decimal import Decimal

        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result([_config("US2Y", "美债2Y", 1)]),
            MagicMock(
                all=MagicMock(
                    return_value=[
                        (
                            "US2Y",
                            Decimal("3.8420"),
                            Decimal("-1.2500"),
                            date(2026, 9, 1),
                        )
                    ]
                )
            ),
        ]

        quotes = await global_index_service.get_global_index_quotes(session)

        assert quotes[0].close == pytest.approx(3.842)
        assert quotes[0].change_pct == pytest.approx(-1.25)
