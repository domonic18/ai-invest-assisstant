"""自选股行情服务单测：名称兜底、分钟 trend 降采样。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.market import WatchlistQuoteItem
from app.services.user import watchlist_quote_service as wsvc


def _scalars_result(rows: list) -> MagicMock:
    return MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )


def _watch(code: str) -> MagicMock:
    watch = MagicMock()
    watch.stock_code = code
    watch.tags = []
    return watch


@pytest.mark.unit
class TestGetWatchlistQuotes:
    @pytest.mark.asyncio
    async def test_redis_hit_prefers_snapshot_name(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([_watch("000001")])

        redis = AsyncMock()
        redis.get.return_value = (
            b'{"stock_name":"\xe5\xb9\xb3\xe5\xae\x89\xe9\x93\xb6\xe8\xa1\x8c",'
            b'"price":12.5,"change_pct":1.2,"amount":1e8,"updated_at":"2026-09-02"}'
        )
        bars = [SimpleNamespace(stock_code="000001", close=float(i + 1)) for i in range(30)]

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(
                wsvc, "_load_stock_names", AsyncMock(return_value={"000001": "基本表名称"})
            ),
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 2)),
            ),
            patch.object(wsvc, "fetch_minute_bars_multi", AsyncMock(return_value=bars)),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        assert len(quotes) == 1
        assert quotes[0].name == "平安银行"
        assert quotes[0].price == 12.5
        assert quotes[0].change_pct == 1.2
        assert len(quotes[0].trend) == 30
        # 共享 Redis 客户端复用连接，单次查询后不应关闭
        redis.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fallback_uses_stock_basic_name_and_kline(self) -> None:
        latest = SimpleNamespace(
            close=10.5, change_pct=-0.5, amount=5_000_000.0, trade_date=date(2026, 7, 16)
        )
        prev = SimpleNamespace(
            close=10.0, change_pct=None, amount=1.0, trade_date=date(2026, 7, 15)
        )

        session = AsyncMock()
        session.execute.return_value = _scalars_result([_watch("600000")])

        redis = AsyncMock()
        redis.get.return_value = None

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(
                wsvc, "_load_stock_names", AsyncMock(return_value={"600000": "浦发银行"})
            ),
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 2)),
            ),
            patch.object(wsvc, "fetch_minute_bars_multi", AsyncMock(return_value=[])),
            patch.object(
                wsvc, "fetch_daily_bars", AsyncMock(return_value=[latest, prev])
            ),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        assert quotes[0].name == "浦发银行"
        assert quotes[0].price == 10.5
        # 日 K 自带 change_pct 时直接采用，不走前收盘推算
        assert quotes[0].change_pct == -0.5
        assert quotes[0].amount == 5_000_000.0
        assert quotes[0].updated_at == "2026-07-16"
        assert quotes[0].trend == []

    @pytest.mark.asyncio
    async def test_fallback_computes_change_pct_from_prev_close(self) -> None:
        latest = SimpleNamespace(
            close=10.5, change_pct=None, amount=5_000_000.0, trade_date=date(2026, 7, 16)
        )
        prev = SimpleNamespace(
            close=10.0, change_pct=None, amount=1.0, trade_date=date(2026, 7, 15)
        )

        session = AsyncMock()
        session.execute.return_value = _scalars_result([_watch("600000")])

        redis = AsyncMock()
        redis.get.return_value = None

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(wsvc, "_load_stock_names", AsyncMock(return_value={})),
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 2)),
            ),
            patch.object(wsvc, "fetch_minute_bars_multi", AsyncMock(return_value=[])),
            patch.object(
                wsvc, "fetch_daily_bars", AsyncMock(return_value=[latest, prev])
            ),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        assert quotes[0].change_pct == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_fallback_without_daily_bars_keeps_name_and_trend(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([_watch("600967")])
        redis = AsyncMock()
        redis.get.return_value = None
        bars = [SimpleNamespace(stock_code="600967", close=float(i + 1)) for i in range(10)]

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(
                wsvc, "_load_stock_names", AsyncMock(return_value={"600967": "内蒙一机"})
            ),
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 2)),
            ),
            patch.object(
                wsvc, "fetch_minute_bars_multi", AsyncMock(return_value=bars)
            ),
            patch.object(wsvc, "fetch_daily_bars", AsyncMock(return_value=[])),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        assert quotes[0].name == "内蒙一机"
        assert quotes[0].price is None
        assert quotes[0].change_pct is None
        assert quotes[0].updated_at is None
        assert len(quotes[0].trend) == 10

    @pytest.mark.asyncio
    async def test_trend_downsample_preserves_endpoints(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([_watch("600000")])
        redis = AsyncMock()
        redis.get.return_value = None
        bars = [SimpleNamespace(stock_code="600000", close=float(i + 1)) for i in range(121)]

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(wsvc, "_load_stock_names", AsyncMock(return_value={})),
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 2)),
            ),
            patch.object(wsvc, "fetch_minute_bars_multi", AsyncMock(return_value=bars)),
            patch.object(wsvc, "fetch_daily_bars", AsyncMock(return_value=[])),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        trend = quotes[0].trend
        assert len(trend) == 60
        assert trend[0] == 1.0
        assert trend[-1] == 121.0

    @pytest.mark.asyncio
    async def test_empty_watchlist_returns_empty(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _scalars_result([])
        redis = AsyncMock()
        names = AsyncMock()

        with (
            patch.object(wsvc, "get_redis", MagicMock(return_value=redis)),
            patch.object(wsvc, "_load_stock_names", names),
        ):
            quotes = await wsvc.get_watchlist_quotes(session, user_id=1)

        assert quotes == []
        names.assert_not_awaited()


def _group(gid: int, name: str, *, enabled: bool = False, default: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=gid, name=name, is_default=default, ai_review_enabled=enabled
    )


def _watch_in(code: str, group_id: int) -> SimpleNamespace:
    watch = SimpleNamespace(stock_code=code, tags=[], group_id=group_id)
    return watch


@pytest.mark.unit
class TestGetWatchlistGroups:
    @pytest.mark.asyncio
    async def test_groups_with_quotes_and_ai_statuses(self) -> None:
        session = AsyncMock()
        groups = [
            _group(1, "核心持仓", enabled=True),
            _group(2, "默认分组", default=True),
        ]
        items = [
            _watch_in("600967", 1),
            _watch_in("600236", 2),
        ]
        session.execute = AsyncMock(
            side_effect=[_scalars_result(groups), _scalars_result(items)]
        )
        quote_a = WatchlistQuoteItem(code="600967", name="内蒙一机", price=10.0)
        quote_b = WatchlistQuoteItem(code="600236", name="桂冠电力", price=5.0)

        with (
            patch.object(
                wsvc,
                "_build_quote_items",
                AsyncMock(return_value=[quote_b, quote_a]),
            ),
            patch.object(
                wsvc,
                "_load_ai_analysis",
                AsyncMock(return_value={"600967": ("ready", "周线企稳，量能温和")}),
            ),
        ):
            result = await wsvc.get_watchlist_groups(session, user_id=3)

        assert [g.name for g in result] == ["核心持仓", "默认分组"]
        assert result[0].items[0].ai_status == "ready"
        assert result[0].items[0].ai_summary == "周线企稳，量能温和"
        assert result[1].items[0].ai_status == "off"
        assert result[1].items[0].ai_summary is None

    @pytest.mark.asyncio
    async def test_enabled_group_without_result_is_pending(self) -> None:
        session = AsyncMock()
        groups = [_group(1, "核心持仓", enabled=True)]
        items = [_watch_in("600967", 1)]
        session.execute = AsyncMock(
            side_effect=[_scalars_result(groups), _scalars_result(items)]
        )
        quote = WatchlistQuoteItem(code="600967", name="内蒙一机")

        with (
            patch.object(
                wsvc, "_build_quote_items", AsyncMock(return_value=[quote])
            ),
            patch.object(wsvc, "_load_ai_analysis", AsyncMock(return_value={})),
        ):
            result = await wsvc.get_watchlist_groups(session, user_id=3)

        assert result[0].items[0].ai_status == "pending"

    @pytest.mark.asyncio
    async def test_no_groups_returns_empty(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_scalars_result([]))
        build = AsyncMock()

        with patch.object(wsvc, "_build_quote_items", build):
            result = await wsvc.get_watchlist_groups(session, user_id=3)

        assert result == []
        build.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_load_ai_analysis_prefers_latest_and_strips_markdown(self) -> None:
        session = AsyncMock()
        rows = [
            SimpleNamespace(
                input_hash="h-600967-2026-09-03",
                structured_output={
                    "sections": {"intraday_review": "## 盘面解读\n缩量*反弹*，`关注` 39.8 元"}
                },
            ),
            SimpleNamespace(
                input_hash="h-600967-2026-09-03",
                structured_output={"sections": {"intraday_review": "**旧内容**"}},
            ),
        ]

        fake_sections = [SimpleNamespace(key="intraday_review", title="盘面解读")]
        with (
            patch.object(
                wsvc.trade_calendar_service,
                "resolve_latest_trade_date",
                AsyncMock(return_value=date(2026, 9, 3)),
            ),
            patch.object(
                wsvc.ai_analysis_repository,
                "load_success_by_hashes",
                AsyncMock(return_value=rows),
            ) as repo_mock,
            patch(
                "app.services.review.stock_daily_analysis_service.load_prompt_config",
                MagicMock(return_value=SimpleNamespace(sections=fake_sections)),
            ),
            patch(
                "app.services.review.stock_daily_analysis_service.input_hash",
                MagicMock(
                    side_effect=lambda code, td, secs: f"h-{code}-{td.isoformat()}"
                ),
            ),
        ):
            result = await wsvc._load_ai_analysis(session, ["600967"])

        # 两个 hash 都请求了（同一 code 仅一个 hash 命中，此处模拟两行不同 hash）
        assert repo_mock.await_args.kwargs["input_hashes"] == ["h-600967-2026-09-03"]
        # created_at 倒序：同 hash 首行（最新）保留，旧行跳过
        assert result["600967"][0] == "ready"
        assert result["600967"][1] == "盘面解读 缩量反弹，关注 39.8 元"
