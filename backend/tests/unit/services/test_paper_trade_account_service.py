"""模拟盘账户配置服务测试（CRUD 校验 / 租户隔离 / agent 指定唯一 / 删除守卫）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.services.trading import account_service as svc


def _session() -> MagicMock:
    """MagicMock 会话：commit/refresh/get/scalar/delete 为 AsyncMock。"""
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock()
    session.scalar = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.unit
class TestCredentials:
    def test_credentials_for_decrypts_token(self) -> None:
        account = SimpleNamespace(token_encrypted="cipher", counter_account_id="acc-1")
        with patch.object(svc, "decrypt_token", lambda cipher: "plain"):
            cred = svc.credentials_for(account)
        assert cred.token == "plain"
        assert cred.account_id == "acc-1"


@pytest.mark.unit
class TestResolveForUser:
    @pytest.mark.asyncio
    async def test_missing_account_raises_404(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await svc.resolve_for_user(session, user_id=1, account_id=99)

    @pytest.mark.asyncio
    async def test_cross_tenant_account_raises_404(self) -> None:
        """他人账户与不存在同样 404（不泄露存在性）。"""
        session = MagicMock()
        session.get = AsyncMock(
            return_value=SimpleNamespace(id=5, user_id=2, is_agent=False)
        )
        with pytest.raises(NotFoundError):
            await svc.resolve_for_user(session, user_id=1, account_id=5)

    @pytest.mark.asyncio
    async def test_own_account_resolves(self) -> None:
        session = MagicMock()
        account = SimpleNamespace(id=5, user_id=1)
        session.get = AsyncMock(return_value=account)
        assert await svc.resolve_for_user(session, 1, 5) is account


@pytest.mark.unit
class TestCreateAccount:
    @pytest.mark.asyncio
    async def test_duplicate_counter_account_conflicts(self) -> None:
        session = MagicMock()
        session.scalar = AsyncMock(return_value=SimpleNamespace(id=8))

        with pytest.raises(ConflictError, match="全平台唯一"):
            await svc.create_account(
                session, 1, name="x", token="t", counter_account_id="acc-1"
            )
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_per_user_cap(self) -> None:
        session = MagicMock()
        session.scalar = AsyncMock(side_effect=[None, svc.MAX_ACCOUNTS_PER_USER])

        with pytest.raises(ConflictError, match="最多"):
            await svc.create_account(
                session, 1, name="x", token="t", counter_account_id="acc-9"
            )
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_encrypts_token_and_commits(self) -> None:
        session = _session()
        session.scalar = AsyncMock(side_effect=[None, 0])

        with patch.object(svc, "encrypt_token", lambda plain: f"enc:{plain}"):
            account = await svc.create_account(
                session, 1, name="人工盘", token="tok", counter_account_id="acc-1"
            )

        assert account.token_encrypted == "enc:tok"
        assert account.user_id == 1
        session.add.assert_called_once()
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestUpdateAccount:
    @pytest.mark.asyncio
    async def test_swap_counter_account_conflicts(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(
            return_value=SimpleNamespace(
                id=5, user_id=1, counter_account_id="old", name="n", token_encrypted="c"
            )
        )
        session.scalar = AsyncMock(return_value=SimpleNamespace(id=8))
        session.refresh = AsyncMock()

        with pytest.raises(ConflictError, match="全平台唯一"):
            await svc.update_account(session, 1, 5, counter_account_id="acc-taken")

    @pytest.mark.asyncio
    async def test_update_reencrypts_and_commits(self) -> None:
        session = _session()
        account = SimpleNamespace(
            id=5, user_id=1, counter_account_id="old", name="n", token_encrypted="c"
        )
        session.get = AsyncMock(return_value=account)
        session.scalar = AsyncMock(return_value=None)
        session.refresh = AsyncMock()

        with patch.object(svc, "encrypt_token", lambda plain: f"enc:{plain}"):
            await svc.update_account(session, 1, 5, name="新名", token="new-tok")

        assert account.name == "新名"
        assert account.token_encrypted == "enc:new-tok"
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestDeleteAccount:
    @pytest.mark.asyncio
    async def test_rejects_when_has_orders(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(
            return_value=SimpleNamespace(id=5, user_id=1, is_agent=False)
        )
        session.scalar = AsyncMock(side_effect=[7, None, None])  # 委托表命中

        with pytest.raises(ConflictError, match="禁止删除"):
            await svc.delete_account(session, 1, 5)
        session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_when_no_data(self) -> None:
        session = _session()
        account = SimpleNamespace(id=5, user_id=1)
        session.get = AsyncMock(return_value=account)
        session.scalar = AsyncMock(side_effect=[None, None, None])

        await svc.delete_account(session, 1, 5)
        session.delete.assert_awaited_once_with(account)
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestAdminDesignateAgent:
    @pytest.mark.asyncio
    async def test_switches_agent_clearing_previous(self) -> None:
        session = _session()
        current_agent = SimpleNamespace(id=1, is_agent=True)
        target = SimpleNamespace(id=2, is_agent=False)
        session.get = AsyncMock(return_value=target)
        session.scalar = AsyncMock(return_value=current_agent)
        session.refresh = AsyncMock()

        result = await svc.admin_designate_agent(session, account_id=2)

        assert result is target
        assert current_agent.is_agent is False
        assert target.is_agent is True
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_designate_missing_account_404(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await svc.admin_designate_agent(session, account_id=99)


@pytest.mark.unit
class TestAdminClearAgent:
    @pytest.mark.asyncio
    async def test_clears_agent_flag(self) -> None:
        """解绑后 is_agent 置 False 并提交（agent 恢复无关联账户态）。"""
        session = _session()
        account = SimpleNamespace(id=2, is_agent=True)
        session.get = AsyncMock(return_value=account)

        result = await svc.admin_clear_agent(session, 2)

        assert result is account
        assert account.is_agent is False
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_agent_account_rejected_400(self) -> None:
        session = _session()
        account = SimpleNamespace(id=2, is_agent=False)
        session.get = AsyncMock(return_value=account)

        with pytest.raises(BadRequestError, match="不是 agent"):
            await svc.admin_clear_agent(session, 2)
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_account_404(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await svc.admin_clear_agent(session, 99)

    @pytest.mark.asyncio
    async def test_set_enabled(self) -> None:
        session = _session()
        account = SimpleNamespace(id=2, is_enabled=True)
        session.get = AsyncMock(return_value=account)
        session.refresh = AsyncMock()

        await svc.admin_set_enabled(session, 2, False)

        assert account.is_enabled is False
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestForbiddenErrorAvailability:
    def test_forbidden_error_is_importable_app_error(self) -> None:
        """403 语义由 core 异常承载（人工操作 agent 账户拦截）。"""
        assert ForbiddenError().status_code == 403
