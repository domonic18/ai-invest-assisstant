"""交易 Agent 注册表服务测试（agent-hub-plan.md D21/D28/D29）。

覆盖：agent_key 读取 404 / active 门禁 / wire 视图映射 / 局部更新 /
LLM 绑定校验（404/停用/非 chat）/ 方法论知识源校验 / 任意状态可写 +
status/cadence 开关（D28）/ 人设模板清单 + 创建（校验与默认值）+
删除级联（解绑账户/清三表/会话 checkpoint，D29）。
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.models.kb import KbSource
from app.models.paper_trade import TradingAgent
from app.schemas.paper_trade import (
    TradingAgentCreateRequest,
    TradingAgentProfileUpdateRequest,
)
from app.services.trading import agent_registry as svc


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.get = AsyncMock()
    return session


def _row(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "agent_key": "short-line",
        "name": "短线猎手",
        "tagline": "日内强势股猎手",
        "strategy_desc": "打板/低吸",
        "style_desc": "激进",
        "llm_config_id": None,
        "methodology_source_id": None,
        "risk_max_position_pct": 20.0,
        "risk_max_total_pct": 80.0,
        "risk_max_daily_orders": 10,
        "auto_exec_enabled": True,
        "status": "active",
        "plan_cadence": "daily",
        "review_cadence": "daily",
        "sort_order": 1,
        "prompt_id": "trading_agent",
        "accent_color": "#3b82f6",
        "updated_at": datetime(2026, 9, 25, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _llm(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {"id": 7, "name": "kimi", "is_active": True, "purpose": "chat"}
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
class TestGetAgent:
    @pytest.mark.asyncio
    async def test_returns_registered_row(self) -> None:
        session = _session()
        row = _row()
        session.get = AsyncMock(return_value=row)
        assert await svc.get_agent(session, "short-line") is row

    @pytest.mark.asyncio
    async def test_unknown_key_raises_404(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="long-line"):
            await svc.get_agent(session, "long-line")

    @pytest.mark.asyncio
    async def test_active_gate_passes_for_active(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=_row())
        assert (await svc.get_active_agent(session, "short-line")).agent_key == "short-line"

    @pytest.mark.asyncio
    async def test_active_gate_rejects_planned(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=_row(agent_key="long-line", status="planned"))
        with pytest.raises(UnprocessableEntityError, match="planned"):
            await svc.get_active_agent(session, "long-line")


@pytest.mark.unit
class TestToView:
    def test_maps_all_registry_fields(self) -> None:
        view = svc.to_view(_row(risk_max_position_pct="20.00"))
        assert view.agent_key == "short-line"
        assert view.risk_max_position_pct == 20.0
        assert view.status == "active"
        assert view.plan_cadence == "daily"
        assert view.review_cadence == "daily"
        assert view.accent_color == "#3b82f6"


@pytest.mark.unit
class TestUpdateAgent:
    @pytest.mark.asyncio
    async def test_partial_update_touches_only_submitted_fields(self) -> None:
        session = _session()
        row = _row()
        session.get = AsyncMock(return_value=row)
        result = await svc.update_agent(
            session, "short-line", data=TradingAgentProfileUpdateRequest(auto_exec_enabled=False)
        )
        assert result.auto_exec_enabled is False
        assert row.risk_max_position_pct == 20.0
        assert row.llm_config_id is None
        assert row.updated_at is not None
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_planned_agent_writable_for_config(self) -> None:
        """D28：任意状态可写（未上线/停用的 Agent 也可先配置）。"""
        session = _session()
        session.get = AsyncMock(return_value=_row(status="planned"))
        result = await svc.update_agent(
            session, "short-line", data=TradingAgentProfileUpdateRequest(name="改名")
        )
        assert result.name == "改名"

    @pytest.mark.asyncio
    async def test_planned_agent_status_flips_to_active(self) -> None:
        """启用未上线 Agent：status 置 active + 可同步改频率。"""
        session = _session()
        session.get = AsyncMock(return_value=_row(status="planned"))
        result = await svc.update_agent(
            session,
            "short-line",
            data=TradingAgentProfileUpdateRequest(
                status="active", plan_cadence="weekly"
            ),
        )
        assert result.status == "active"
        assert result.plan_cadence == "weekly"

    def test_status_planned_rejected_by_schema(self) -> None:
        """'planned' 仅为种子初始态，API 不可设置（请求体校验直接拒绝）。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TradingAgentProfileUpdateRequest(status="planned")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_llm_config_none_clears_binding_without_lookup(self) -> None:
        session = _session()
        row = _row(llm_config_id=7)
        session.get = AsyncMock(return_value=row)
        await svc.update_agent(
            session, "short-line", data=TradingAgentProfileUpdateRequest(llm_config_id=None)
        )
        assert row.llm_config_id is None
        # session.get 只被调了一次（注册行本身），未查 LLMConfig
        assert session.get.await_count == 1

    @pytest.mark.asyncio
    async def test_llm_config_missing_raises_404(self) -> None:
        session = _session()

        async def _get(_type, key):
            return None if key == 99 else _row()

        session.get = AsyncMock(side_effect=_get)
        with pytest.raises(NotFoundError, match="99"):
            await svc.update_agent(
                session, "short-line", data=TradingAgentProfileUpdateRequest(llm_config_id=99)
            )

    @pytest.mark.asyncio
    async def test_llm_config_inactive_raises_422(self) -> None:
        session = _session()

        async def _get(_type, key):
            return _row() if _type is TradingAgent else _llm(is_active=False)

        session.get = AsyncMock(side_effect=_get)
        with pytest.raises(UnprocessableEntityError, match="停用"):
            await svc.update_agent(
                session, "short-line", data=TradingAgentProfileUpdateRequest(llm_config_id=7)
            )

    @pytest.mark.asyncio
    async def test_llm_config_non_chat_purpose_raises_422(self) -> None:
        session = _session()

        async def _get(_type, key):
            return _row() if _type is TradingAgent else _llm(purpose="embedding")

        session.get = AsyncMock(side_effect=_get)
        with pytest.raises(UnprocessableEntityError, match="chat"):
            await svc.update_agent(
                session, "short-line", data=TradingAgentProfileUpdateRequest(llm_config_id=7)
            )

    @pytest.mark.asyncio
    async def test_llm_config_valid_assigns(self) -> None:
        session = _session()

        async def _get(_type, key):
            return _row() if _type is TradingAgent else _llm()

        session.get = AsyncMock(side_effect=_get)
        result = await svc.update_agent(
            session, "short-line", data=TradingAgentProfileUpdateRequest(llm_config_id=7)
        )
        assert result.llm_config_id == 7

    @pytest.mark.asyncio
    async def test_methodology_source_none_clears_without_lookup(self) -> None:
        """置空 = 未启用方法论基座注入（不做知识源查询）。"""
        session = _session()
        row = _row(methodology_source_id=1)
        session.get = AsyncMock(return_value=row)
        result = await svc.update_agent(
            session, "short-line", data=TradingAgentProfileUpdateRequest(methodology_source_id=None)
        )
        assert result.methodology_source_id is None
        assert session.get.await_count == 1

    @pytest.mark.asyncio
    async def test_methodology_source_missing_raises_404(self) -> None:
        session = _session()

        async def _get(_type, key):
            return None if key == 99 else _row()

        session.get = AsyncMock(side_effect=_get)
        with pytest.raises(NotFoundError, match="99"):
            await svc.update_agent(
                session,
                "short-line",
                data=TradingAgentProfileUpdateRequest(methodology_source_id=99),
            )

    @pytest.mark.asyncio
    async def test_methodology_source_disabled_raises_422(self) -> None:
        session = _session()

        async def _get(_type, key):
            if _type is KbSource:
                return SimpleNamespace(id=key, name="旧书", enabled=False)
            return _row()

        session.get = AsyncMock(side_effect=_get)
        with pytest.raises(UnprocessableEntityError, match="停用"):
            await svc.update_agent(
                session,
                "short-line",
                data=TradingAgentProfileUpdateRequest(methodology_source_id=2),
            )

    @pytest.mark.asyncio
    async def test_methodology_source_valid_assigns(self) -> None:
        session = _session()

        async def _get(_type, key):
            if _type is KbSource:
                return SimpleNamespace(id=key, name="趋势理论", enabled=True)
            return _row()

        session.get = AsyncMock(side_effect=_get)
        result = await svc.update_agent(
            session,
            "short-line",
            data=TradingAgentProfileUpdateRequest(methodology_source_id=1),
        )
        assert result.methodology_source_id == 1


def _create_data(**overrides: object) -> TradingAgentCreateRequest:
    fields: dict[str, object] = {
        "agent_key": "test-agent",
        "name": "测试 Agent",
        "tagline": "一句话定位",
        "prompt_id": "trading_agent_short_line",
    }
    fields.update(overrides)
    return TradingAgentCreateRequest(**fields)


@pytest.mark.unit
class TestListPromptTemplates:
    def test_lists_yaml_personas_with_labels(self) -> None:
        templates = svc.list_prompt_templates()
        ids = {t.prompt_id for t in templates}
        assert {"trading_agent_short_line", "trading_agent_long_line", "trading_agent_m60"} <= ids
        for template in templates:
            assert template.label


@pytest.mark.unit
class TestCreateAgent:
    @pytest.mark.asyncio
    async def test_defaults_active_with_conservative_risk(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=None)
        session.scalar = AsyncMock(return_value=3)
        session.add = MagicMock()
        result = await svc.create_agent(session, data=_create_data())
        assert result.status == "active"
        assert result.sort_order == 4
        assert result.risk_max_position_pct == 20.0
        assert result.risk_max_total_pct == 60.0
        assert result.risk_max_daily_orders == 10
        assert result.auto_exec_enabled is False
        assert result.plan_cadence == "daily"
        assert result.review_cadence == "daily"
        assert result.accent_color == "#38bdf8"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_key_conflicts_409(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=_row())
        with pytest.raises(ConflictError, match="已存在"):
            await svc.create_agent(session, data=_create_data())

    @pytest.mark.asyncio
    async def test_invalid_key_rejected_422(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=None)
        for bad_key in ("Bad Key", "A-upper", "-lead"):
            with pytest.raises(UnprocessableEntityError, match="agent_key"):
                await svc.create_agent(session, data=_create_data(agent_key=bad_key))

    @pytest.mark.asyncio
    async def test_unknown_prompt_template_rejected_422(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(UnprocessableEntityError, match="人设模板"):
            await svc.create_agent(
                session, data=_create_data(prompt_id="trading_agent_nope")
            )

    @pytest.mark.asyncio
    async def test_llm_binding_validated_on_create(self) -> None:
        session = _session()
        # 注册行不存在（过重复检查）且 llm_config 99 不存在（404）
        session.get = AsyncMock(return_value=None)
        session.scalar = AsyncMock(return_value=0)
        session.add = MagicMock()
        with pytest.raises(NotFoundError, match="99"):
            await svc.create_agent(session, data=_create_data(llm_config_id=99))

    @pytest.mark.asyncio
    async def test_cadence_and_optional_fields_applied(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=None)
        session.scalar = AsyncMock(return_value=0)
        session.add = MagicMock()
        result = await svc.create_agent(
            session,
            data=_create_data(
                plan_cadence="weekly",
                review_cadence="monthly",
                strategy_desc="策略",
                style_desc="稳健",
                accent_color="#22d3ee",
            ),
        )
        assert result.plan_cadence == "weekly"
        assert result.review_cadence == "monthly"
        assert result.strategy_desc == "策略"
        assert result.style_desc == "稳健"
        assert result.accent_color == "#22d3ee"


@pytest.mark.unit
class TestDeleteAgent:
    @pytest.mark.asyncio
    async def test_cascades_account_unbind_tables_sessions_registry(self) -> None:
        session = _session()
        row = _row()
        session.get = AsyncMock(return_value=row)
        session.execute = AsyncMock()
        thread_id = uuid.uuid4()
        session.scalars = AsyncMock(return_value=[thread_id])
        session.delete = AsyncMock()
        checkpointer = MagicMock()
        checkpointer.adelete_thread = AsyncMock()
        with patch(
            "app.agent.runtime.assistant_agent.get_checkpointer",
            new_callable=AsyncMock,
            return_value=checkpointer,
        ):
            sessions_removed = await svc.delete_agent(session, "short-line")

        assert sessions_removed == 1
        checkpointer.adelete_thread.assert_awaited_once_with(str(thread_id))
        # 解绑账户 + 三表清理 + 会话清理 = 5 条批量语句
        assert session.execute.await_count == 5
        session.delete.assert_awaited_once_with(row)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_sessions_skips_checkpointer(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=_row())
        session.execute = AsyncMock()
        session.scalars = AsyncMock(return_value=[])
        session.delete = AsyncMock()
        with patch(
            "app.agent.runtime.assistant_agent.get_checkpointer",
            new_callable=AsyncMock,
        ) as get_cp_mock:
            assert await svc.delete_agent(session, "short-line") == 0
        get_cp_mock.assert_not_awaited()
        session.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_key_raises_404(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="ghost"):
            await svc.delete_agent(session, "ghost")
