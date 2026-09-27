"""builtin skill 启动同步契约测试：trading 场景不投影进 DB 技能表（D27）。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.skill.skill_sync import sync_builtin_skills


@pytest.mark.unit
class TestSyncBuiltinSkills:
    @pytest.mark.asyncio
    async def test_trading_scenario_not_projected(self) -> None:
        """交易 Agent 内部作业技能不进 skill 表：不进技能广场、不参与安装体系。"""
        session = AsyncMock()
        executed = MagicMock()
        executed.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=executed)
        added: list[MagicMock] = []
        session.add = MagicMock(side_effect=added.append)  # add 是同步方法

        await sync_builtin_skills(session)

        ids = {row.skill_id for row in added}
        assert ids, "非 trading builtin 应全部投影"
        assert not ids & {"trading-short-line", "trading-long-line", "trading-m60"}
        assert "market-daily-review" in ids
