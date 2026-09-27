"""模拟盘分层复盘服务契约测试（生成/缓存/预检/周期末判定）。"""

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market.trade_calendar_service import NonTradingDayError
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_review_service
from app.services.trading.agent_review_service import (
    NoReviewTargetError,
    PaperTradeReviewContent,
    PaperTradeReviewLockedError,
    resolve_window,
)
from app.services.trading.errors import AgentAccountNotDesignatedError

_TRADE_DATE = date(2026, 7, 15)  # Wednesday


def _agent() -> SimpleNamespace:
    """注册行替身（generate_review 消费的字段）。"""
    return SimpleNamespace(
        agent_key="short-line", llm_config_id=None, methodology_source_id=None
    )


def _cached_row(structured: dict | None):
    """构造 ai_analysis_repository.load_latest_success 的返回值。"""
    if structured is None:
        return None
    row = MagicMock()
    row.structured_output = {"agent_key": "short-line", **structured}
    return row


def _content_dict(period: str = "day") -> dict:
    return {
        "period": period,
        "trade_date": _TRADE_DATE.isoformat(),
        "overall": "整体执行纪律良好",
        "trades": [
            {
                "cl_ord_id": "A",
                "stock_code": "600000",
                "selection_verdict": "correct",
                "plan_verdict": "neutral",
                "execution_verdict": "wrong",
                "reason": "追高买入偏离计划买点",
            }
        ],
        "bias": "偏乐观",
        "suggestion": "严格执行买点纪律",
        "market_context": "主线板块发酵期，情绪偏进攻",
        "methodology_check": [
            {"title": "不追高", "verdict": "violated", "note": "A 笔偏离买点 3% 追高"}
        ],
        "experiences": [
            {"title": "禁止追高", "body": "偏离买点 3% 以上不追", "mem_type": "discipline"}
        ],
    }


def _content() -> PaperTradeReviewContent:
    return PaperTradeReviewContent.model_validate(_content_dict())


@pytest.mark.unit
class TestResolveWindow:
    def test_day_window_is_single_day(self) -> None:
        assert resolve_window("day", _TRADE_DATE) == (_TRADE_DATE, _TRADE_DATE)

    def test_week_window_anchors_monday(self) -> None:
        assert resolve_window("week", _TRADE_DATE) == (date(2026, 7, 13), _TRADE_DATE)

    def test_month_window_starts_day_one(self) -> None:
        assert resolve_window("month", _TRADE_DATE) == (date(2026, 7, 1), _TRADE_DATE)


@pytest.mark.unit
class TestGetReview:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_generated(self) -> None:
        with (
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
        ):
            assert (
                await agent_review_service.get_review(
                    AsyncMock(), "short-line", period="day", trade_date=_TRADE_DATE
                )
                is None
            )

    @pytest.mark.asyncio
    async def test_reads_by_computed_input_hash(self) -> None:
        """同 trade_date 会并存 day/week/month 行：读取按 input_hash
        （agent_key+账户+周期+窗口确定性派生）定位，周期维度不得互串。"""
        mock_load = AsyncMock(return_value=_cached_row(_content_dict(period="day")))
        hashes: dict[str, str] = {}
        with (
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                mock_load,
            ),
        ):
            for period in ("day", "week"):
                await agent_review_service.get_review(
                    AsyncMock(), "short-line", period=period, trade_date=_TRADE_DATE
                )
                hashes[period] = mock_load.await_args.kwargs["input_hash"]

        assert hashes["day"] != hashes["week"]
        assert mock_load.await_args.kwargs["trade_date"] == _TRADE_DATE

    @pytest.mark.asyncio
    async def test_returns_parsed_content(self) -> None:
        with (
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_cached_row(_content_dict())),
            ),
        ):
            content = await agent_review_service.get_review(
                AsyncMock(), "short-line", period="day", trade_date=_TRADE_DATE
            )

        assert content is not None
        assert content.agent_key == "short-line"
        assert content.trades[0].cl_ord_id == "A"
        assert content.experiences[0].mem_type == "discipline"


@pytest.mark.unit
class TestGenerateReview:
    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=False),
            ),
            pytest.raises(NonTradingDayError),
        ):
            await agent_review_service.generate_review(
                AsyncMock(), _agent(), period="day", trade_date=_TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_requires_agent_account(self) -> None:
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.market.trade_calendar_service.resolve_latest_trade_date",
                AsyncMock(return_value=_TRADE_DATE),
            ),
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(side_effect=AgentAccountNotDesignatedError("未指定")),
            ),
            pytest.raises(AgentAccountNotDesignatedError),
        ):
            await agent_review_service.generate_review(AsyncMock(), _agent(), period="day")

    @pytest.mark.asyncio
    async def test_returns_cached_before_readiness_check(self) -> None:
        """缓存命中直接返回，不再触发同步就绪/复盘对象预检。"""
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_cached_row(_content_dict())),
            ),
        ):
            result = await agent_review_service.generate_review(
                AsyncMock(), _agent(), period="day", trade_date=_TRADE_DATE
            )

        assert result.cached is True

    @pytest.mark.asyncio
    async def test_raises_not_ready_before_sync_landed(self) -> None:
        """16:00 盘后同步未落库（当日资金快照缺失）→ 交由 Celery 退避重试。"""
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.trading.agent_review_service._sync_landed",
                AsyncMock(return_value=False),
            ),
            pytest.raises(ReviewInputDataNotReadyError, match="尚未落库"),
        ):
            await agent_review_service.generate_review(
                AsyncMock(), _agent(), period="day", trade_date=_TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_raises_no_target_when_idle_account(self) -> None:
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.trading.agent_review_service._sync_landed",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.agent_review_service._has_review_target",
                AsyncMock(return_value=False),
            ),
            pytest.raises(NoReviewTargetError, match="无交易且无持仓"),
        ):
            await agent_review_service.generate_review(
                AsyncMock(), _agent(), period="day", trade_date=_TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_raises_locked_when_lock_not_acquired(self) -> None:
        @asynccontextmanager
        async def _locked(*args, **kwargs):
            yield False

        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.trading.agent_review_service._sync_landed",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.agent_review_service._has_review_target",
                AsyncMock(return_value=True),
            ),
            patch.object(agent_review_service, "redis_lock", _locked),
            pytest.raises(PaperTradeReviewLockedError, match="正在生成"),
        ):
            await agent_review_service.generate_review(
                AsyncMock(), _agent(), period="day", trade_date=_TRADE_DATE, regenerate=True
            )

    @pytest.mark.asyncio
    async def test_generates_validates_and_persists(self) -> None:
        """就绪路径：LLM 输出 → 幻觉 cl_ord_id 剔除 → 落库（model=None）。"""

        @asynccontextmanager
        async def _locked(*args, **kwargs):
            yield True

        llm_content = _content().model_copy(
            update={
                "trades": _content().trades
                + [
                    _content().trades[0].model_copy(
                        update={"cl_ord_id": "HALLUCINATED", "stock_code": "999999"}
                    )
                ]
            }
        )

        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.services.trading.agent_review_service._sync_landed",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.agent_review_service._has_review_target",
                AsyncMock(return_value=True),
            ),
            patch.object(agent_review_service, "redis_lock", _locked),
            patch(
                "app.services.trading.agent_review_service._collect_window_input",
                AsyncMock(
                    return_value={"orders": [{"cl_ord_id": "A"}, {"cl_ord_id": "B"}]}
                ),
            ),
            patch(
                "app.services.trading.agent_review_service._market_review_optional",
                AsyncMock(return_value={"overall": "主线发酵"}),
            ),
            patch(
                "app.services.trading.agent_methodology.build_methodology_input",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.trading.agent_review_service._run_llm",
                AsyncMock(return_value=llm_content),
            ) as llm_mock,
            patch(
                "app.repositories.review.ai_analysis_repository.insert_result",
                AsyncMock(),
            ) as insert_mock,
        ):
            session = AsyncMock()
            result = await agent_review_service.generate_review(
                session, _agent(), period="day", trade_date=_TRADE_DATE, regenerate=True
            )

        assert result.cached is False
        # 幻觉 cl_ord_id 被剔除，仅保留窗口内真实委托
        assert [t.cl_ord_id for t in result.content.trades] == ["A"]
        llm_mock.assert_awaited_once()
        insert_mock.assert_awaited_once()
        kwargs = insert_mock.await_args.kwargs
        assert kwargs["skill_id"] == agent_review_service.REVIEW_SKILL_ID
        assert kwargs["model"] is None
        assert kwargs["status"] == "success"
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestRunLlmPersona:
    @pytest.mark.asyncio
    async def test_injects_registry_persona_into_user_prompt(self) -> None:
        """复盘 user_prompt 装载 per-agent 技能包契约（D34 skill 化）+ 注册行人设段。"""
        agent = SimpleNamespace(
            agent_key="short-line",
            llm_config_id=None,
            name="短线猎手",
            tagline="趋势短线：顺势而为，快进快出",
        )
        structured = AsyncMock(return_value=_content())
        with patch(
            "app.agent.runtime.structured.run_structured", structured
        ) as run_mock:
            await agent_review_service._run_llm(
                AsyncMock(), agent, "day", _TRADE_DATE, {"orders": []}
            )

        user_prompt = run_mock.await_args.kwargs["user_prompt"]
        # 契约来自 skills/trading-short-line/review_prompt.yaml（真实文件装载）
        assert "复盘官" in user_prompt
        assert "盘面语境" in user_prompt
        assert "方法论验证" in user_prompt
        assert "短线猎手" in user_prompt
        assert "趋势短线：顺势而为，快进快出" in user_prompt
        assert run_mock.await_args.kwargs["config_id"] is None


@pytest.mark.unit
class TestReviewPromptSkillId:
    def test_specific_package_when_registered(self) -> None:
        assert agent_review_service.review_prompt_skill_id("short-line") == (
            "trading-short-line"
        )

    def test_shared_default_fallback_for_unregistered_agent(self) -> None:
        """未建专属技能目录的新 Agent 回退 trading-default（D28 扩展性镜像）。"""
        assert agent_review_service.review_prompt_skill_id("no-such-agent") == (
            "trading-default"
        )


@pytest.mark.unit
class TestMarketReviewOptional:
    @pytest.mark.asyncio
    async def test_returns_sections_when_ready(self) -> None:
        review = {"sections": {"emotion": "主线发酵"}, "date": "2026-07-15"}
        with patch(
            "app.services.trading.agent_plan_input._market_review_sections",
            AsyncMock(return_value=review),
        ):
            result = await agent_review_service._market_review_optional(
                AsyncMock(), _TRADE_DATE
            )
        assert result == {"emotion": "主线发酵"}

    @pytest.mark.asyncio
    async def test_degrades_to_none_when_missing(self) -> None:
        """补跑历史窗口时当日解读缺失：降级 None 不阻塞复盘。"""
        with patch(
            "app.services.trading.agent_plan_input._market_review_sections",
            AsyncMock(side_effect=ReviewInputDataNotReadyError("缺失")),
        ):
            result = await agent_review_service._market_review_optional(
                AsyncMock(), _TRADE_DATE
            )
        assert result is None


@pytest.mark.unit
class TestLegacyCacheCompat:
    def test_backfills_missing_d34_keys(self) -> None:
        """D34 前缓存行缺 market_context/methodology_check：补空值可读。"""
        legacy = {
            k: v
            for k, v in _content_dict().items()
            if k not in ("market_context", "methodology_check")
        }
        content = PaperTradeReviewContent.model_validate(legacy)
        assert content.market_context == ""
        assert content.methodology_check == []
        assert content.overall == "整体执行纪律良好"

    def test_generated_content_carries_new_fields(self) -> None:
        content = _content()
        assert content.market_context == "主线板块发酵期，情绪偏进攻"
        assert content.methodology_check[0].verdict == "violated"


@pytest.mark.unit
class TestValidate:
    def test_filters_hallucinated_cl_ord_ids(self) -> None:
        content = _content()
        patched = content.model_copy(
            update={"trades": content.trades + [content.trades[0].model_copy(update={"cl_ord_id": "X"})]}
        )

        result = agent_review_service._validate(patched, {"A"})

        assert [t.cl_ord_id for t in result.trades] == ["A"]

    def test_keeps_empty_trades(self) -> None:
        content = _content().model_copy(update={"trades": []})

        assert agent_review_service._validate(content, {"A"}).trades == []


@pytest.mark.unit
class TestPeriodEndChecks:
    def _patch_next(
        self, monkeypatch: pytest.MonkeyPatch, next_day: date | None
    ) -> AsyncMock:
        async def fake_next_trading_day(
            session: AsyncMock, day: date
        ) -> date | None:
            return next_day

        monkeypatch.setattr(
            agent_review_service, "next_trading_day", fake_next_trading_day
        )
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_week_false_when_next_day_same_iso_week(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 周三之后周四是交易日 → 未到周期末
        session = self._patch_next(monkeypatch, date(2026, 7, 16))
        assert await agent_review_service.is_last_trading_day_of_week(
            session, _TRADE_DATE
        ) is False

    @pytest.mark.asyncio
    async def test_week_true_when_next_day_crosses_week(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 周五之后下一交易日是下周一 → 周期末
        session = self._patch_next(monkeypatch, date(2026, 7, 20))
        assert await agent_review_service.is_last_trading_day_of_week(
            session, date(2026, 7, 17)
        ) is True

    @pytest.mark.asyncio
    async def test_week_true_when_no_next_trading_day(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert await agent_review_service.is_last_trading_day_of_week(
            self._patch_next(monkeypatch, None), date(2026, 7, 17)
        ) is True

    @pytest.mark.asyncio
    async def test_month_false_when_next_day_same_month(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = self._patch_next(monkeypatch, date(2026, 7, 30))
        assert await agent_review_service.is_last_trading_day_of_month(
            session, date(2026, 7, 29)
        ) is False

    @pytest.mark.asyncio
    async def test_month_true_when_next_day_crosses_month(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = self._patch_next(monkeypatch, date(2026, 8, 3))
        assert await agent_review_service.is_last_trading_day_of_month(
            session, date(2026, 7, 31)
        ) is True


@pytest.mark.unit
class TestRecorderWiring:
    """D35 会话管理：generate_review 全程经 AgentRunRecorder 落执行轨迹。"""

    def _recorder(self) -> MagicMock:
        rec = MagicMock()
        rec.start = AsyncMock()
        rec.finish = AsyncMock()

        @asynccontextmanager
        async def _step(*args, **kwargs):
            yield

        rec.step = MagicMock(side_effect=_step)
        return rec

    @pytest.mark.asyncio
    async def test_cache_hit_finishes_skipped_without_steps(self) -> None:
        rec = self._recorder()
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_cached_row(_content_dict())),
            ),
            patch(
                "app.services.trading.agent_review_service.AgentRunRecorder",
                return_value=rec,
            ),
        ):
            result = await agent_review_service.generate_review(
                AsyncMock(), _agent(), period="day", trade_date=_TRADE_DATE
            )

        assert result.cached is True
        rec.start.assert_awaited_once()
        rec.finish.assert_awaited_once_with(
            "skipped", summary={"cache_hit": True, "stage": "pre_lock"}
        )
        rec.step.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_ready_finishes_failed_then_raises(self) -> None:
        rec = self._recorder()
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.account_service.resolve_agent_account",
                AsyncMock(return_value=MagicMock(id=7)),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.trading.agent_review_service._sync_landed",
                AsyncMock(return_value=False),
            ),
            patch(
                "app.services.trading.agent_review_service.AgentRunRecorder",
                return_value=rec,
            ),
            pytest.raises(ReviewInputDataNotReadyError, match="尚未落库"),
        ):
            await agent_review_service.generate_review(
                AsyncMock(), _agent(), period="day", trade_date=_TRADE_DATE
            )

        rec.finish.assert_awaited_once()
        args, kwargs = rec.finish.await_args
        assert args[0] == "failed"
        assert "尚未落库" in kwargs["error_msg"]
