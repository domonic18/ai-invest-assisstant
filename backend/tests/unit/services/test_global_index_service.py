"""全球指标快照服务单测：启用过滤、排序、无数据字段留空。"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError
from app.models.quote_global_index import GlobalIndexDaily
from app.services.market import global_index_service


def _scalars_result(rows: list) -> MagicMock:
    return MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )


def _config(
    code: str,
    name: str,
    sort_order: int,
    enabled: bool = True,
    market_category: str = "全球",
) -> MagicMock:
    cfg = MagicMock()
    cfg.index_code = code
    cfg.index_name = name
    cfg.sort_order = sort_order
    cfg.is_enabled = enabled
    cfg.market_category = market_category
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
            MagicMock(
                all=MagicMock(
                    return_value=[("GC00Y", 2649.1), ("GC00Y", 2650.5)]
                )
            ),
        ]

        quotes = await global_index_service.get_global_index_quotes(session)

        assert [q.index_code for q in quotes] == ["GC00Y", "UDI"]
        assert quotes[0].index_name == "COMEX黄金"
        assert quotes[0].close == 2650.5
        assert quotes[0].change_pct == 0.83
        assert quotes[0].trade_date == date(2026, 9, 2)
        assert quotes[0].trend == [2649.1, 2650.5]
        assert quotes[1].trend == []

    @pytest.mark.asyncio
    async def test_disabled_configs_excluded(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result([_config("GC00Y", "COMEX黄金", 1)]),
            MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
            MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ]

        quotes = await global_index_service.get_global_index_quotes(session)

        assert len(quotes) == 1
        assert quotes[0].index_code == "GC00Y"
        assert quotes[0].close is None
        assert quotes[0].trend == []
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
            MagicMock(
                all=MagicMock(return_value=[("US2Y", Decimal("3.8420"))])
            ),
        ]

        quotes = await global_index_service.get_global_index_quotes(session)

        assert quotes[0].close == pytest.approx(3.842)
        assert quotes[0].change_pct == pytest.approx(-1.25)


@pytest.mark.unit
class TestTrackedQuotesWithAShareExtras:
    """快照/选项清单含用户自加的 A 股标的；固定展示的大盘标的不进选项。"""

    @pytest.mark.asyncio
    async def test_a_share_extra_uses_kline_quotes(self) -> None:
        configs = [
            _config("GC00Y", "COMEX黄金", 1),
            _config("sh000905", "中证500", 2, market_category="A股"),
        ]
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(configs),
            # 全球指标最新收盘（GlobalIndexDaily）
            MagicMock(
                all=MagicMock(
                    return_value=[("GC00Y", 2650.5, 0.83, date(2026, 9, 2))]
                )
            ),
            # A 股标的最新日 K（quote_kline_stock_daily）
            MagicMock(
                all=MagicMock(
                    return_value=[("sh000905", 6850.0, 1.2, date(2026, 9, 2))]
                )
            ),
            # 全球指标近 30 日趋势
            MagicMock(
                all=MagicMock(return_value=[("GC00Y", 2649.1), ("GC00Y", 2650.5)])
            ),
            # A 股标的近 30 日趋势
            MagicMock(
                all=MagicMock(
                    return_value=[("sh000905", 6800.0), ("sh000905", 6850.0)]
                )
            ),
        ]

        quotes = await global_index_service.get_global_index_quotes(session)

        assert [q.index_code for q in quotes] == ["GC00Y", "sh000905"]
        assert quotes[1].close == 6850.0
        assert quotes[1].change_pct == 1.2
        assert quotes[1].trend == [6800.0, 6850.0]

    @pytest.mark.asyncio
    async def test_options_exclude_fixed_codes_and_carry_category(self) -> None:
        configs = [
            _config("sh000001", "上证指数", 1, market_category="A股"),  # 固定展示，应被剔除
            _config("sh000905", "中证500", 2, market_category="A股"),
        ]
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(configs),
            MagicMock(
                all=MagicMock(
                    return_value=[("sh000905", 6850.0, 1.2, date(2026, 9, 2))]
                )
            ),
        ]

        options = await global_index_service.list_tracked_index_options(session)

        assert [o.index_code for o in options] == ["sh000905"]
        assert options[0].id is not None
        assert options[0].market_category == "A股"
        assert options[0].latest_close == 6850.0
        assert options[0].latest_trade_date == date(2026, 9, 2)


def _daily(
    code: str,
    d: date,
    open_: str | None = "100",
    high: str | None = "110",
    low: str | None = "90",
    close: str | None = "105",
    volume: int | None = 1000,
) -> GlobalIndexDaily:
    return GlobalIndexDaily(
        index_code=code,
        trade_date=d,
        open=Decimal(open_) if open_ is not None else None,
        high=Decimal(high) if high is not None else None,
        low=Decimal(low) if low is not None else None,
        close=Decimal(close) if close is not None else None,
        volume=volume,
    )


@pytest.mark.unit
class TestGetGlobalIndexKline:
    @pytest.mark.asyncio
    async def test_daily_passes_ohlc_and_coerces_decimal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [
            _daily("HSI", date(2026, 9, 4), "25000", "25100", "24900", "25050"),
            _daily("HSI", date(2026, 9, 7), "25050", "25420", "25000", "25413"),
        ]
        monkeypatch.setattr(
            global_index_service.global_index_repository,
            "list_daily_bars",
            AsyncMock(return_value=rows),
        )

        result = await global_index_service.get_global_index_kline(
            AsyncMock(), "HSI", "daily", limit=10
        )

        assert result.code == "HSI"
        assert result.name == "恒生指数"
        assert [b.date for b in result.bars] == [date(2026, 9, 4), date(2026, 9, 7)]
        assert result.bars[-1].close == pytest.approx(25413)
        assert result.bars[-1].open == pytest.approx(25050)

    @pytest.mark.asyncio
    async def test_weekly_aggregates_ohlc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [
            _daily("HSI", date(2026, 9, 1), "100", "120", "80", "110", 100),
            _daily("HSI", date(2026, 9, 3), "110", "130", "90", "125", 200),
            _daily("HSI", date(2026, 9, 8), "125", "140", "100", "135", 300),
        ]
        monkeypatch.setattr(
            global_index_service.global_index_repository,
            "list_daily_bars",
            AsyncMock(return_value=rows),
        )

        result = await global_index_service.get_global_index_kline(
            AsyncMock(), "HSI", "weekly", limit=10
        )

        assert [b.date for b in result.bars] == [date(2026, 9, 1), date(2026, 9, 8)]
        week1 = result.bars[0]
        assert week1.open == pytest.approx(100)
        assert week1.high == pytest.approx(130)
        assert week1.low == pytest.approx(80)
        assert week1.close == pytest.approx(125)
        assert week1.volume == 300

    @pytest.mark.asyncio
    async def test_close_only_source_derives_ohlc_from_closes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [
            _daily("US10Y", date(2026, 9, 1), None, None, None, "3.80", None),
            _daily("US10Y", date(2026, 9, 2), None, None, None, "3.90", None),
        ]
        monkeypatch.setattr(
            global_index_service.global_index_repository,
            "list_daily_bars",
            AsyncMock(return_value=rows),
        )

        result = await global_index_service.get_global_index_kline(
            AsyncMock(), "US10Y", "weekly", limit=10
        )

        bar = result.bars[0]
        assert bar.open == pytest.approx(3.80)
        assert bar.high == pytest.approx(3.90)
        assert bar.low == pytest.approx(3.80)
        assert bar.close == pytest.approx(3.90)
        assert bar.volume is None

    @pytest.mark.asyncio
    async def test_spread_builds_close_only_bars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            global_index_service.global_index_repository,
            "list_closes",
            AsyncMock(
                side_effect=[
                    [(date(2026, 9, 1), Decimal("3.80")), (date(2026, 9, 2), Decimal("3.85"))],
                    [(date(2026, 9, 1), Decimal("4.10")), (date(2026, 9, 2), Decimal("4.05"))],
                ]
            ),
        )

        result = await global_index_service.get_global_index_kline(
            AsyncMock(), "US2Y10S", "daily", limit=10
        )

        assert result.name == "美债10Y-2Y利差"
        assert [b.close for b in result.bars] == [pytest.approx(0.30), pytest.approx(0.20)]
        assert result.bars[0].open is None

    @pytest.mark.asyncio
    async def test_invalid_period_or_code_raises(self) -> None:
        with pytest.raises(BadRequestError):
            await global_index_service.get_global_index_kline(
                AsyncMock(), "HSI", "minute"
            )
        with pytest.raises(BadRequestError):
            await global_index_service.get_global_index_kline(
                AsyncMock(), "NOPE", "daily"
            )

    @pytest.mark.asyncio
    async def test_limit_slices_latest_bars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [
            _daily("HSI", date(2026, 9, i + 1), close=str(100 + i)) for i in range(5)
        ]
        monkeypatch.setattr(
            global_index_service.global_index_repository,
            "list_daily_bars",
            AsyncMock(return_value=rows),
        )

        result = await global_index_service.get_global_index_kline(
            AsyncMock(), "HSI", "daily", limit=2
        )

        assert [b.date for b in result.bars] == [date(2026, 9, 4), date(2026, 9, 5)]
