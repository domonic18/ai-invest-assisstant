"""agent 持久化（persist_*）工具单测（mock service，不触网不连库）。"""


from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools import (
    get_market_overview,
)
from app.agent.tools import market_tools as mt
from app.schemas.market import (
    MarketStatsResponse,
)


def _review_persist_mocks() -> tuple[MagicMock, AsyncMock]:
    cfg = MagicMock()
    cfg.provider = "anthropic"
    cfg.model_name = "kimi"
    response = SimpleNamespace(trade_date=date(2026, 9, 4), sections=[])
    return cfg, AsyncMock(return_value=response)


@pytest.mark.unit
class TestReviewLatencyAnchor:
    def setup_method(self) -> None:
        mt._review_gen_start = None

    @pytest.mark.asyncio
    async def test_latency_measured_from_first_data_tool_to_persist(self) -> None:
        cfg, persist_mock = _review_persist_mocks()
        stats = MarketStatsResponse(trade_date=date(2026, 8, 21), up_count=3000)
        fake_time = MagicMock()
        fake_time.monotonic = MagicMock(side_effect=[100.0, 165.5])
        with (
            patch.object(mt, "time", fake_time),
            patch.object(
                mt.market_stats_svc,
                "get_market_stats",
                AsyncMock(return_value=stats),
            ),
            patch.object(
                mt.index_quotation_service, "get_index_quotes", AsyncMock(return_value=[])
            ),
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.market_review_generator.persist_market_review_result",
                persist_mock,
            ),
        ):
            await get_market_overview.ainvoke({})
            result = await mt.persist_market_review.ainvoke(
                {"trade_date": "2026-09-04", "sections": {"overview": "x"}}
            )

        assert result["trade_date"] == "2026-09-04"
        assert persist_mock.await_args.kwargs["latency_ms"] == 65500

    @pytest.mark.asyncio
    async def test_persist_without_data_tool_reports_zero(self) -> None:
        cfg, persist_mock = _review_persist_mocks()
        with (
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.market_review_generator.persist_market_review_result",
                persist_mock,
            ),
        ):
            await mt.persist_market_review.ainvoke(
                {"trade_date": "2026-09-04", "sections": {"overview": "x"}}
            )

        assert persist_mock.await_args.kwargs["latency_ms"] == 0

    @pytest.mark.asyncio
    async def test_stale_anchor_reports_zero_without_fresh_data_call(self) -> None:
        mt._review_gen_start = -2000.0
        cfg, persist_mock = _review_persist_mocks()
        fake_time = MagicMock()
        fake_time.monotonic = MagicMock(side_effect=[200.0])
        with (
            patch.object(mt, "time", fake_time),
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.market_review_generator.persist_market_review_result",
                persist_mock,
            ),
        ):
            await mt.persist_market_review.ainvoke(
                {"trade_date": "2026-09-04", "sections": {"overview": "x"}}
            )

        assert persist_mock.await_args.kwargs["latency_ms"] == 0


@pytest.mark.unit
class TestPersistLimitUpAttributionTool:
    @pytest.mark.asyncio
    async def test_persists_groups_and_emits_event(self) -> None:
        cfg = MagicMock()
        cfg.provider = "anthropic"
        cfg.model_name = "kimi"
        saved = MagicMock()
        saved.groups = [
            MagicMock(stock_codes=["600519", "000001"]),
            MagicMock(stock_codes=["300750"]),
        ]
        persist_mock = AsyncMock(return_value=saved)
        with (
            patch.object(mt.trade_calendar_service, "is_trading_day", AsyncMock(return_value=True)),
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.limit_up_ai_service.persist_attribution_result",
                persist_mock,
            ),
        ):
            result = await mt.persist_limit_up_attribution.ainvoke(
                {
                    "trade_date": "2026-09-04",
                    "groups": [
                        {
                            "theme": "白酒",
                            "reason": "消费复苏催化",
                            "stock_codes": ["600519"],
                        }
                    ],
                    "stock_themes": {"600519": ["白酒", "消费"]},
                }
            )

        content = persist_mock.await_args.args[2]
        assert content.groups[0].theme == "白酒"
        assert content.stock_themes == {"600519": ["白酒", "消费"]}
        assert persist_mock.await_args.kwargs["model"] == "anthropic/kimi"
        assert result["groups"] == 2
        assert result["stocks"] == 3
        assert result["__event__"] == {
            "type": "limit_up_attribution.complete",
            "trade_date": "2026-09-04",
        }

    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        with patch.object(
            mt.trade_calendar_service, "is_trading_day", AsyncMock(return_value=False)
        ):
            result = await mt.persist_limit_up_attribution.ainvoke(
                {
                    "trade_date": "2026-09-05",
                    "groups": [{"theme": "白酒", "reason": "r", "stock_codes": ["600519"]}],
                }
            )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_reports_not_ready_error(self) -> None:
        from app.services.review.market_review_service import ReviewInputDataNotReadyError

        cfg = MagicMock()
        cfg.provider = "anthropic"
        cfg.model_name = "kimi"
        with (
            patch.object(mt.trade_calendar_service, "is_trading_day", AsyncMock(return_value=True)),
            patch(
                "app.services.admin.llm_config_service.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.services.review.limit_up_ai_service.persist_attribution_result",
                AsyncMock(side_effect=ReviewInputDataNotReadyError("涨停池数据尚未就绪")),
            ),
        ):
            result = await mt.persist_limit_up_attribution.ainvoke(
                {
                    "trade_date": "2026-09-04",
                    "groups": [{"theme": "白酒", "reason": "r", "stock_codes": ["600519"]}],
                }
            )

        assert "error" in result
