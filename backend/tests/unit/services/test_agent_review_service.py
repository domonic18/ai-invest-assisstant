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
    return SimpleNamespace(agent_key="short-line", llm_config_id=None)


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
        """复盘 user_prompt 注入注册行人设段（D27：共享复盘契约 + per-agent 视角）。"""
        agent = SimpleNamespace(
            agent_key="short-line",
            llm_config_id=None,
            name="短线猎手",
            tagline="趋势短线：顺势而为，快进快出",
            style_desc="进取",
            strategy_desc="主线板块选股，回踩买点区间接回，破位止损。",
        )
        loader = MagicMock()
        loader.load.return_value = MagicMock(system_prompt="你是模拟盘分层复盘官")
        structured = AsyncMock(return_value=_content())
        with (
            patch(
                "app.services.trading.agent_review_service.get_prompt_loader",
                return_value=loader,
            ),
            patch(
                "app.agent.runtime.structured.run_structured", structured
            ) as run_mock,
        ):
            await agent_review_service._run_llm(
                AsyncMock(), agent, "day", _TRADE_DATE, {"orders": []}
            )

        user_prompt = run_mock.await_args.kwargs["user_prompt"]
        assert "你是模拟盘分层复盘官" in user_prompt
        assert "短线猎手" in user_prompt
        assert "趋势短线：顺势而为，快进快出" in user_prompt
        assert "主线板块选股" in user_prompt
        assert run_mock.await_args.kwargs["config_id"] is None


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
    def _session(self, next_day: date | None) -> AsyncMock:
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=next_day)
        return session

    @pytest.mark.asyncio
    async def test_week_false_when_next_day_same_iso_week(self) -> None:
        # 周三之后周四是交易日 → 未到周期末
        session = self._session(date(2026, 7, 16))
        assert await agent_review_service.is_last_trading_day_of_week(
            session, _TRADE_DATE
        ) is False

    @pytest.mark.asyncio
    async def test_week_true_when_next_day_crosses_week(self) -> None:
        # 周五之后下一交易日是下周一 → 周期末
        session = self._session(date(2026, 7, 20))
        assert await agent_review_service.is_last_trading_day_of_week(
            session, date(2026, 7, 17)
        ) is True

    @pytest.mark.asyncio
    async def test_week_true_when_no_next_trading_day(self) -> None:
        assert await agent_review_service.is_last_trading_day_of_week(
            self._session(None), date(2026, 7, 17)
        ) is True

    @pytest.mark.asyncio
    async def test_month_false_when_next_day_same_month(self) -> None:
        session = self._session(date(2026, 7, 30))
        assert await agent_review_service.is_last_trading_day_of_month(
            session, date(2026, 7, 29)
        ) is False

    @pytest.mark.asyncio
    async def test_month_true_when_next_day_crosses_month(self) -> None:
        session = self._session(date(2026, 8, 3))
        assert await agent_review_service.is_last_trading_day_of_month(
            session, date(2026, 7, 31)
        ) is True
