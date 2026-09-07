"""涨停池服务（limit_pool_service）契约测试。

测试 patch 目标按函数实际定义模块定向。"""


from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.clock import today_cn
from app.services.market import (
    limit_pool_service,
    market_service,
    trade_calendar_service,
)


def _scalars_result(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _patch_attribution_cache(output: dict | None):
    """patch ai_analysis_repository.load_latest_success 返回归因缓存行。

    output=None 等价于缓存未命中；否则 row.structured_output=output。
    """
    if output is None:
        return patch(
            "app.repositories.review.ai_analysis_repository.load_latest_success",
            AsyncMock(return_value=None),
        )
    row = MagicMock()
    row.structured_output = output
    return patch(
        "app.repositories.review.ai_analysis_repository.load_latest_success",
        AsyncMock(return_value=row),
    )


def _limit_up_row(**overrides):
    row = MagicMock()
    row.stock_code = overrides.get("stock_code", "000001")
    row.stock_name = overrides.get("stock_name", "平安银行")
    row.change_pct = Decimal("10.0")
    row.latest_price = Decimal("12.5")
    row.sealed_amount = Decimal("1000000")
    row.first_seal_time = overrides.get("first_seal_time", "092500")
    row.last_seal_time = "092500"
    row.broken_limit_count = overrides.get("broken_limit_count", 0)
    row.limit_status = "2/2"
    row.consecutive_boards = overrides.get("consecutive_boards", 2)
    row.industry = overrides.get("industry", "银行")
    return row



def _sector_row(sector_name, change_pct=None, main_net_inflow=None):
    return MagicMock(
        sector_name=sector_name,
        change_pct=Decimal(str(change_pct)) if change_pct is not None else None,
        main_net_inflow=(
            Decimal(str(main_net_inflow)) if main_net_inflow is not None else None
        ),
    )


@pytest.mark.unit
class TestLimitUpRates:
    """连板率读 pool_limit_up_stock，炸板家数读 market_breadth.broken_limit_count。"""

    @pytest.mark.asyncio
    async def test_rates_from_db(self) -> None:
        session = AsyncMock()
        # 依次：涨停总数、连板数、炸板家数
        session.scalar.side_effect = [3, 1, 1]

        continuous_rate, broken_rate, broken_limit_count = (
            await market_service._limit_up_rates(session, date(2026, 7, 16))
        )

        assert continuous_rate == round(1 / 3, 4)
        assert broken_limit_count == 1
        assert broken_rate == 0.25

    @pytest.mark.asyncio
    async def test_empty_pool_returns_none_rates(self) -> None:
        session = AsyncMock()
        session.scalar.side_effect = [0, None]  # 无涨停池 → 跳过连板查询；无炸板行

        continuous_rate, broken_rate, broken_limit_count = (
            await market_service._limit_up_rates(session, date(2026, 7, 16))
        )

        assert continuous_rate is None
        assert broken_rate is None
        assert broken_limit_count is None


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
        session.execute.side_effect = [
            _scalars_result(rows),  # 涨停池
            _scalars_result([]),  # 板块资金流查询
        ]

        with _patch_attribution_cache(None):
            result = await market_service.get_limit_up(session, date(2026, 7, 17))

        assert result.total == 3
        assert result.continuous == 2
        assert result.first_board == 1
        assert result.max_boards == 3
        assert len(result.ladder) == 2
        assert {item.stock_code for item in result.ladder} == {"000001", "000002"}
        assert result.ai_generated is False

    @pytest.mark.asyncio
    async def test_seal_type_derivation(self) -> None:
        rows = [
            _limit_up_row(stock_code="000001", first_seal_time="092500", broken_limit_count=0),
            _limit_up_row(stock_code="000002", first_seal_time="092500", broken_limit_count=3),
            _limit_up_row(stock_code="000003", first_seal_time="101215", broken_limit_count=0),
            _limit_up_row(stock_code="000004", first_seal_time=None, broken_limit_count=None),
        ]
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(rows),
            _scalars_result([]),
        ]

        with _patch_attribution_cache(None):
            result = await market_service.get_limit_up(session, date(2026, 7, 17))

        seal_types = {item.stock_code: item.seal_type for item in result.items}
        assert seal_types == {
            "000001": "一字板",
            "000002": "T字板",
            "000003": None,
            "000004": None,
        }

    @pytest.mark.asyncio
    async def test_groups_sorted_by_count_with_sector_stats(self) -> None:
        rows = [
            _limit_up_row(stock_code="000001", industry="电力", consecutive_boards=3),
            _limit_up_row(
                stock_code="000002",
                industry="电力",
                consecutive_boards=1,
                first_seal_time="094500",
            ),
            _limit_up_row(stock_code="000003", industry="白酒Ⅱ", consecutive_boards=1),
        ]
        sectors = [
            _sector_row("电力", change_pct=4.8, main_net_inflow=6390000000),
            _sector_row("白酒", change_pct=3.79, main_net_inflow=3656000000),
        ]
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(rows),
            _scalars_result(sectors),
        ]

        with _patch_attribution_cache(None):
            result = await market_service.get_limit_up(session, date(2026, 7, 17))

        assert [group.name for group in result.groups] == ["电力", "白酒Ⅱ"]
        power = result.groups[0]
        assert power.count == 2
        assert power.change_pct == pytest.approx(4.8)
        assert power.main_net_inflow == pytest.approx(6390000000)
        # 组内按板数降序、同板按首次封板时间升序
        assert [item.stock_code for item in power.items] == ["000001", "000002"]
        # "白酒Ⅱ" 归一化后匹配板块资金流中的 "白酒"
        liquor = result.groups[1]
        assert liquor.change_pct == pytest.approx(3.79)

    @pytest.mark.asyncio
    async def test_groups_other_industry_sorted_last(self) -> None:
        rows = [
            _limit_up_row(stock_code="000001", industry=None, consecutive_boards=1),
            _limit_up_row(stock_code="000002", industry="电力", consecutive_boards=1),
            _limit_up_row(stock_code="000003", industry="电力", consecutive_boards=1),
        ]
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(rows),
            _scalars_result([]),
        ]

        with _patch_attribution_cache(None):
            result = await market_service.get_limit_up(session, date(2026, 7, 17))

        assert [group.name for group in result.groups] == ["电力", "其他"]
        assert result.groups[-1].change_pct is None

    @pytest.mark.asyncio
    async def test_group_sector_stats_fuzzy_containment(self) -> None:
        """hybk "煤炭开采" 通过互相包含匹配板块名 "煤炭开采加工"。"""
        rows = [_limit_up_row(stock_code="000001", industry="煤炭开采")]
        sectors = [
            _sector_row("煤炭开采加工", change_pct=5.3, main_net_inflow=1163000000)
        ]
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(rows),
            _scalars_result(sectors),
        ]

        with _patch_attribution_cache(None):
            result = await market_service.get_limit_up(session, date(2026, 7, 17))

        assert result.groups[0].change_pct == pytest.approx(5.3)

    @pytest.mark.asyncio
    async def test_ai_groups_when_attribution_cached(self) -> None:
        """有 AI 归因缓存时按题材分组：组带原因、个股带题材、未覆盖股入「其他」。"""
        rows = [
            _limit_up_row(stock_code="000001", industry="电力", consecutive_boards=3),
            _limit_up_row(stock_code="000002", industry="电力", consecutive_boards=1),
            _limit_up_row(stock_code="000003", industry="白酒Ⅱ", consecutive_boards=1),
        ]
        attribution = {
            "groups": [
                {
                    "theme": "电力改革",
                    "reason": "容量电价政策催化，板块集体走强",
                    "stock_codes": ["000001", "000002"],
                }
            ],
            "stock_themes": {
                "000001": ["电力改革", "绿电"],
                "000002": ["电力改革"],
            },
        }
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(rows),
        ]

        with _patch_attribution_cache(attribution):
            result = await market_service.get_limit_up(session, date(2026, 7, 17))

        assert result.ai_generated is True
        assert [group.name for group in result.groups] == ["电力改革", "其他"]
        ai_group = result.groups[0]
        assert ai_group.reason == "容量电价政策催化，板块集体走强"
        assert ai_group.change_pct is None
        # 组内按板数降序
        assert [item.stock_code for item in ai_group.items] == ["000001", "000002"]
        other = result.groups[1]
        assert [item.stock_code for item in other.items] == ["000003"]
        assert other.reason is None

        themes = {item.stock_code: item.themes for item in result.items}
        assert themes["000001"] == ["电力改革", "绿电"]
        assert themes["000003"] == []

    @pytest.mark.asyncio
    async def test_ai_groups_filter_hallucinated_codes(self) -> None:
        """AI 缓存中的幻觉代码被过滤，不进入任何分组。"""
        rows = [_limit_up_row(stock_code="000001", industry="电力")]
        attribution = {
            "groups": [
                {
                    "theme": "电力改革",
                    "reason": "政策催化",
                    "stock_codes": ["000001", "999999"],
                }
            ],
            "stock_themes": {"999999": ["电力改革"]},
        }
        session = AsyncMock()
        session.execute.side_effect = [
            _scalars_result(rows),
        ]

        with _patch_attribution_cache(attribution):
            result = await market_service.get_limit_up(session, date(2026, 7, 17))

        assert result.ai_generated is True
        assert len(result.groups) == 1
        assert [item.stock_code for item in result.groups[0].items] == ["000001"]
        assert result.items[0].themes == []

    @pytest.mark.asyncio
    async def test_empty_when_no_data(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([])
        with patch.object(
            trade_calendar_service, "fetch_max_daily_date", AsyncMock(return_value=None)
        ):
            result = await market_service.get_limit_up(session)

        assert result.total == 0
        assert result.ladder == []
        assert result.trade_date == today_cn()

    @pytest.mark.asyncio
    async def test_intraday_today_does_not_fall_back_to_previous_pool(self) -> None:
        """盘中（当日已有涨跌统计、涨停池未写入）返回当日空结果，而非旧池。"""
        today = today_cn()
        session = AsyncMock()
        session.scalar.return_value = 1  # 当日已有 market_breadth 行
        session.execute.return_value = _scalars_result([])  # 当日涨停池为空
        with patch.object(
            trade_calendar_service,
            "fetch_max_daily_date",
            AsyncMock(return_value=today - timedelta(days=3)),
        ):
            result = await market_service.get_limit_up(session)

        expected = today if today.weekday() < 5 else today - timedelta(days=3)
        assert result.trade_date == expected
        assert result.total == 0


@pytest.mark.unit
class TestGetLimitUpIntraday:
    def _bars(self, code: str, closes: list[float]) -> list[MagicMock]:
        return [
            MagicMock(stock_code=code, close=Decimal(str(close))) for close in closes
        ]

    @pytest.mark.asyncio
    async def test_downsamples_to_60_points(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result(["600001"])
        bars = self._bars("600001", [float(i) for i in range(240)])
        with patch.object(
            limit_pool_service, "fetch_minute_bars_multi", AsyncMock(return_value=bars)
        ):
            result = await market_service.get_limit_up_intraday(
                session, date(2026, 7, 21)
            )

        series = result.series["600001"]
        assert len(series) == 60
        assert series[0] == 0.0
        assert series[-1] == 239.0

    @pytest.mark.asyncio
    async def test_stocks_without_minute_data_are_omitted(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result(["600001", "000001"])
        bars = self._bars("600001", [10.0, 10.5, 11.0])
        with patch.object(
            limit_pool_service, "fetch_minute_bars_multi", AsyncMock(return_value=bars)
        ):
            result = await market_service.get_limit_up_intraday(
                session, date(2026, 7, 21)
            )

        assert set(result.series) == {"600001"}
        # 不足 60 点时原样返回
        assert result.series["600001"] == [10.0, 10.5, 11.0]
