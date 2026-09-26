"""模拟盘复盘采集器契约测试（跳过口径/加发/未就绪传播）。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.trading.agent_review_service import (
    NoReviewTargetError,
    PaperTradeReviewLockedError,
)
from app.services.trading.errors import AgentAccountNotDesignatedError
from collector.core.base import CollectStatus
from collector.spiders.paper_trade_review import (
    PaperTradeReviewCollector,
    ReviewInputDataNotReadyError,
)

_TRADE_DATE = date(2026, 7, 17)  # Friday


def _collector() -> PaperTradeReviewCollector:
    return PaperTradeReviewCollector(
        {"source": "internal", "data_type": "paper-trade-review"}
    )


def _session_factory() -> MagicMock:
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


def _patch_env(
    *,
    trading_day: bool = True,
    generate: AsyncMock | None = None,
    week_end: bool = False,
    month_end: bool = False,
):
    """统一打桩：日历/会话工厂/生成服务/周期末判定。"""
    return (
        patch(
            "collector.spiders.paper_trade_review.is_trading_day",
            return_value=trading_day,
        ),
        patch(
            "collector.spiders.paper_trade_review.latest_trading_day",
            return_value=_TRADE_DATE,
        ),
        patch("collector.spiders.paper_trade_review.AsyncSessionLocal"),
        patch(
            "collector.spiders.paper_trade_review.agent_review_service.generate_review",
            generate or AsyncMock(return_value=MagicMock(cached=False)),
        ),
        patch(
            "collector.spiders.paper_trade_review.agent_review_service.is_last_trading_day_of_week",
            AsyncMock(return_value=week_end),
        ),
        patch(
            "collector.spiders.paper_trade_review.agent_review_service.is_last_trading_day_of_month",
            AsyncMock(return_value=month_end),
        ),
    )


@pytest.mark.unit
class TestPaperTradeReviewCollector:
    @pytest.mark.asyncio
    async def test_skips_non_trading_day(self) -> None:
        patches = _patch_env(trading_day=False)
        with patches[0], patches[1]:
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "不是交易日" in (result.message or "")

    @pytest.mark.asyncio
    async def test_success_generates_day_review(self) -> None:
        generate = AsyncMock(return_value=MagicMock(cached=False))
        patches = _patch_env(generate=generate)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 1
        assert result.metadata["day"] == {"cached": False}
        generate.assert_awaited_once()
        assert generate.await_args.kwargs["period"] == "day"

    @pytest.mark.asyncio
    async def test_cache_hit_reports_message_without_storing(self) -> None:
        patches = _patch_env(generate=AsyncMock(return_value=MagicMock(cached=True)))
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 0
        assert "缓存命中" in (result.message or "")

    @pytest.mark.asyncio
    async def test_week_and_month_boost_on_period_end(self) -> None:
        """周五（且为月末最后交易日）：同任务内加发 week + month。"""
        generate = AsyncMock(return_value=MagicMock(cached=False))
        patches = _patch_env(
            generate=generate, week_end=True, month_end=True
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        periods = [c.kwargs["period"] for c in generate.await_args_list]
        assert periods == ["day", "week", "month"]
        assert result.metadata["week"] == {"cached": False}
        assert result.metadata["month"] == {"cached": False}

    @pytest.mark.asyncio
    async def test_boost_failure_does_not_fail_day_result(self) -> None:
        """加发（week）失败只记 metadata，不拖垮已成功的日度结果。"""

        async def _generate(session, *, period, **kwargs):
            if period == "week":
                raise NoReviewTargetError("窗口内无交易")
            return MagicMock(cached=False)

        patches = _patch_env(generate=AsyncMock(side_effect=_generate), week_end=True)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["week"] == {"skipped": "窗口内无交易"}
        assert result.metadata["day"] == {"cached": False}

    @pytest.mark.asyncio
    async def test_boost_locked_is_recorded_not_raised(self) -> None:
        async def _generate(session, *, period, **kwargs):
            if period == "month":
                raise PaperTradeReviewLockedError("正在生成")
            return MagicMock(cached=False)

        patches = _patch_env(
            generate=AsyncMock(side_effect=_generate), month_end=True
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["month"] == {"skipped": "正在生成"}

    @pytest.mark.asyncio
    async def test_not_ready_error_propagates_for_retry(self) -> None:
        """输入未就绪必须向上传播交由 Celery 退避重试，而非转为 FAILED。"""
        patches = _patch_env(
            generate=AsyncMock(side_effect=ReviewInputDataNotReadyError("未就绪"))
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            with pytest.raises(ReviewInputDataNotReadyError):
                await _collector().run()

    @pytest.mark.asyncio
    async def test_skips_when_agent_account_not_designated(self) -> None:
        patches = _patch_env(
            generate=AsyncMock(
                side_effect=AgentAccountNotDesignatedError("未指定 agent 专属账户")
            )
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "未指定" in (result.message or "")

    @pytest.mark.asyncio
    async def test_skips_when_no_review_target(self) -> None:
        patches = _patch_env(
            generate=AsyncMock(side_effect=NoReviewTargetError("无交易且无持仓"))
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "无交易" in (result.message or "")

    @pytest.mark.asyncio
    async def test_unexpected_error_fails_with_errors_list(self) -> None:
        patches = _patch_env(generate=AsyncMock(side_effect=RuntimeError("boom")))
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert result.errors == ["boom"]
