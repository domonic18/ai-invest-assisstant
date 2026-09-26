"""交易 Agent 配置服务测试（单例读取/兜底创建/局部更新/LLM 绑定校验）。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.schemas.paper_trade import TradingAgentConfigUpdateRequest
from app.services.trading import agent_config as svc


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.get = AsyncMock()
    return session


def _row(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": 1,
        "llm_config_id": None,
        "risk_max_position_pct": 20.0,
        "risk_max_total_pct": 80.0,
        "risk_max_daily_orders": 10,
        "auto_exec_enabled": True,
        "updated_at": datetime(2026, 9, 25, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _llm(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {"id": 7, "name": "kimi", "is_active": True, "purpose": "chat"}
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
class TestGetConfigRow:
    @pytest.mark.asyncio
    async def test_returns_existing_row(self) -> None:
        session = _session()
        row = _row()
        session.get = AsyncMock(return_value=row)
        assert await svc.get_config_row(session) is row
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_row_creates_singleton_fallback(self) -> None:
        """迁移 seed 缺失时兜底创建 id=1（kb_settings 先例）。"""
        session = _session()
        session.get = AsyncMock(return_value=None)
        row = await svc.get_config_row(session)
        assert row.id == svc.CONFIG_ID
        session.add.assert_called_once_with(row)
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestUpdateConfig:
    @pytest.mark.asyncio
    async def test_partial_update_touches_only_submitted_fields(self) -> None:
        session = _session()
        row = _row()
        session.get = AsyncMock(return_value=row)
        result = await svc.update_config(
            session, data=TradingAgentConfigUpdateRequest(auto_exec_enabled=False)
        )
        assert result.auto_exec_enabled is False
        assert row.risk_max_position_pct == 20.0
        assert row.llm_config_id is None
        assert row.updated_at is not None
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_config_none_clears_binding_without_lookup(self) -> None:
        session = _session()
        row = _row(llm_config_id=7)
        session.get = AsyncMock(return_value=row)
        await svc.update_config(
            session, data=TradingAgentConfigUpdateRequest(llm_config_id=None)
        )
        assert row.llm_config_id is None
        # session.get 只被调了一次（config 行本身），未查 LLMConfig
        assert session.get.await_count == 1

    @pytest.mark.asyncio
    async def test_llm_config_missing_raises_404(self) -> None:
        session = _session()

        async def _get(_type, key):
            return None if key == 99 else _row()

        session.get = AsyncMock(side_effect=_get)
        with pytest.raises(NotFoundError, match="99"):
            await svc.update_config(
                session, data=TradingAgentConfigUpdateRequest(llm_config_id=99)
            )

    @pytest.mark.asyncio
    async def test_llm_config_inactive_raises_422(self) -> None:
        session = _session()

        async def _get(_type, key):
            return _row() if key == 1 else _llm(is_active=False)

        session.get = AsyncMock(side_effect=_get)
        with pytest.raises(UnprocessableEntityError, match="停用"):
            await svc.update_config(
                session, data=TradingAgentConfigUpdateRequest(llm_config_id=7)
            )

    @pytest.mark.asyncio
    async def test_llm_config_non_chat_purpose_raises_422(self) -> None:
        session = _session()

        async def _get(_type, key):
            return _row() if key == 1 else _llm(purpose="embedding")

        session.get = AsyncMock(side_effect=_get)
        with pytest.raises(UnprocessableEntityError, match="chat"):
            await svc.update_config(
                session, data=TradingAgentConfigUpdateRequest(llm_config_id=7)
            )

    @pytest.mark.asyncio
    async def test_llm_config_valid_assigns(self) -> None:
        session = _session()

        async def _get(_type, key):
            return _row() if key == 1 else _llm()

        session.get = AsyncMock(side_effect=_get)
        result = await svc.update_config(
            session, data=TradingAgentConfigUpdateRequest(llm_config_id=7)
        )
        assert result.llm_config_id == 7
