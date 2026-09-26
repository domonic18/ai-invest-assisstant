"""交易 Agent 注册表服务测试（agent-hub-plan.md D21）。

覆盖：agent_key 读取 404 / active 门禁 / wire 视图映射 / 局部更新 /
LLM 绑定校验（404/停用/非 chat）/ 方法论知识源校验 / planned 不可写。
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.kb import KbSource
from app.models.paper_trade import TradingAgent
from app.schemas.paper_trade import TradingAgentProfileUpdateRequest
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
    async def test_planned_agent_not_writable(self) -> None:
        session = _session()
        session.get = AsyncMock(return_value=_row(status="planned"))
        with pytest.raises(UnprocessableEntityError, match="未激活"):
            await svc.update_agent(
                session, "short-line", data=TradingAgentProfileUpdateRequest(name="改名")
            )

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
