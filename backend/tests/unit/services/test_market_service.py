"""Unit tests for market overview service."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

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
class TestAmountPair:
    """官方成交额只读 market_amount：最新两行即当日与前一有数据交易日。"""

    @pytest.mark.asyncio
    async def test_returns_latest_two_rows(self) -> None:
        rows = [
            MagicMock(amount=Decimal("2660000000000")),
            MagicMock(amount=Decimal("2410000000000")),
        ]
        session = AsyncMock()
        session.execute.return_value = _scalars_result(rows)

        amount, prev = await market_service._amount_pair(session, date(2026, 7, 17))

        assert amount == 2.66e12
        assert prev == 2.41e12

    @pytest.mark.asyncio
    async def test_empty_returns_none_pair(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([])

        assert await market_service._amount_pair(session, date(2026, 7, 17)) == (
            None,
            None,
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
            patch.object(market_service, "_index_spot", AsyncMock(return_value=spot)),
            patch.object(
                market_service,
                "_local_index_closes",
                AsyncMock(return_value=[1.0, 2.0]),
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
            patch.object(market_service, "_index_spot", AsyncMock(return_value=None)),
            patch.object(
                market_service, "_db_index_spot", AsyncMock(return_value=db_spot)
            ),
            patch.object(
                market_service, "_local_index_closes", AsyncMock(return_value=[1.0])
            ),
        ):
            quotes = await market_service.get_index_quotes(AsyncMock())

        assert quotes[0].name == "深证成指"
        assert quotes[0].price == 10868.24

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
            market_service, "fetch_daily_bars", AsyncMock(return_value=bars)
        ):
            spot = await market_service._db_index_spot(AsyncMock())

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
                market_service,
                "latest_minute_day",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                market_service, "fetch_minute_bars", AsyncMock(return_value=bars)
            ),
            patch.object(
                market_service, "prev_minute_close", AsyncMock(return_value=3781.0)
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
                market_service, "fetch_minute_bars", AsyncMock(return_value=bars)
            ),
            patch.object(
                market_service, "prev_minute_close", AsyncMock(return_value=None)
            ),
            patch.object(
                market_service,
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
                market_service, "fetch_minute_bars", AsyncMock(return_value=[])
            ),
            pytest.raises(ValueError, match="无分时数据"),
        ):
            await market_service.get_index_intraday(
                AsyncMock(), "sh000001", date(2026, 6, 1)
            )

    @pytest.mark.asyncio
    async def test_empty_when_no_minute_data(self) -> None:
        with patch.object(
            market_service, "latest_minute_day", AsyncMock(return_value=None)
        ):
            result = await market_service.get_index_intraday(AsyncMock(), "sh000001")

        assert result.points == []
        assert result.name == "上证指数"


@pytest.mark.unit
class TestHistoricalBreadth:
    @pytest.mark.asyncio
    async def test_prefers_market_breadth_row(self) -> None:
        """market_breadth 有当日行且涨停池未覆盖时返回行内全量统计。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=3000,
            down_count=1800,
            flat_count=200,
            limit_up_count=55,
            limit_down_count=12,
        )
        # 第一次 scalar 查 market_breadth 行，第二次查涨停池家数（未覆盖）
        session.scalar.side_effect = [row, None]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 17)
        )

        assert breadth == {
            "up_count": 3000,
            "down_count": 1800,
            "flat_count": 200,
            "limit_up_count": 55,
            "limit_down_count": 12,
        }

    @pytest.mark.asyncio
    async def test_pool_count_overrides_row_limit_up(self) -> None:
        """涨停池已覆盖当日时，涨停数覆盖为池计数（官方池口径，不含 ST）。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=3000,
            down_count=1800,
            flat_count=200,
            limit_up_count=55,
            limit_down_count=12,
        )
        session.scalar.side_effect = [row, 53]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 17)
        )

        assert breadth["limit_up_count"] == 53
        assert breadth["limit_down_count"] == 12

    @pytest.mark.asyncio
    async def test_falls_back_to_limit_up_pool_count(self) -> None:
        """表内无当日行时：涨停数取 limit_up_pool 计数，其余为空口径。"""
        session = AsyncMock()
        # 第一次 scalar 查 market_breadth 行（无），第二次查涨停池家数
        session.scalar.side_effect = [None, 42]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 16)
        )

        assert breadth["limit_up_count"] == 42
        assert breadth["limit_down_count"] == 0
        assert breadth["up_count"] is None
        assert breadth["down_count"] is None

    @pytest.mark.asyncio
    async def test_all_null_breadth_row_falls_back(self) -> None:
        """非交易日运行残留的全空 breadth 行视为无数据，回退涨停池计数。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=None,
            down_count=None,
            flat_count=None,
            limit_up_count=None,
            limit_down_count=None,
        )
        session.scalar.side_effect = [row, 33]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 17)
        )

        assert breadth["limit_up_count"] == 33
        assert breadth["up_count"] is None

    @pytest.mark.asyncio
    async def test_fallback_preserves_row_limit_down_count(self) -> None:
        """回退合并时保留行内跌停数（limit-down-pool 补采写入）。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=None,
            down_count=None,
            flat_count=None,
            limit_up_count=None,
            limit_down_count=9,
        )
        session.scalar.side_effect = [row, 33]

        breadth = await market_service._historical_breadth(
            session, date(2026, 7, 17)
        )

        assert breadth["limit_up_count"] == 33
        assert breadth["limit_down_count"] == 9

    @pytest.mark.asyncio
    async def test_historical_stats_without_emotion(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                market_service,
                "resolve_latest_trade_date",
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
                "_amount_pair",
                AsyncMock(return_value=(2.4e12, 2.2e12)),
            ),
            patch.object(
                market_service,
                "_limit_up_rates",
                AsyncMock(return_value=(0.3, 0.2, 8)),
            ),
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
class TestLimitUpRates:
    """连板率读 limit_up_pool，炸板家数读 market_breadth.broken_count。"""

    @pytest.mark.asyncio
    async def test_rates_from_db(self) -> None:
        session = AsyncMock()
        # 依次：涨停总数、连板数、炸板家数
        session.scalar.side_effect = [3, 1, 1]

        continuous_rate, broken_rate, broken_count = (
            await market_service._limit_up_rates(session, date(2026, 7, 16))
        )

        assert continuous_rate == round(1 / 3, 4)
        assert broken_count == 1
        assert broken_rate == 0.25

    @pytest.mark.asyncio
    async def test_empty_pool_returns_none_rates(self) -> None:
        session = AsyncMock()
        session.scalar.side_effect = [0, None]  # 无涨停池 → 跳过连板查询；无炸板行

        continuous_rate, broken_rate, broken_count = (
            await market_service._limit_up_rates(session, date(2026, 7, 16))
        )

        assert continuous_rate is None
        assert broken_rate is None
        assert broken_count is None


@pytest.mark.unit
class TestHistoricalIndexQuotes:
    """历史指数行情只读本地 kline_daily（服务层倒序反转为升序序列）。"""

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
            market_service, "fetch_daily_bars", AsyncMock(return_value=bars)
        ):
            quotes = await market_service.get_index_quotes(
                AsyncMock(), date(2026, 7, 16)
            )

        assert len(quotes) == len(market_service.INDEX_CODES)
        assert quotes[0].price == 102.0
        assert quotes[0].change == 2.0
        assert quotes[0].change_pct == 2.0
        assert quotes[0].trend == [100.0, 102.0]

    @pytest.mark.asyncio
    async def test_non_trading_day_returns_empty(self) -> None:
        bars = [self._bar(date(2026, 7, 17), 100.0)]
        with patch.object(
            market_service, "fetch_daily_bars", AsyncMock(return_value=bars)
        ):
            quotes = await market_service.get_index_quotes(
                AsyncMock(), date(2026, 7, 16)
            )

        assert quotes == []


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
        session.execute.return_value = _scalars_result([])
        with patch.object(
            market_service, "fetch_max_daily_date", AsyncMock(return_value=None)
        ):
            result = await market_service.get_limit_up(session)

        assert result.total == 0
        assert result.ladder == []
        assert result.trade_date == date.today()

    @pytest.mark.asyncio
    async def test_intraday_today_does_not_fall_back_to_previous_pool(self) -> None:
        """盘中（当日已有涨跌统计、涨停池未写入）返回当日空结果，而非旧池。"""
        today = date.today()
        session = AsyncMock()
        session.scalar.return_value = 1  # 当日已有 market_breadth 行
        session.execute.return_value = _scalars_result([])  # 当日涨停池为空
        with patch.object(
            market_service,
            "fetch_max_daily_date",
            AsyncMock(return_value=today - timedelta(days=3)),
        ):
            result = await market_service.get_limit_up(session)

        expected = today if today.weekday() < 5 else today - timedelta(days=3)
        assert result.trade_date == expected
        assert result.total == 0


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
        # 共享 Redis 客户端复用连接，单次查询后不应关闭
        redis.close.assert_not_awaited()

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
            market_service, "fetch_daily_bars", AsyncMock(return_value=rows)
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
            market_service, "fetch_daily_bars", AsyncMock(return_value=[bar])
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
            market_service, "fetch_aggregated_bars", AsyncMock(return_value=rows)
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
        from app.core.constants import INDEX_CODES

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
            market_service,
            "fetch_daily_bars",
            AsyncMock(side_effect=[_bars() for _ in INDEX_CODES]),
        ):
            quotes = await market_service._historical_index_quotes(
                AsyncMock(), date(2026, 7, 17)
            )

        assert len(quotes) == len(INDEX_CODES)
        assert quotes[0].price == 101.0
        assert quotes[0].change == 1.0
        assert quotes[0].change_pct == 1.0
        assert quotes[0].trend == [100.0, 101.0]


@pytest.mark.unit
class TestLiveBreadth:
    """当日涨跌统计只读 market_breadth 表：最新行直返、无行返回空统计。"""

    @pytest.mark.asyncio
    async def test_returns_latest_row(self) -> None:
        session = AsyncMock()
        row = MagicMock(
            up_count=2500,
            down_count=2100,
            flat_count=300,
            limit_up_count=60,
            limit_down_count=15,
        )
        # 第一次 scalar 查 market_breadth 最新行，第二次查涨停池家数（未覆盖）
        session.scalar.side_effect = [row, None]

        breadth = await market_service._live_breadth(session, date(2026, 7, 17))

        assert breadth == {
            "up_count": 2500,
            "down_count": 2100,
            "flat_count": 300,
            "limit_up_count": 60,
            "limit_down_count": 15,
        }

    @pytest.mark.asyncio
    async def test_pool_count_overrides_snapshot_limit_up(self) -> None:
        """涨停池入库后，当日涨停数覆盖为池计数（快照估算仅盘中使用）。"""
        session = AsyncMock()
        row = MagicMock(
            up_count=2500,
            down_count=2100,
            flat_count=300,
            limit_up_count=60,
            limit_down_count=15,
        )
        session.scalar.side_effect = [row, 53]

        breadth = await market_service._live_breadth(session, date(2026, 7, 17))

        assert breadth["limit_up_count"] == 53
        assert breadth["limit_down_count"] == 15

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_row(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = None

        breadth = await market_service._live_breadth(session, date(2026, 7, 17))

        assert breadth["up_count"] is None
        assert breadth["down_count"] is None
        assert breadth["limit_up_count"] == 0
        assert breadth["limit_down_count"] == 0


@pytest.mark.unit
class TestResolveLatestTradeDate:
    @pytest.mark.asyncio
    async def test_returns_today_when_no_kline(self) -> None:
        session = AsyncMock()
        with patch.object(
            market_service, "fetch_max_daily_date", AsyncMock(return_value=None)
        ):
            assert await market_service.resolve_latest_trade_date(session) == (
                date.today()
            )

    @pytest.mark.asyncio
    async def test_intraday_returns_today_when_breadth_exists(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 1  # 当日已有涨跌统计
        today = date.today()
        kline_max = today - timedelta(days=3)
        with patch.object(
            market_service,
            "fetch_max_daily_date",
            AsyncMock(return_value=kline_max),
        ):
            result = await market_service.resolve_latest_trade_date(session)
        expected = today if today.weekday() < 5 else kline_max
        assert result == expected

    @pytest.mark.asyncio
    async def test_falls_back_to_kline_max_without_breadth(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 0
        kline_max = date(2026, 7, 17)
        with patch.object(
            market_service,
            "fetch_max_daily_date",
            AsyncMock(return_value=kline_max),
        ):
            assert await market_service.resolve_latest_trade_date(session) == (
                kline_max
            )


@pytest.mark.unit
class TestIsTradingDay:
    @pytest.mark.asyncio
    async def test_weekend_is_not_trading_day(self) -> None:
        session = AsyncMock()
        assert await market_service.is_trading_day(
            session, date(2026, 7, 19)
        ) is False  # 周日

    @pytest.mark.asyncio
    async def test_past_day_with_kline_bar(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                market_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                market_service, "has_daily_bar", AsyncMock(return_value=True)
            ),
        ):
            assert await market_service.is_trading_day(
                session, date(2026, 7, 17)
            ) is True

    @pytest.mark.asyncio
    async def test_past_day_without_kline_bar_is_holiday(self) -> None:
        session = AsyncMock()
        with (
            patch.object(
                market_service,
                "fetch_max_daily_date",
                AsyncMock(return_value=date(2026, 7, 17)),
            ),
            patch.object(
                market_service, "has_daily_bar", AsyncMock(return_value=False)
            ),
        ):
            assert await market_service.is_trading_day(
                session, date(2026, 7, 16)
            ) is False

    @pytest.mark.asyncio
    async def test_future_weekday_after_kline_max_allowed(self) -> None:
        session = AsyncMock()
        with patch.object(
            market_service,
            "fetch_max_daily_date",
            AsyncMock(return_value=date(2026, 7, 17)),
        ):
            assert await market_service.is_trading_day(
                session, date(2026, 7, 20)
            ) is True


@pytest.mark.unit
class TestBackfillTradeDate:
    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        session = AsyncMock()
        with pytest.raises(market_service.NonTradingDayError):
            await market_service.backfill_trade_date(session, date(2026, 7, 19))

    @pytest.mark.asyncio
    async def test_dispatches_backfill_tasks_in_order(self) -> None:
        session = AsyncMock()
        day = date(2026, 7, 17)
        calls: list[tuple[str, dict]] = []

        async def fake_dispatch(
            session: object, task_name: str, params: dict, **kwargs: object
        ) -> MagicMock:
            calls.append((task_name, params))
            return MagicMock(id=len(calls))

        with (
            patch.object(
                market_service, "is_trading_day", AsyncMock(return_value=True)
            ),
            patch(
                "collector.runtime.dispatcher.dispatch_collector_task",
                side_effect=fake_dispatch,
            ),
        ):
            results = await market_service.backfill_trade_date(session, day)

        expected = [
            "limit-up-pool",
            "broken-pool",
            "limit-down-pool",
            "market-amount",
            "sector-fund-flow",
        ]
        assert [name for name, _ in calls] == expected
        assert all(p["trade_date"] == "2026-07-17" for _, p in calls)
        assert [r.task for r in results] == expected
        assert all(r.status == "dispatched" for r in results)
