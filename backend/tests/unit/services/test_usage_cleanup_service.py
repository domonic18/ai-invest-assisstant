"""用量记录手动清理服务测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.account_quota import AdminAuditLog
from app.services.quota.usage_cleanup_service import cleanup_token_usage


@pytest.mark.unit
class TestCleanupTokenUsage:
    async def test_deletes_records_and_writes_audit(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        execute_result = MagicMock()
        execute_result.rowcount = 42
        session.execute.return_value = execute_result

        removed = await cleanup_token_usage(session, actor_id=1, ip="127.0.0.1")

        assert removed == 42
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, AdminAuditLog)
        assert added.action == "usage.cleanup"
        assert added.detail == {"retention_days": 180, "removed_count": 42}
        assert added.actor_id == 1
        assert added.ip == "127.0.0.1"

    async def test_retention_days_override_and_zero_rowcount(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        execute_result = MagicMock()
        execute_result.rowcount = 0
        session.execute.return_value = execute_result

        removed = await cleanup_token_usage(session, actor_id=2, retention_days=30)

        assert removed == 0
        added = session.add.call_args[0][0]
        assert added.detail == {"retention_days": 30, "removed_count": 0}
