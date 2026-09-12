"""指数行情服务（index_quotation_service）契约测试。

阶段 2.3 后 market_service 已拆为 7 个子服务；测试 patch 目标按函数实际定义
模块定向（patch market_service 命名空间无法拦截子服务内部的查找）。"""


from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.services.market import (
    index_quotation_service,
    market_service,
)


@pytest.mark.unit
class TestGetIndexQuotes:
    @pytest.mark.asyncio
    async def test_uses_redis_spot_when_present(self) -> None:
        spot = [
            {
                "code": "sh000001",
                "name": "上证指数",
                "price": 3352.88,
                "change": 41.0,
                "change_pct": 1.24,
                "amount": 5e11,
            }
        ]
        with (
            patch.object(index_quotation_service, "_index_spot", AsyncMock(return_value=spot)),
            patch.object(
                index_quotation_service,
                "_local_index_closes",
                AsyncMock(return_value=[1.0, 2.0]),
            ),
            patch.object(
                index_quotation_service,
                "_kline_extra_quotes",
                AsyncMock(return_value=[]),
            ),
        ):
            quotes = await market_service.get_index_quotes(AsyncMock())

        assert len(quotes) == 1
        assert quotes[0].code == "sh000001"
        assert quotes[0].trend == [1.0, 2.0]

    @pytest.mark.asyncio
    async def test_db_spot_when_redis_empty(self) -> None:
        db_spot = [
            {
                "code": "sz399001",
                "name": "深证成指",
                "price": 10868.24,
                "change": 169.0,
                "change_pct": 1.58,
                "amount": 6e11,
            }
        ]
        with (
            patch.object(index_quotation_service, "_index_spot", AsyncMock(return_value=None)),
            patch.object(
                index_quotation_service,
                "_bar_synthesized_spot",
                AsyncMock(return_value=db_spot),
            ),
            patch.object(
                index_quotation_service, "_local_index_closes", AsyncMock(return_value=[1.0])
            ),
            patch.object(
                index_quotation_service,
                "_kline_extra_quotes",
                AsyncMock(return_value=[]),
            ),
        ):
            quotes = await market_service.get_index_quotes(AsyncMock())

        assert quotes[0].name == "深证成指"
        assert quotes[0].price == 10868.24

    @pytest.mark.asyncio
    async def test_appends_kline_extra_codes(self) -> None:
        """扩展标的（沪深300ETF/富时A50）无实时通道，行情由日 K 合成并追加在尾部。"""

        async def _spot_by_codes(_session: object, codes: dict) -> list[dict]:
            return [
                {
                    "code": code,
                    "name": name,
                    "price": 1.0,
                    "change": 0.01,
                    "change_pct": 1.0,
                    "amount": None,
                }
                for code, name in codes.items()
            ]
        with (
            patch.object(index_quotation_service, "_index_spot", AsyncMock(return_value=None)),
            patch.object(
                index_quotation_service, "_bar_synthesized_spot", side_effect=_spot_by_codes
            ),
            patch.object(
                index_quotation_service, "_local_index_closes", AsyncMock(return_value=[1.0])
            ),
        ):
            quotes = await market_service.get_index_quotes(AsyncMock())

        assert len(quotes) == len(market_service.INDEX_CODES) + len(
            index_quotation_service.KLINE_CHART_EXTRA_CODES
        )
        assert [q.code for q in quotes][-2:] == ["sh510300", "CN00Y"]

    @pytest.mark.asyncio
    async def test_db_index_spot_synthesizes_from_daily_bars(self) -> None:
        def _bar(day: date, close: float) -> MagicMock:
            bar = MagicMock()
            bar.trade_date = day
            bar.close = close
            bar.amount = Decimal("5000")
            return bar

        bars = [_bar(date(2026, 7, 17), 101.0), _bar(date(2026, 7, 16), 100.0)]
        with patch.object(
            index_quotation_service, "fetch_daily_bars", AsyncMock(return_value=bars)
        ):
            spot = await index_quotation_service._bar_synthesized_spot(
                AsyncMock(), market_service.INDEX_CODES
            )

        assert len(spot) == len(market_service.INDEX_CODES)
        assert spot[0]["price"] == 101.0
        assert spot[0]["change"] == 1.0
        assert spot[0]["change_pct"] == 1.0
        assert spot[0]["amount"] == 5000.0


@pytest.mark.unit
class TestGetIndexIntraday:
    def _bar(self, ts: str, close: float) -> MagicMock:
        bar = MagicMock()
        bar.trade_time = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo("Asia/Shanghai")
        )
        bar.close = Decimal(str(close))
        bar.volume = 100
        bar.amount = Decimal("1000")
        return bar

    @pytest.mark.asyncio
    async def test_rejects_unknown_code(self) -> None:
        with pytest.raises(ValueError, match="不支持的指数代码"):
            await market_service.get_index_intraday(AsyncMock(), "sh999999")

    @pytest.mark.asyncio
    async def test_builds_points_and_prev_close(self) -> None:
        bars = [
            self._bar("2026-07-17 09:31:00", 3800.0),
            self._bar("2026-07-17 09:32:00", 3801.5),
        ]
        with (
            patch.object(
                index_quotation_service,
                "latest_minute_day",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                index_quotation_service, "fetch_minute_bars", AsyncMock(return_value=bars)
            ),
            patch.object(
                index_quotation_service, "prev_minute_close", AsyncMock(return_value=3781.0)
            ),
        ):
            result = await market_service.get_index_intraday(AsyncMock(), "sh000001")

        assert result.trade_date == date(2026, 7, 17)
        assert result.prev_close == 3781.0
        assert [p.time for p in result.points] == ["09:31", "09:32"]
        assert result.points[1].price == 3801.5
        assert result.points[0].volume == 100.0

    @pytest.mark.asyncio
    async def test_prev_close_falls_back_to_daily(self) -> None:
        bars = [self._bar("2026-07-17 09:31:00", 3800.0)]
        daily_bar = MagicMock()
        daily_bar.trade_date = date(2026, 7, 16)
        daily_bar.close = Decimal("3775")
        with (
            patch.object(
                index_quotation_service, "fetch_minute_bars", AsyncMock(return_value=bars)
            ),
            patch.object(
                index_quotation_service, "prev_minute_close", AsyncMock(return_value=None)
            ),
            patch.object(
                index_quotation_service,
                "fetch_daily_bars",
                AsyncMock(return_value=[daily_bar]),
            ),
        ):
            result = await market_service.get_index_intraday(
                AsyncMock(), "sh000001", date(2026, 7, 17)
            )

        assert result.prev_close == 3775.0

    @pytest.mark.asyncio
    async def test_historical_date_without_bars_raises(self) -> None:
        with (
            patch.object(
                index_quotation_service, "fetch_minute_bars", AsyncMock(return_value=[])
            ),
            pytest.raises(ValueError, match="无分时数据"),
        ):
            await market_service.get_index_intraday(
                AsyncMock(), "sh000001", date(2026, 6, 1)
            )

    @pytest.mark.asyncio
    async def test_empty_when_no_minute_data(self) -> None:
        with patch.object(
            index_quotation_service, "latest_minute_day", AsyncMock(return_value=None)
        ):
            result = await market_service.get_index_intraday(AsyncMock(), "sh000001")

        assert result.points == []
        assert result.name == "上证指数"


@pytest.mark.unit
class TestHistoricalIndexQuotes:
    """历史指数行情只读本地 quote_kline_stock_daily（服务层倒序反转为升序序列）。"""

    def _bar(self, day: date, close: float) -> MagicMock:
        bar = MagicMock()
        bar.trade_date = day
        bar.close = close
        return bar

    @pytest.mark.asyncio
    async def test_picks_close_for_requested_date(self) -> None:
        # fetch_daily_bars 返回倒序（最新在前）
        bars = [
            self._bar(date(2026, 7, 17), 101.0),
            self._bar(date(2026, 7, 16), 102.0),
            self._bar(date(2026, 7, 15), 100.0),
        ]
        with patch.object(
            index_quotation_service, "fetch_daily_bars", AsyncMock(return_value=bars)
        ):
            quotes = await market_service.get_index_quotes(
                AsyncMock(), date(2026, 7, 16)
            )

        assert len(quotes) == len(market_service.INDEX_CODES) + len(
            index_quotation_service.KLINE_CHART_EXTRA_CODES
        )
        assert quotes[0].price == 102.0
        assert quotes[0].change == 2.0
        assert quotes[0].change_pct == 2.0
        assert quotes[0].trend == [100.0, 102.0]

    @pytest.mark.asyncio
    async def test_non_trading_day_returns_empty(self) -> None:
        bars = [self._bar(date(2026, 7, 17), 100.0)]
        with patch.object(
            index_quotation_service, "fetch_daily_bars", AsyncMock(return_value=bars)
        ):
            quotes = await market_service.get_index_quotes(
                AsyncMock(), date(2026, 7, 16)
            )

        assert quotes == []


@pytest.mark.unit
class TestGetIndexKline:
    @pytest.mark.asyncio
    async def test_rejects_unknown_code(self) -> None:
        with pytest.raises(ValueError, match="不支持的指数代码"):
            await market_service.get_index_kline(AsyncMock(), "sh999999")

    @pytest.mark.asyncio
    async def test_rejects_unknown_period(self) -> None:
        with pytest.raises(ValueError, match="不支持的 K 线周期"):
            await market_service.get_index_kline(
                AsyncMock(), "sh000001", period="minutely"
            )

    @pytest.mark.asyncio
    async def test_daily_returns_ascending_bars(self) -> None:
        def _bar(day: date, close: float) -> MagicMock:
            bar = MagicMock()
            bar.trade_date = day
            bar.open = close - 1
            bar.high = close + 1
            bar.low = close - 2
            bar.close = close
            bar.volume = 100
            bar.amount = Decimal("1000.5")
            return bar

        # fetch_daily_bars 返回倒序，服务层应反转为升序
        rows = [_bar(date(2026, 7, 17), 101.0), _bar(date(2026, 7, 16), 100.0)]
        with patch.object(
            index_quotation_service, "fetch_daily_bars", AsyncMock(return_value=rows)
        ):
            resp = await market_service.get_index_kline(AsyncMock(), "sh000001")

        assert resp.period == "daily"
        assert resp.name == "上证指数"
        assert [b.date for b in resp.bars] == [date(2026, 7, 16), date(2026, 7, 17)]
        assert resp.bars[-1].close == 101.0
        assert resp.bars[-1].amount == 1000.5

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("code", "expected_name"),
        [("sh510300", "沪深300ETF"), ("CN00Y", "富时A50")],
    )
    async def test_accepts_kline_chart_extra_codes(
        self, code: str, expected_name: str
    ) -> None:
        bar = MagicMock()
        bar.trade_date = date(2026, 7, 17)
        bar.open = 100.0
        bar.high = 101.0
        bar.low = 99.0
        bar.close = 100.5
        bar.volume = 100
        bar.amount = None
        with patch.object(
            index_quotation_service, "fetch_daily_bars", AsyncMock(return_value=[bar])
        ):
            resp = await market_service.get_index_kline(AsyncMock(), code)

        assert resp.code == code
        assert resp.name == expected_name
        assert len(resp.bars) == 1

    @pytest.mark.asyncio
    async def test_weekly_uses_time_bucket(self) -> None:
        rows = [
            {
                "bucket_date": date(2026, 7, 13),
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 103.0,
                "volume": 500,
                "amount": None,
            }
        ]
        with patch.object(
            index_quotation_service, "fetch_aggregated_bars", AsyncMock(return_value=rows)
        ) as mock_fetch:
            resp = await market_service.get_index_kline(
                AsyncMock(), "sh000001", period="weekly"
            )

        assert mock_fetch.await_args.args[2] == "1 week"
        assert resp.period == "weekly"
        assert resp.bars[0].date == date(2026, 7, 13)
        assert resp.bars[0].volume == 500
        assert resp.bars[0].amount is None


@pytest.mark.unit
class TestHistoricalIndexQuotesLocal:
    @pytest.mark.asyncio
    async def test_local_daily_bars_drive_quotes(self) -> None:
        from app.core.constants import INDEX_CODES, KLINE_CHART_EXTRA_CODES

        all_codes = {**INDEX_CODES, **KLINE_CHART_EXTRA_CODES}

        def _bars() -> list[MagicMock]:
            # fetch_daily_bars 返回倒序（最新在前）
            newer = MagicMock()
            newer.trade_date = date(2026, 7, 17)
            newer.close = 101.0
            older = MagicMock()
            older.trade_date = date(2026, 7, 16)
            older.close = 100.0
            return [newer, older]

        with patch.object(
            index_quotation_service,
            "fetch_daily_bars",
            AsyncMock(side_effect=[_bars() for _ in all_codes]),
        ):
            quotes = await market_service._historical_index_quotes(
                AsyncMock(), date(2026, 7, 17)
            )

        assert len(quotes) == len(all_codes)
        assert quotes[0].price == 101.0
        assert quotes[0].change == 1.0
        assert quotes[0].change_pct == 1.0
        assert quotes[0].trend == [100.0, 101.0]
