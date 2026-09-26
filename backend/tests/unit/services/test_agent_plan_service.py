"""交易 Agent 每日计划生成服务契约测试（批次 7：缓存/预检/校验/落库）。"""

from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market.trade_calendar_service import NonTradingDayError
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_plan_service
from app.services.trading.agent_plan_service import (
    AgentDailyPlanContent,
    PlanTradePlanItem,
)

_TRADE_DATE = date(2026, 7, 15)  # Wednesday


def _content_dict() -> dict:
    return {
        "trade_date": _TRADE_DATE.isoformat(),
        "selections": [{"stock_code": "600000", "reason": "复盘主线延续", "confidence": 0.8}],
        "plans": [
            {
                "stock_code": "600000",
                "plan_type": "buy",
                "strategy": "回踩买点区间接回",
                "buy_zone_low": 9.9,
                "buy_zone_high": 10.2,
                "target_price": 11.0,
                "stop_loss": 9.5,
                "position_pct": 10,
                "basis": "当日复盘解读 + 涨停归因",
            }
        ],
    }


def _content() -> AgentDailyPlanContent:
    return AgentDailyPlanContent.model_validate(_content_dict())


@pytest.mark.unit
class TestSchemaContract:
    def test_content_fields_all_required(self) -> None:
        """LLM 结构化输出契约铁律：字段禁默认值（默认值不进 required）。"""
        required = set(AgentDailyPlanContent.model_json_schema()["required"])
        assert {"trade_date", "selections", "plans"} <= required

    def test_plan_item_fields_all_required(self) -> None:
        required = set(PlanTradePlanItem.model_json_schema()["required"])
        assert {
            "stock_code",
            "plan_type",
            "strategy",
            "buy_zone_low",
            "buy_zone_high",
            "target_price",
            "stop_loss",
            "position_pct",
            "basis",
        } <= required

    def test_normalizes_chinese_plan_type(self) -> None:
        item = PlanTradePlanItem(**{**_content_dict()["plans"][0], "plan_type": "买入"})
        assert item.plan_type == "buy"

    def test_rejects_unknown_plan_type(self) -> None:
        with pytest.raises(ValueError):
            PlanTradePlanItem(**{**_content_dict()["plans"][0], "plan_type": "观望"})


@pytest.mark.unit
class TestGenerateDailyPlan:
    @pytest.mark.asyncio
    async def test_requires_paper_trade_configured(self) -> None:
        with patch(
            "app.core.config.get_settings",
            return_value=MagicMock(paper_trade_url=""),
        ):
            from app.services.trading.errors import PaperTradeNotConfiguredError

            with pytest.raises(PaperTradeNotConfiguredError):
                await agent_plan_service.generate_daily_plan(AsyncMock())

    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        with (
            patch(
                "app.core.config.get_settings",
                return_value=MagicMock(paper_trade_url="http://sidecar"),
            ),
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=False),
            ),
            pytest.raises(NonTradingDayError),
        ):
            await agent_plan_service.generate_daily_plan(
                AsyncMock(), trade_date=_TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_raises_not_ready_when_review_missing(self) -> None:
        """复盘解读未生成（18:35 前）→ 输入未就绪，交由 Celery 退避重试。"""
        with (
            patch(
                "app.core.config.get_settings",
                return_value=MagicMock(paper_trade_url="http://sidecar"),
            ),
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
            pytest.raises(ReviewInputDataNotReadyError, match="尚未生成"),
        ):
            await agent_plan_service.generate_daily_plan(
                AsyncMock(), trade_date=_TRADE_DATE, regenerate=True
            )

    @pytest.mark.asyncio
    async def test_returns_cached_without_llm(self) -> None:
        row = MagicMock()
        row.structured_output = _content_dict()
        with (
            patch(
                "app.core.config.get_settings",
                return_value=MagicMock(paper_trade_url="http://sidecar"),
            ),
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
                AsyncMock(return_value=row),
            ) as load_mock,
        ):
            result = await agent_plan_service.generate_daily_plan(
                AsyncMock(), trade_date=_TRADE_DATE
            )

        assert result.cached is True
        assert result.dropped_codes == []
        assert result.content.selections[0].stock_code == "600000"
        kwargs = load_mock.await_args.kwargs
        assert kwargs["skill_id"] == agent_plan_service.PLAN_SKILL_ID
        assert "input_hash" in kwargs

    @pytest.mark.asyncio
    async def test_generates_validates_and_persists(self) -> None:
        """生成主链路：LLM → 校验剔除 → 缓存行 + 两表 upsert（source_result_id 回填）。"""

        @asynccontextmanager
        async def _locked(*args, **kwargs):
            yield True

        content = _content()
        with (
            patch(
                "app.core.config.get_settings",
                return_value=MagicMock(paper_trade_url="http://sidecar"),
            ),
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
                "app.services.trading.agent_plan_service._collect_plan_input",
                AsyncMock(return_value=({}, [])),
            ),
            patch.object(agent_plan_service, "redis_lock", _locked),
            patch(
                "app.services.trading.agent_plan_service._run_llm",
                AsyncMock(return_value=content),
            ) as llm_mock,
            patch(
                "app.services.trading.agent_plan_service._validate_codes",
                AsyncMock(return_value=(content, ["999999"])),
            ),
            patch(
                "app.repositories.review.ai_analysis_repository.insert_result",
                AsyncMock(return_value=42),
            ) as insert_mock,
            patch(
                "app.services.trading.agent_plan_service._persist",
                AsyncMock(),
            ) as persist_mock,
        ):
            result = await agent_plan_service.generate_daily_plan(
                AsyncMock(), trade_date=_TRADE_DATE, regenerate=True
            )

        assert result.cached is False
        assert result.dropped_codes == ["999999"]
        llm_mock.assert_awaited_once()
        insert_mock.assert_awaited_once()
        assert insert_mock.await_args.kwargs["skill_id"] == agent_plan_service.PLAN_SKILL_ID
        persist_mock.assert_awaited_once()
        assert persist_mock.await_args.kwargs["source_result_id"] == 42
        assert persist_mock.await_args.kwargs["trade_date"] == _TRADE_DATE

    @pytest.mark.asyncio
    async def test_raises_locked_when_lock_not_acquired(self) -> None:
        @asynccontextmanager
        async def _locked(*args, **kwargs):
            yield False

        with (
            patch(
                "app.core.config.get_settings",
                return_value=MagicMock(paper_trade_url="http://sidecar"),
            ),
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
                "app.services.trading.agent_plan_service._collect_plan_input",
                AsyncMock(return_value=({}, [])),
            ),
            patch.object(agent_plan_service, "redis_lock", _locked),
            pytest.raises(agent_plan_service.PlanGenerationLockedError, match="正在生成"),
        ):
            await agent_plan_service.generate_daily_plan(
                AsyncMock(), trade_date=_TRADE_DATE, regenerate=True
            )


@pytest.mark.unit
class TestActiveMemories:
    @pytest.mark.asyncio
    async def test_missing_table_degrades_to_empty(self) -> None:
        """批次 9 建 agent_memory 前（UndefinedTable → ProgrammingError）降级空集。"""
        from sqlalchemy.exc import ProgrammingError

        nested = MagicMock()
        nested.__aenter__ = AsyncMock(return_value=None)
        nested.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.begin_nested = MagicMock(return_value=nested)
        session.execute = AsyncMock(
            side_effect=ProgrammingError(
                "SELECT title, body, mem_type FROM agent_memory",
                {},
                RuntimeError('relation "agent_memory" does not exist'),
            )
        )

        assert await agent_plan_service._active_memories(session) == []
        # SAVEPOINT 已退出（回滚），外层事务保持可用
        nested.__aexit__.assert_awaited_once()


@pytest.mark.unit
class TestCollectPlanInput:
    @pytest.mark.asyncio
    async def test_includes_methodology_and_memories(self) -> None:
        """输入组装含方法论基座（方案 A KB 直读）与经验记忆，检索 query 取自盘面输入。"""
        review_row = MagicMock()
        review_row.structured_output = {"sections": {"overall": "主线高位分歧"}}
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=review_row),
            ),
            patch(
                "app.services.review.limit_up_ai_service.get_cached_attribution",
                AsyncMock(return_value=None),
            ),
            patch.object(
                agent_plan_service, "_stock_anomalies", AsyncMock(return_value=[])
            ),
            patch.object(
                agent_plan_service,
                "_manual_removed_codes",
                AsyncMock(return_value=[]),
            ),
            patch.object(
                agent_plan_service, "_local_positions", AsyncMock(return_value=[])
            ),
            patch.object(
                agent_plan_service,
                "_active_memories",
                AsyncMock(return_value=[{"title": "禁追高"}]),
            ),
            patch(
                "app.services.trading.agent_plan_service.agent_methodology"
                ".build_methodology_input",
                AsyncMock(return_value={"disciplines": [{"id": 2086}]}),
            ) as build_mock,
        ):
            plan_input, _ = await agent_plan_service._collect_plan_input(
                AsyncMock(), 7, _TRADE_DATE
            )

        assert plan_input["methodology"] == {"disciplines": [{"id": 2086}]}
        assert plan_input["memories"] == [{"title": "禁追高"}]
        assert "主线高位分歧" in build_mock.await_args.kwargs["query_text"]

    @pytest.mark.asyncio
    async def test_methodology_degrades_to_none(self) -> None:
        """未配置方法论知识源 → methodology 键为 None，其余输入不受影响。"""
        review_row = MagicMock()
        review_row.structured_output = {"sections": {"overall": "缩量整理"}}
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=review_row),
            ),
            patch(
                "app.services.review.limit_up_ai_service.get_cached_attribution",
                AsyncMock(return_value=None),
            ),
            patch.object(
                agent_plan_service, "_stock_anomalies", AsyncMock(return_value=[])
            ),
            patch.object(
                agent_plan_service,
                "_manual_removed_codes",
                AsyncMock(return_value=[]),
            ),
            patch.object(
                agent_plan_service, "_local_positions", AsyncMock(return_value=[])
            ),
            patch.object(
                agent_plan_service, "_active_memories", AsyncMock(return_value=[])
            ),
            patch(
                "app.services.trading.agent_plan_service.agent_methodology"
                ".build_methodology_input",
                AsyncMock(return_value=None),
            ),
        ):
            plan_input, _ = await agent_plan_service._collect_plan_input(
                AsyncMock(), 7, _TRADE_DATE
            )

        assert plan_input["methodology"] is None


@pytest.mark.unit
class TestValidateCodes:
    @pytest.mark.asyncio
    async def test_drops_hallucinated_and_manual_removed(self) -> None:
        content = _content().model_copy(
            update={
                "selections": _content().selections
                + [
                    agent_plan_service.PlanSelectionItem(
                        stock_code="999999", reason="幻觉代码", confidence=None
                    )
                ],
            }
        )
        session = AsyncMock()
        executed = MagicMock()
        executed.scalars.return_value.all.return_value = ["600000"]
        session.execute = AsyncMock(return_value=executed)

        validated, dropped = await agent_plan_service._validate_codes(
            session, content, manual_removed=["600519"]
        )
        # 幻觉代码 999999 被剔除（600519 不在清单中，不重复计）
        assert [s.stock_code for s in validated.selections] == ["600000"]
        assert dropped == ["999999"]

    @pytest.mark.asyncio
    async def test_drops_manual_removed_selection(self) -> None:
        """人工移出代码被 LLM 重复选入时兜底剔除（prompt 禁选 + 服务层双保险）。"""
        content = _content().model_copy(
            update={
                "selections": _content().selections
                + [
                    agent_plan_service.PlanSelectionItem(
                        stock_code="600519", reason="再次候选", confidence=0.7
                    )
                ],
            }
        )
        session = AsyncMock()
        executed = MagicMock()
        executed.scalars.return_value.all.return_value = ["600000", "600519"]
        session.execute = AsyncMock(return_value=executed)

        validated, dropped = await agent_plan_service._validate_codes(
            session, content, manual_removed=["600519"]
        )
        assert [s.stock_code for s in validated.selections] == ["600000"]
        assert dropped == ["600519"]
