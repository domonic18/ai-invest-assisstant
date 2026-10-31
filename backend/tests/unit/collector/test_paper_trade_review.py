"""模拟盘复盘采集器契约测试（多 Agent 循环隔离/跳过口径/加发/cadence 门控/未就绪传播）。"""

from contextlib import ExitStack
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading.agent_review_service import (
    PaperTradeReviewLockedError,
    ReviewWindowNotReadyError,
)
from app.services.trading.errors import AgentAccountNotDesignatedError
from collector.core.base import CollectStatus
from collector.spiders.paper_trade_review import PaperTradeReviewCollector

_TRADE_DATE = date(2026, 7, 17)  # Friday


def _agent(key: str = "short-line", cadence: str = "daily") -> SimpleNamespace:
    return SimpleNamespace(agent_key=key, review_cadence=cadence)


def _result(
    cached: bool = False,
    no_target: bool = False,
    period: str = "day",
    trade_date: str = "2026-07-17",
) -> SimpleNamespace:
    """generate_review 返回值替身（spider 消费 cached + content 的周期/基准日/无对象标记）。"""
    return SimpleNamespace(
        cached=cached,
        content=SimpleNamespace(
            period=period,
            trade_date=trade_date,
            no_target_reason="复盘窗口内无委托成交" if no_target else None,
        ),
    )


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
    """统一打桩（定时通道）：日历/会话工厂/注册表/生成服务/周期末判定。"""
    agent_rows = agents if agents is not None else [_agent()]
    cadence_by_key = {a.agent_key: a.review_cadence for a in agent_rows}
    return (
        patch(
            "collector.spiders.paper_trade_review_scheduled.is_trading_day",
            AsyncMock(return_value=trading_day),
        ),
        patch(
            "collector.spiders.paper_trade_review_scheduled.resolve_latest_trade_date",
            AsyncMock(return_value=_TRADE_DATE),
        ),
        patch("collector.spiders.paper_trade_review_scheduled.AsyncSessionLocal"),
        patch(
            "collector.spiders.paper_trade_review_scheduled.agent_registry.get_active_agents",
            AsyncMock(return_value=agent_rows),
        ),
        patch(
            "collector.spiders.paper_trade_review_scheduled.agent_registry.get_agent",
            AsyncMock(
                side_effect=lambda _s, key: _agent(
                    key, cadence_by_key.get(key, "daily")
                )
            ),
        ),
        patch(
            "app.services.trading.agent_review_service.generate_review",
            generate or AsyncMock(return_value=_result()),
        ),
        patch(
            "collector.spiders.paper_trade_review_scheduled.is_last_trading_day_of_week",
            AsyncMock(return_value=week_end),
        ),
        patch(
            "collector.spiders.paper_trade_review_scheduled.is_last_trading_day_of_month",
            AsyncMock(return_value=month_end),
        ),
    )


def _activate(patches):
    """在单个 with 块内启用全部 patch。"""
    stack = ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


def _patch_on_demand(
    *,
    trading_day: bool = True,
    generate: AsyncMock | None = None,
    agent_error: Exception | None = None,
):
    """按需分支打桩：日历/会话工厂/注册表/生成服务。"""
    get_agent = AsyncMock(side_effect=lambda _s, key: _agent(key))
    if agent_error is not None:
        get_agent = AsyncMock(side_effect=agent_error)
    return [
        patch(
            "collector.spiders.paper_trade_review_on_demand.is_trading_day",
            AsyncMock(return_value=trading_day),
        ),
        patch(
            "collector.spiders.paper_trade_review_on_demand.resolve_latest_trade_date",
            AsyncMock(return_value=_TRADE_DATE),
        ),
        patch("collector.spiders.paper_trade_review_on_demand.AsyncSessionLocal"),
        patch(
            "collector.spiders.paper_trade_review_on_demand.agent_registry.get_agent",
            get_agent,
        ),
        patch(
            "app.services.trading.agent_review_service.generate_review",
            generate or AsyncMock(return_value=_result()),
        ),
    ]


@pytest.mark.unit
class TestPaperTradeReviewOnDemand:
    """B4 按需通道：params 带 agent_key 时只生成该 Agent 指定周期。"""

    @pytest.mark.asyncio
    async def test_generates_requested_period(self) -> None:
        generate = AsyncMock(return_value=_result(period="quarter"))
        patches = _patch_on_demand(generate=generate)
        with _activate(patches):
            result = await _collector().run(
                agent_key="short-line", period="quarter", trade_date="2026-07-17"
            )

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 1
        assert result.items_stored == 1
        request = generate.await_args.args[2]
        assert request.period == "quarter"
        assert request.trade_date == _TRADE_DATE
        assert request.scope == "current"
        assert request.start_date is None
        assert request.end_date is None
        assert generate.await_args.kwargs["regenerate"] is False
        assert generate.await_args.kwargs["trigger"] == "manual"
        assert result.metadata == {
            "agent_key": "short-line",
            "period": "quarter",
            "trade_date": "2026-07-17",
            "start_date": None,
            "end_date": None,
            "cached": False,
            "no_target": False,
        }

    @pytest.mark.asyncio
    async def test_custom_range_skips_single_day_precheck(self) -> None:
        """自定义区间：基准日由服务层收边，不做单日交易日预检。"""
        generate = AsyncMock(return_value=_result(period="month", trade_date="2026-07-17"))
        patches = _patch_on_demand(trading_day=False, generate=generate)
        with _activate(patches):
            result = await _collector().run(
                agent_key="short-line",
                start_date="2026-06-01",
                end_date="2026-07-17",
            )

        assert result.status == CollectStatus.SUCCESS
        request = generate.await_args.args[2]
        assert request.period is None
        assert request.start_date == date(2026, 6, 1)
        assert request.end_date == _TRADE_DATE
        assert result.metadata["start_date"] == "2026-06-01"
        assert result.metadata["end_date"] == "2026-07-17"

    @pytest.mark.asyncio
    async def test_previous_scope_passes_through(self) -> None:
        generate = AsyncMock(return_value=_result(period="week"))
        patches = _patch_on_demand(generate=generate)
        with _activate(patches):
            result = await _collector().run(
                agent_key="short-line", period="week", scope="previous"
            )

        assert result.status == CollectStatus.SUCCESS
        request = generate.await_args.args[2]
        assert request.scope == "previous"
        # 上期窗口基准日由服务层解析，spider 仍取最近交易日做非交易日预检
        assert request.trade_date == _TRADE_DATE

    @pytest.mark.asyncio
    async def test_rejects_unpaired_range(self) -> None:
        patches = _patch_on_demand()
        with _activate(patches):
            result = await _collector().run(
                agent_key="short-line", start_date="2026-06-01"
            )

        assert result.status == CollectStatus.FAILED
        assert "须同时提供开始日与结束日" in (result.message or "")

    @pytest.mark.asyncio
    async def test_rejects_ordering_violation(self) -> None:
        patches = _patch_on_demand()
        with _activate(patches):
            result = await _collector().run(
                agent_key="short-line",
                start_date="2026-07-17",
                end_date="2026-06-01",
            )

        assert result.status == CollectStatus.FAILED
        assert "早于开始日" in (result.message or "")

    @pytest.mark.asyncio
    async def test_regenerate_flag_passes_through(self) -> None:
        generate = AsyncMock(return_value=_result())
        patches = _patch_on_demand(generate=generate)
        with _activate(patches):
            await _collector().run(
                agent_key="short-line", period="year", regenerate=True
            )

        assert generate.await_args.kwargs["regenerate"] is True
        # 缺省基准日回退最新交易日
        assert generate.await_args.args[2].trade_date == _TRADE_DATE

    @pytest.mark.asyncio
    async def test_cached_and_no_target_messages(self) -> None:
        patches = _patch_on_demand(generate=AsyncMock(return_value=_result(cached=True)))
        with _activate(patches):
            cached = await _collector().run(agent_key="short-line", period="month")
        assert cached.items_stored == 0
        assert "未重新生成" in (cached.message or "")

        patches = _patch_on_demand(
            generate=AsyncMock(return_value=_result(no_target=True))
        )
        with _activate(patches):
            idle = await _collector().run(agent_key="short-line", period="half_year")
        assert idle.items_stored == 1
        assert "无复盘对象" in (idle.message or "")

    @pytest.mark.asyncio
    async def test_rejects_unknown_period(self) -> None:
        patches = _patch_on_demand()
        with _activate(patches):
            result = await _collector().run(agent_key="short-line", period="decade")

        assert result.status == CollectStatus.FAILED
        assert result.errors == ["未知复盘周期：decade"]

    @pytest.mark.asyncio
    async def test_rejects_invalid_trade_date(self) -> None:
        patches = _patch_on_demand()
        with _activate(patches):
            result = await _collector().run(
                agent_key="short-line", period="day", trade_date="2026/07/17"
            )

        assert result.status == CollectStatus.FAILED
        assert "无效的 trade_date" in (result.message or "")

    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        patches = _patch_on_demand(trading_day=False)
        with _activate(patches):
            result = await _collector().run(
                agent_key="short-line", period="day", trade_date="2026-07-18"
            )

        assert result.status == CollectStatus.FAILED
        assert "不是交易日" in (result.message or "")

    @pytest.mark.asyncio
    async def test_unknown_agent_fails(self) -> None:
        from app.core.exceptions import NotFoundError

        patches = _patch_on_demand(agent_error=NotFoundError("交易 Agent ghost 不存在"))
        with _activate(patches):
            result = await _collector().run(agent_key="ghost", period="week")

        assert result.status == CollectStatus.FAILED
        assert result.errors == ["交易 Agent ghost 不存在"]

    @pytest.mark.asyncio
    async def test_locked_is_skipped(self) -> None:
        patches = _patch_on_demand(
            generate=AsyncMock(side_effect=PaperTradeReviewLockedError("正在生成"))
        )
        with _activate(patches):
            result = await _collector().run(agent_key="short-line", period="day")

        assert result.status == CollectStatus.SKIPPED
        assert "请稍后刷新查看" in (result.message or "")

    @pytest.mark.asyncio
    async def test_account_not_designated_fails(self) -> None:
        patches = _patch_on_demand(
            generate=AsyncMock(side_effect=AgentAccountNotDesignatedError("short-line"))
        )
        with _activate(patches):
            result = await _collector().run(agent_key="short-line", period="day")

        assert result.status == CollectStatus.FAILED
        assert result.errors and "尚未关联专属模拟盘账户" in result.errors[0]

    @pytest.mark.asyncio
    async def test_not_ready_propagates_for_retry(self) -> None:
        patches = _patch_on_demand(
            generate=AsyncMock(side_effect=ReviewInputDataNotReadyError("未就绪"))
        )
        with _activate(patches):
            with pytest.raises(ReviewInputDataNotReadyError):
                await _collector().run(agent_key="short-line", period="day")

    @pytest.mark.asyncio
    async def test_window_not_ready_fails_without_retry(self) -> None:
        """手动触发且窗口末日未同步：记 FAILED 带引导文案，不向上抛重试。"""
        patches = _patch_on_demand(
            generate=AsyncMock(
                side_effect=ReviewWindowNotReadyError(
                    "2026-07-17 盘后同步（16:00）尚未落库，复盘输入未就绪；"
                    "请改用「上期」或历史区间，或 16:00 后再试"
                )
            )
        )
        with _activate(patches):
            result = await _collector().run(agent_key="short-line", period="month")

        assert result.status == CollectStatus.FAILED
        assert result.errors and "16:00" in result.errors[0]
        assert "上期" in (result.message or "")


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
        generate = AsyncMock(return_value=_result())
        with _activate(_patch_env(generate=generate)):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 1
        assert result.metadata["agents"]["short-line"]["day"] == {
            "cached": False,
            "no_target": False,
        }
        generate.assert_awaited_once()
        assert generate.await_args.args[1].agent_key == "short-line"
        assert generate.await_args.args[2].period == "day"

    @pytest.mark.asyncio
    async def test_cache_hit_reports_message_without_storing(self) -> None:
        patches = _patch_env(generate=AsyncMock(return_value=_result(cached=True)))
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 0
        assert "缓存命中" in (result.message or "")

    @pytest.mark.asyncio
    async def test_week_and_month_boost_on_period_end(self) -> None:
        """周五（且为月末最后交易日）：同任务内加发 week + month。"""
        generate = AsyncMock(return_value=_result())
        patches = _patch_env(generate=generate, week_end=True, month_end=True)
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        periods = [c.args[2].period for c in generate.await_args_list]
        assert periods == ["day", "week", "month"]
        agent_meta = result.metadata["agents"]["short-line"]
        assert agent_meta["week"] == {"cached": False, "no_target": False}
        assert agent_meta["month"] == {"cached": False, "no_target": False}

    @pytest.mark.asyncio
    async def test_no_target_agent_records_marker_and_message(self) -> None:
        """空仓无复盘对象：标记行照常入库（SUCCESS），消息行与未执行可区分。"""
        patches = _patch_env(generate=AsyncMock(return_value=_result(no_target=True)))
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 1
        assert result.metadata["agents"]["short-line"]["day"] == {
            "cached": False,
            "no_target": True,
        }
        assert "已执行复盘但无对象" in (result.message or "")

    @pytest.mark.asyncio
    async def test_boost_unexpected_error_recorded_not_raised(self) -> None:
        """加发周期非锁异常隔离：首周期结果保留，其余周期继续执行。"""

        async def _generate(_session, _agent, request, **kwargs):
            if request.period == "week":
                raise RuntimeError("boom")
            return _result()

        patches = _patch_env(
            generate=AsyncMock(side_effect=_generate), week_end=True, month_end=True
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        agent_meta = result.metadata["agents"]["short-line"]
        assert agent_meta["day"] == {"cached": False, "no_target": False}
        assert agent_meta["week"] == {"error": "boom"}
        assert agent_meta["month"] == {"cached": False, "no_target": False}

    @pytest.mark.asyncio
    async def test_boost_soft_timeout_propagates(self) -> None:
        """软超时必须上抛（由 run_collector_task 统一收尾），不按加发周期隔离。"""
        from celery.exceptions import SoftTimeLimitExceeded

        async def _generate(_session, _agent, request, **kwargs):
            if request.period == "week":
                raise SoftTimeLimitExceeded()
            return _result()

        patches = _patch_env(generate=AsyncMock(side_effect=_generate), week_end=True)
        with _activate(patches):
            with pytest.raises(SoftTimeLimitExceeded):
                await _collector().run()

    @pytest.mark.asyncio
    async def test_boost_locked_is_recorded_not_raised(self) -> None:
        async def _generate(_session, _agent, request, **kwargs):
            if request.period == "month":
                raise PaperTradeReviewLockedError("正在生成")
            return _result()

        patches = _patch_env(generate=AsyncMock(side_effect=_generate), month_end=True)
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        assert result.metadata["agents"]["short-line"]["month"] == {"skipped": "正在生成"}

    @pytest.mark.asyncio
    async def test_not_ready_error_propagates_for_retry(self) -> None:
        """全部 Agent 未就绪向上传播交由 Celery 退避重试，且携带 agent 级原因。"""
        patches = _patch_env(
            generate=AsyncMock(
                side_effect=ReviewInputDataNotReadyError(
                    "2026-07-17 盘后同步（16:00）尚未落库，复盘输入未就绪"
                )
            )
        )
        with _activate(patches):
            with pytest.raises(
                ReviewInputDataNotReadyError, match="：2026-07-17 盘后同步"
            ):
                await _collector().run()

    @pytest.mark.asyncio
    async def test_not_ready_gate_ignores_agents_not_due(self) -> None:
        """混合 cadence：weekly 非生成日不参与门槛，daily 未就绪仍须抛错重试。

        旧实现以 ``not_ready == len(agents)`` 判定，weekly 跳过使门槛被稀释，
        daily 未就绪被降级为 SKIPPED，当日日度复盘永久丢失。
        """

        async def _generate(_session, agent, request, **kwargs):
            if agent.agent_key == "long-line":
                return _result()
            raise ReviewInputDataNotReadyError("未就绪")

        patches = _patch_env(
            agents=[_agent("short-line"), _agent("long-line", "weekly")],
            generate=AsyncMock(side_effect=_generate),
            week_end=False,
        )
        with _activate(patches):
            with pytest.raises(ReviewInputDataNotReadyError, match="1 个应生成复盘"):
                await _collector().run()

    @pytest.mark.asyncio
    async def test_not_ready_with_due_agent_ok_is_partial(self) -> None:
        """应生成 Agent 中部分未就绪 → PARTIAL，不整任务重试。"""

        async def _generate(_session, agent, request, **kwargs):
            if agent.agent_key == "m60":
                raise ReviewInputDataNotReadyError("未就绪")
            return _result()

        patches = _patch_env(
            agents=[_agent("short-line"), _agent("m60")],
            generate=AsyncMock(side_effect=_generate),
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_not_ready_with_one_ready_agent_is_partial(self) -> None:
        """单 Agent 未就绪不传播：另一个成功 → PARTIAL，明细进 message。"""

        async def _generate(_session, agent, request, **kwargs):
            if agent.agent_key == "m60":
                raise ReviewInputDataNotReadyError("未就绪")
            return _result()

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
                side_effect=lambda _s, a, _r, **kw: (
                    _result()
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
        assert result.metadata["agents"]["short-line"]["day"] == {
            "cached": False,
            "no_target": False,
        }

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
        generate = AsyncMock(return_value=_result())
        patches = _patch_env(
            agents=[_agent("long-line", "weekly")], generate=generate, week_end=True
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        periods = [c.args[2].period for c in generate.await_args_list]
        assert periods == ["week"]
        assert result.metadata["agents"]["long-line"] == {
            "week": {"cached": False, "no_target": False}
        }
        assert result.items_stored == 1

    @pytest.mark.asyncio
    async def test_monthly_agent_generates_only_month_on_month_end(self) -> None:
        """D28：月频 Agent 月末只生成 month；非月末跳过。"""
        generate = AsyncMock(return_value=_result())
        patches = _patch_env(
            agents=[_agent("long-line", "monthly")], generate=generate, month_end=True
        )
        with _activate(patches):
            result = await _collector().run()

        assert result.status == CollectStatus.SUCCESS
        periods = [c.args[2].period for c in generate.await_args_list]
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
        assert result.metadata["agents"]["short-line"] == {
            "day": {"cached": False, "no_target": False}
        }
