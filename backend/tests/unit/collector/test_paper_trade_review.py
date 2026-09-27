"""模拟盘复盘采集器契约测试（多 Agent 循环隔离/跳过口径/加发/cadence 门控/未就绪传播）。"""

from contextlib import ExitStack
from datetime import date
from types import SimpleNamespace
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


def _agent(key: str = "short-line", cadence: str = "daily") -> SimpleNamespace:
    return SimpleNamespace(agent_key=key, review_cadence=cadence)


def _collector() -> PaperTradeReviewCollector:
    return PaperTradeReviewCollector(
        {"source": "internal", "data_type": "paper-trade-review"}
    )


def _patch_env(
    *,
    trading_day: bool = True,
    agents: list | None = None,
    generate: AsyncMock | None = None,
    week_end: bool = False,
    month_end: bool = False,
):
    """统一打桩：日历/会话工厂/注册表/生成服务/周期末判定。"""
    agent_rows = agents if agents is not None else [_agent()]
    cadence_by_key = {a.agent_key: a.review_cadence for a in agent_rows}
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
            "collector.spiders.paper_trade_review.agent_registry.get_active_agents",
            AsyncMock(return_value=agent_rows),
        ),
        patch(
            "collector.spiders.paper_trade_review.agent_registry.get_agent",
            AsyncMock(
                side_effect=lambda _s, key: _agent(
                    key, cadence_by_key.get(key, "daily")
                )
            ),
        ),
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


def _activate(patches):
    """在单个 with 块内启用全部 patch。"""
    stack = ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


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
    async def test_skips_when_no_active_agents(self) -> None:
        with _activate(_patch_env(agents=[])):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "无 active" in (result.message or "")

    @pytest.mark.asyncio
    async def test_success_generates_day_review(self) -> None:
        generate = AsyncMock(return_value=MagicMock(cached=False))
        with _activate(_patch_env(generate=generate)):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 1
        assert result.metadata["agents"]["short-line"]["day"] == {"cached": False}
        generate.assert_awaited_once()
        assert generate.await_args.args[1].agent_key == "short-line"
        assert generate.await_args.kwargs["period"] == "day"

    @pytest.mark.asyncio
    async def test_cache_hit_reports_message_without_storing(self) -> None:
        patches = _patch_env(generate=AsyncMock(return_value=MagicMock(cached=True)))
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 0
        assert "缓存命中" in (result.message or "")

    @pytest.mark.asyncio
    async def test_week_and_month_boost_on_period_end(self) -> None:
        """周五（且为月末最后交易日）：同任务内加发 week + month。"""
        generate = AsyncMock(return_value=MagicMock(cached=False))
        patches = _patch_env(generate=generate, week_end=True, month_end=True)
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        periods = [c.kwargs["period"] for c in generate.await_args_list]
        assert periods == ["day", "week", "month"]
        agent_meta = result.metadata["agents"]["short-line"]
        assert agent_meta["week"] == {"cached": False}
        assert agent_meta["month"] == {"cached": False}

    @pytest.mark.asyncio
    async def test_boost_failure_does_not_fail_day_result(self) -> None:
        """加发（week）失败只记 metadata，不拖垮已成功的日度结果。"""

        async def _generate(_session, _agent, *, period, **kwargs):
            if period == "week":
                raise NoReviewTargetError("窗口内无交易")
            return MagicMock(cached=False)

        patches = _patch_env(generate=AsyncMock(side_effect=_generate), week_end=True)
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        agent_meta = result.metadata["agents"]["short-line"]
        assert agent_meta["week"] == {"skipped": "窗口内无交易"}
        assert agent_meta["day"] == {"cached": False}

    @pytest.mark.asyncio
    async def test_boost_locked_is_recorded_not_raised(self) -> None:
        async def _generate(_session, _agent, *, period, **kwargs):
            if period == "month":
                raise PaperTradeReviewLockedError("正在生成")
            return MagicMock(cached=False)

        patches = _patch_env(generate=AsyncMock(side_effect=_generate), month_end=True)
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["agents"]["short-line"]["month"] == {"skipped": "正在生成"}

    @pytest.mark.asyncio
    async def test_not_ready_error_propagates_for_retry(self) -> None:
        """全部 Agent 输入未就绪必须向上传播交由 Celery 退避重试。"""
        patches = _patch_env(
            generate=AsyncMock(side_effect=ReviewInputDataNotReadyError("未就绪"))
        )
        with _activate(patches):
            with pytest.raises(ReviewInputDataNotReadyError):
                await _collector().run()

    @pytest.mark.asyncio
    async def test_not_ready_with_one_ready_agent_is_partial(self) -> None:
        """单 Agent 未就绪不传播：另一个成功 → PARTIAL，明细进 message。"""

        async def _generate(_session, agent, **kwargs):
            if agent.agent_key == "m60":
                raise ReviewInputDataNotReadyError("未就绪")
            return MagicMock(cached=False)

        patches = _patch_env(
            agents=[_agent("short-line"), _agent("m60")],
            generate=AsyncMock(side_effect=_generate),
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.PARTIAL
        assert "m60" in (result.message or "")

    @pytest.mark.asyncio
    async def test_skips_when_agent_account_not_designated(self) -> None:
        patches = _patch_env(
            generate=AsyncMock(side_effect=AgentAccountNotDesignatedError("short-line"))
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "尚未关联专属模拟盘账户" in (result.message or "")

    @pytest.mark.asyncio
    async def test_skips_when_no_review_target(self) -> None:
        patches = _patch_env(
            generate=AsyncMock(side_effect=NoReviewTargetError("无交易且无持仓"))
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "无交易" in (result.message or "")

    @pytest.mark.asyncio
    async def test_unexpected_error_fails_with_errors_list(self) -> None:
        patches = _patch_env(generate=AsyncMock(side_effect=RuntimeError("boom")))
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.FAILED
        assert result.errors == ["short-line: boom"]

    @pytest.mark.asyncio
    async def test_partial_when_one_agent_fails(self) -> None:
        """单 Agent 真错误不拖垮其他 Agent：成功者照常入库，聚合 PARTIAL。"""
        patches = _patch_env(
            agents=[_agent("short-line"), _agent("m60")],
            generate=AsyncMock(
                side_effect=lambda _s, a, **kw: (
                    MagicMock(cached=False)
                    if a.agent_key == "short-line"
                    else (_ for _ in ()).throw(RuntimeError("boom"))
                )
            ),
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.PARTIAL
        assert result.items_collected == 1
        assert result.errors == ["m60: boom"]
        assert result.metadata["agents"]["short-line"]["day"] == {"cached": False}

    @pytest.mark.asyncio
    async def test_weekly_agent_skips_midweek(self) -> None:
        """D28：周频 Agent 非周期日跳过（记明细不生成）。"""
        patches = _patch_env(agents=[_agent("long-line", "weekly")], week_end=False)
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SKIPPED
        assert "weekly 频复盘未到生成日" in (result.message or "")

    @pytest.mark.asyncio
    async def test_weekly_agent_generates_only_week_on_period_end(self) -> None:
        """D28：周频 Agent 周期末只生成 week（无 day）。"""
        generate = AsyncMock(return_value=MagicMock(cached=False))
        patches = _patch_env(
            agents=[_agent("long-line", "weekly")], generate=generate, week_end=True
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        periods = [c.kwargs["period"] for c in generate.await_args_list]
        assert periods == ["week"]
        assert result.metadata["agents"]["long-line"] == {"week": {"cached": False}}
        assert result.items_stored == 1

    @pytest.mark.asyncio
    async def test_monthly_agent_generates_only_month_on_month_end(self) -> None:
        """D28：月频 Agent 月末只生成 month；非月末跳过。"""
        generate = AsyncMock(return_value=MagicMock(cached=False))
        patches = _patch_env(
            agents=[_agent("long-line", "monthly")], generate=generate, month_end=True
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        periods = [c.kwargs["period"] for c in generate.await_args_list]
        assert periods == ["month"]

        patches = _patch_env(agents=[_agent("long-line", "monthly")], month_end=False)
        with _activate(patches):
            result = await _collector().run()
        assert result.status == CollectStatus.SKIPPED
        assert "monthly 频复盘未到生成日" in (result.message or "")

    @pytest.mark.asyncio
    async def test_mixed_cadences_partial_detail(self) -> None:
        """D28：daily 正常生成 + weekly 非周期跳过 → SUCCESS，明细含两行。"""
        patches = _patch_env(
            agents=[_agent("short-line"), _agent("long-line", "weekly")],
            week_end=False,
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert "long-line: weekly 频复盘未到生成日" in (result.message or "")
        assert result.metadata["agents"]["short-line"] == {"day": {"cached": False}}
