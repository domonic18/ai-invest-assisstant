"""Unit tests for market overview service."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import market_service


def _scalars_result(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _limit_up_row(**overrides):
    row = MagicMock()
    row.stock_code = overrides.get("stock_code", "000001")
    row.stock_name = overrides.get("stock_name", "平安银行")
    row.change_pct = Decimal("10.0")
    row.latest_price = Decimal("12.5")
    row.sealed_amount = Decimal("1000000")
    row.first_seal_time = "092500"
    row.last_seal_time = "092500"
    row.break_count = 0
    row.limit_stat = "2/2"
    row.consecutive_boards = overrides.get("consecutive_boards", 2)
    row.industry = overrides.get("industry", "银行")
    return row


@pytest.mark.unit
class TestCountBreadth:
    def _row(
        self,
        code: str,
        name: str,
        pct: float,
        price: float,
        high: float,
        low: float,
    ) -> dict:
        return {
            "代码": code,
            "名称": name,
            "最新价": price,
            "涨跌幅": pct,
            "最高": high,
            "最低": low,
            "时间戳": "15:30:01",
        }

    def test_counts_up_down_flat(self) -> None:
        import pandas as pd

        df = pd.DataFrame(
            [
                self._row("sh600001", "甲", 1.0, 10.0, 10.5, 9.8),
                self._row("sz000001", "乙", -2.0, 9.0, 9.5, 8.9),
                self._row("bj920001", "丙", 0.0, 5.0, 5.1, 4.9),
                self._row("sh600002", "丁", float("nan"), 0.0, 0.0, 0.0),
            ]
        )
        result = market_service._count_breadth(df)

        assert result["up_count"] == 1
        assert result["down_count"] == 1
        assert result["flat_count"] == 1

    def test_sealed_limit_up_down_by_board(self) -> None:
        import pandas as pd

        df = pd.DataFrame(
            [
                # 主板封板涨停 / 触板未封（收盘未在最高价）
                self._row("sh600001", "甲", 10.0, 11.0, 11.0, 10.0),
                self._row("sh600002", "乙", 10.0, 10.9, 11.0, 10.0),
                # 创业板 20% 封板
                self._row("sz300001", "丙", 20.0, 12.0, 12.0, 10.5),
                # 科创板 20% 封板
                self._row("sh688001", "丁", 19.9, 11.98, 11.98, 10.0),
                # 北交所 30% 封板
                self._row("bj920001", "戊", 30.0, 13.0, 13.0, 9.5),
                # ST 5% 封板
                self._row("sh600003", "ST己", 5.0, 10.5, 10.5, 9.9),
                # 主板封板跌停 / ST 封板跌停
                self._row("sz000002", "庚", -10.0, 9.0, 9.5, 9.0),
                self._row("sz000003", "*ST辛", -5.0, 9.5, 10.0, 9.5),
            ]
        )
        result = market_service._count_breadth(df)

        assert result["limit_up_count"] == 5
        assert result["limit_down_count"] == 2


@pytest.mark.unit
class TestFetchAmountPair:
    def test_walks_back_over_non_trading_days(self) -> None:
        amounts = {
            date(2026, 7, 17): 2.66e12,
            date(2026, 7, 16): 2.41e12,
        }

        def fake_official(day: date) -> float | None:
            return amounts.get(day)

        with patch.object(
            market_service, "_fetch_official_amount", side_effect=fake_official
        ):
            pair = market_service._fetch_amount_pair(date(2026, 7, 17))

        assert pair["amount"] == 2.66e12
        assert pair["prev_amount"] == 2.41e12

    def test_skips_weekend_to_find_prev(self) -> None:
        amounts = {
            date(2026, 7, 20): 2.5e12,  # 周一
            date(2026, 7, 17): 2.66e12,  # 上周五
        }

        def fake_official(day: date) -> float | None:
            return amounts.get(day)

        with patch.object(
            market_service, "_fetch_official_amount", side_effect=fake_official
        ):
            pair = market_service._fetch_amount_pair(date(2026, 7, 20))

        assert pair["prev_amount"] == 2.66e12


@pytest.mark.unit
class TestGetIndexQuotes:
    @pytest.mark.asyncio
    async def test_uses_cache_when_present(self) -> None:
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
            patch.object(
                market_service, "_cache_get", AsyncMock(side_effect=[spot, [1.0, 2.0]])
            ),
            patch.object(market_service, "_cache_set", AsyncMock()),
        ):
            quotes = await market_service.get_index_quotes()

        assert len(quotes) == 1
        assert quotes[0].code == "sh000001"
        assert quotes[0].trend == [1.0, 2.0]

    @pytest.mark.asyncio
    async def test_fetches_and_caches_when_empty(self) -> None:
        spot = [
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
            patch.object(market_service, "_cache_get", AsyncMock(return_value=None)),
            patch.object(market_service, "_cache_set", AsyncMock()) as cache_set,
            patch.object(
                market_service, "_fetch_index_spot", MagicMock(return_value=spot)
            ),
            patch.object(
                market_service, "_fetch_index_trend", MagicMock(return_value=[1.0])
            ),
        ):
            quotes = await market_service.get_index_quotes()

        assert quotes[0].name == "深证成指"
        assert cache_set.await_count >= 2


@pytest.mark.unit
class TestGetIndexIntraday:
    @pytest.mark.asyncio
    async def test_rejects_unknown_code(self) -> None:
        with pytest.raises(ValueError, match="不支持的指数代码"):
            await market_service.get_index_intraday("sh999999")

    @pytest.mark.asyncio
    async def test_builds_points_and_prev_close(self) -> None:
        intraday = {
            "trade_date": "2026-07-17",
            "points": [
                {"time": "09:31", "price": 3800.0, "volume": 1e8, "amount": 2e9},
                {"time": "09:32", "price": 3801.5, "volume": 9e7, "amount": 1.8e9},
            ],
            "prev_close": 3781.0,
        }
        spot = [
            {
                "code": "sh000001",
                "name": "上证指数",
                "price": 3801.5,
                "change": 20.5,
                "change_pct": 0.54,
                "amount": 5e11,
            }
        ]
        with (
            patch.object(market_service, "_cache_get", AsyncMock(side_effect=[None, spot])),
            patch.object(market_service, "_cache_set", AsyncMock()),
            patch.object(
                market_service, "_fetch_index_intraday", MagicMock(return_value=intraday)
            ),
        ):
            result = await market_service.get_index_intraday("sh000001")

        assert result.trade_date == date(2026, 7, 17)
        assert result.prev_close == 3781.0
        assert len(result.points) == 2
        assert result.points[0].time == "09:31"
        assert result.points[1].volume == 9e7

    @pytest.mark.asyncio
    async def test_historical_date_uses_series_prev_close(self) -> None:
        intraday = {
            "trade_date": "2026-07-16",
            "points": [
                {"time": "09:31", "price": 3780.0, "volume": 1e8, "amount": 2e9},
            ],
            "prev_close": 3775.0,
        }
        with (
            patch.object(market_service, "_cache_get", AsyncMock(return_value=None)),
            patch.object(market_service, "_cache_set", AsyncMock()) as cache_set,
            patch.object(
                market_service, "_fetch_index_intraday", MagicMock(return_value=intraday)
            ) as fetch,
        ):
            result = await market_service.get_index_intraday(
                "sh000001", date(2026, 7, 16)
            )

        fetch.assert_called_once_with("sh000001", date(2026, 7, 16))
        assert result.prev_close == 3775.0
        assert result.trade_date == date(2026, 7, 16)
        # 历史数据缓存 24h
        assert cache_set.await_args.args[2] == market_service._HIST_CACHE_TTL

    @pytest.mark.asyncio
    async def test_historical_date_out_of_range_raises(self) -> None:
        intraday = {"trade_date": "2026-06-01", "points": [], "prev_close": None}
        with (
            patch.object(market_service, "_cache_get", AsyncMock(return_value=None)),
            patch.object(
                market_service, "_fetch_index_intraday", MagicMock(return_value=intraday)
            ),
            pytest.raises(ValueError, match="无分时数据"),
        ):
            await market_service.get_index_intraday("sh000001", date(2026, 6, 1))

    @pytest.mark.asyncio
    async def test_uses_cached_response(self) -> None:
        cached = {
            "code": "sz399006",
            "name": "创业板指",
            "trade_date": "2026-07-17",
            "prev_close": 3400.0,
            "points": [{"time": "09:31", "price": 3401.0, "volume": 1.0, "amount": 2.0}],
        }
        with patch.object(market_service, "_cache_get", AsyncMock(return_value=cached)):
            result = await market_service.get_index_intraday("sz399006")

        assert result.name == "创业板指"
        assert result.prev_close == 3400.0


@pytest.mark.unit
class TestHistoricalBreadth:
    @pytest.mark.asyncio
    async def test_uses_db_limit_up_and_em_limit_down(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 42

        with (
            patch.object(market_service, "_cache_get", AsyncMock(return_value=None)),
            patch.object(market_service, "_cache_set", AsyncMock()),
            patch.object(
                market_service, "_fetch_limit_down_count", MagicMock(return_value=33)
            ),
        ):
            breadth = await market_service._historical_breadth(
                session, date(2026, 7, 16)
            )

        assert breadth["limit_up_count"] == 42
        assert breadth["limit_down_count"] == 33
        assert breadth["up_count"] is None
        assert breadth["down_count"] is None

    @pytest.mark.asyncio
    async def test_historical_stats_without_emotion(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                market_service,
                "_latest_limit_up_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                market_service,
                "_historical_breadth",
                AsyncMock(
                    return_value={
                        "up_count": None,
                        "down_count": None,
                        "flat_count": None,
                        "limit_up_count": 42,
                        "limit_down_count": 33,
                    }
                ),
            ),
            patch.object(
                market_service,
                "_fetch_amount_pair",
                MagicMock(return_value={"amount": 2.4e12, "prev_amount": 2.2e12}),
            ),
            patch.object(
                market_service,
                "_limit_up_rates",
                AsyncMock(return_value=(0.3, 0.2, 8)),
            ),
            patch.object(market_service, "_cache_get", AsyncMock(return_value=None)),
            patch.object(market_service, "_cache_set", AsyncMock()),
        ):
            stats = await market_service.get_market_stats(session, date(2026, 7, 16))

        assert stats.trade_date == date(2026, 7, 16)
        assert stats.up_count is None
        assert stats.limit_up_count == 42
        assert stats.limit_down_count == 33
        assert stats.emotion_score is None
        assert stats.emotion_label is None
        assert stats.amount == 2.4e12
        assert stats.amount_change_pct == pytest.approx(9.09, abs=0.01)


@pytest.mark.unit
class TestZtPoolFallback:
    def _pool(self) -> list[dict]:
        return [
            {
                "stock_code": "002632",
                "stock_name": "道明光学",
                "change_pct": 10.06,
                "latest_price": 9.63,
                "sealed_amount": 1.3e8,
                "first_seal_time": "092500",
                "last_seal_time": "092500",
                "break_count": 0,
                "limit_stat": "1/1",
                "consecutive_boards": 1,
                "industry": "塑料",
            },
            {
                "stock_code": "603580",
                "stock_name": "艾艾精工",
                "change_pct": 9.99,
                "latest_price": 40.84,
                "sealed_amount": 2.7e8,
                "first_seal_time": "092501",
                "last_seal_time": "092501",
                "break_count": 0,
                "limit_stat": "6/5",
                "consecutive_boards": 3,
                "industry": "塑料",
            },
        ]

    @pytest.mark.asyncio
    async def test_breadth_falls_back_to_em_pool(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 0

        with (
            patch.object(market_service, "_cache_get", AsyncMock(return_value=None)),
            patch.object(market_service, "_cache_set", AsyncMock()),
            patch.object(
                market_service,
                "_fetch_zt_pool_items",
                MagicMock(return_value=self._pool()),
            ),
            patch.object(
                market_service, "_fetch_limit_down_count", MagicMock(return_value=33)
            ),
        ):
            breadth = await market_service._historical_breadth(
                session, date(2026, 7, 16)
            )

        assert breadth["limit_up_count"] == 2
        assert breadth["limit_down_count"] == 33

    @pytest.mark.asyncio
    async def test_rates_fall_back_to_em_pool(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 0

        with (
            patch.object(market_service, "_cache_get", AsyncMock(return_value=None)),
            patch.object(market_service, "_cache_set", AsyncMock()),
            patch.object(
                market_service,
                "_fetch_zt_pool_items",
                MagicMock(return_value=self._pool()),
            ),
            patch.object(
                market_service, "_fetch_broken_pool_count", MagicMock(return_value=1)
            ),
        ):
            continuous_rate, broken_rate, broken_count = (
                await market_service._limit_up_rates(session, date(2026, 7, 16))
            )

        assert continuous_rate == 0.5
        assert broken_count == 1
        assert broken_rate == round(1 / 3, 4)

    @pytest.mark.asyncio
    async def test_limit_up_falls_back_to_em_pool(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([])

        with patch.object(
            market_service,
            "_zt_pool_items",
            AsyncMock(return_value=self._pool()),
        ):
            result = await market_service.get_limit_up(session, date(2026, 7, 16))

        assert result.total == 2
        assert result.continuous == 1
        assert result.first_board == 1
        assert result.max_boards == 3
        assert result.items[0].stock_code == "603580"
        assert result.ladder[0].stock_name == "艾艾精工"


@pytest.mark.unit
class TestHistoricalIndexQuotes:
    @pytest.mark.asyncio
    async def test_picks_close_for_requested_date(self) -> None:
        series = [
            {"date": "2026-07-15", "close": 100.0},
            {"date": "2026-07-16", "close": 102.0},
            {"date": "2026-07-17", "close": 101.0},
        ]
        with patch.object(
            market_service, "_cache_get", AsyncMock(return_value=series)
        ):
            quotes = await market_service.get_index_quotes(date(2026, 7, 16))

        assert len(quotes) == len(market_service.INDEX_CODES)
        assert quotes[0].price == 102.0
        assert quotes[0].change == 2.0
        assert quotes[0].change_pct == 2.0
        assert quotes[0].trend == [100.0, 102.0]

    @pytest.mark.asyncio
    async def test_non_trading_day_returns_empty(self) -> None:
        series = [{"date": "2026-07-17", "close": 100.0}]
        with patch.object(
            market_service, "_cache_get", AsyncMock(return_value=series)
        ):
            quotes = await market_service.get_index_quotes(date(2026, 7, 16))

        assert quotes == []


@pytest.mark.unit
class TestFetchIndexIntradayHistory:
    def _df(self):
        import pandas as pd

        rows = [
            ("2026-07-16 09:31:00", 100.0),
            ("2026-07-16 15:00:00", 101.0),
            ("2026-07-17 09:31:00", 102.0),
            ("2026-07-17 15:00:00", 103.0),
        ]
        return pd.DataFrame(
            {
                "day": [r[0] for r in rows],
                "close": [r[1] for r in rows],
                "volume": [1.0] * 4,
                "amount": [2.0] * 4,
            }
        )

    def test_filters_requested_day_and_prev_close(self) -> None:
        import sys

        fake_ak = MagicMock()
        fake_ak.stock_zh_a_minute.return_value = self._df()
        with patch.dict(sys.modules, {"akshare": fake_ak}):
            result = market_service._fetch_index_intraday(
                "sh000001", date(2026, 7, 16)
            )

        assert result["trade_date"] == "2026-07-16"
        assert len(result["points"]) == 2
        assert result["points"][0]["time"] == "09:31"
        assert result["prev_close"] is None

    def test_prev_close_from_previous_day(self) -> None:
        import sys

        fake_ak = MagicMock()
        fake_ak.stock_zh_a_minute.return_value = self._df()
        with patch.dict(sys.modules, {"akshare": fake_ak}):
            result = market_service._fetch_index_intraday(
                "sh000001", date(2026, 7, 17)
            )

        assert result["prev_close"] == 101.0

    def test_latest_day_when_no_date(self) -> None:
        import sys

        fake_ak = MagicMock()
        fake_ak.stock_zh_a_minute.return_value = self._df()
        with patch.dict(sys.modules, {"akshare": fake_ak}):
            result = market_service._fetch_index_intraday("sh000001", None)

        assert result["trade_date"] == "2026-07-17"
        assert result["prev_close"] == 101.0


@pytest.mark.unit
class TestGetLimitUp:
    @pytest.mark.asyncio
    async def test_groups_ladder_and_first_board(self) -> None:
        rows = [
            _limit_up_row(stock_code="000001", consecutive_boards=3),
            _limit_up_row(stock_code="000002", consecutive_boards=2),
            _limit_up_row(stock_code="000003", consecutive_boards=1),
        ]
        session = AsyncMock()
        session.execute.return_value = _scalars_result(rows)

        result = await market_service.get_limit_up(session, date(2026, 7, 17))

        assert result.total == 3
        assert result.continuous == 2
        assert result.first_board == 1
        assert result.max_boards == 3
        assert len(result.ladder) == 2
        assert {item.stock_code for item in result.ladder} == {"000001", "000002"}

    @pytest.mark.asyncio
    async def test_empty_when_no_data(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = None

        result = await market_service.get_limit_up(session)

        assert result.total == 0
        assert result.ladder == []


@pytest.mark.unit
class TestEmotionScore:
    def test_hot_market_scores_high(self) -> None:
        score, ratio = market_service._emotion_score(
            up=2847, down=1562, flat=100, limit_up=128,
            continuous_rate=0.36, broken_rate=0.18,
        )
        assert score > 60
        assert ratio == pytest.approx(2.84, abs=0.01)

    def test_cold_market_scores_low(self) -> None:
        score, _ = market_service._emotion_score(
            up=400, down=4700, flat=50, limit_up=10,
            continuous_rate=0.10, broken_rate=0.45,
        )
        assert score < 40

    def test_clamped_to_bounds(self) -> None:
        score, _ = market_service._emotion_score(
            up=5000, down=0, flat=0, limit_up=500,
            continuous_rate=1.0, broken_rate=0.0,
        )
        assert 0 <= score <= 100


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
            market_service, "get_limit_up", AsyncMock(return_value=limit_up)
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


@pytest.mark.unit
class TestGetWatchlistQuotes:
    @pytest.mark.asyncio
    async def test_prefers_redis_quote(self) -> None:
        watch = MagicMock()
        watch.stock_code = "000001"
        watch.tags = ["银行"]

        session = AsyncMock()
        session.execute.return_value = _scalars_result([watch])

        redis = AsyncMock()
        redis.get.return_value = (
            b'{"stock_name":"\\u5e73\\u5b89\\u94f6\\u884c","price":12.5,'
            b'"pct_change":1.2,"amount":1e8,"updated_at":"2026-07-17"}'
        )

        with patch.object(market_service, "_redis", MagicMock(return_value=redis)):
            quotes = await market_service.get_watchlist_quotes(session, user_id=1)

        assert len(quotes) == 1
        assert quotes[0].price == 12.5
        assert quotes[0].change_pct == 1.2
        redis.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_kline(self) -> None:
        watch = MagicMock()
        watch.stock_code = "600000"
        watch.tags = []

        kline = MagicMock()
        kline.close = Decimal("10.5")
        kline.pct_change = Decimal("-0.5")
        kline.amount = Decimal("5000000")
        kline.trade_date = date(2026, 7, 16)

        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result([watch]),
            MagicMock(scalar_one_or_none=MagicMock(return_value=kline)),
        ]

        redis = AsyncMock()
        redis.get.return_value = None

        with patch.object(market_service, "_redis", MagicMock(return_value=redis)):
            quotes = await market_service.get_watchlist_quotes(session, user_id=1)

        assert quotes[0].price == 10.5
        assert quotes[0].updated_at == "2026-07-16"
