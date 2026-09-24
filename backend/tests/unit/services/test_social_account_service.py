"""追踪账号服务单测：sec_uid 四形态解析、CRUD 校验与审计。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants.social import SOCIAL_MIN_POLL_INTERVAL_MINUTES
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.services.social import account_service
from app.services.social.account_service import (
    create_account,
    delete_account,
    extract_sec_uid,
    resolve_sec_uid,
    update_account,
)

_SEC_UID = "MS4wLjABAAAA" + "a" * 20


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.unit
class TestExtractSecUid:
    def test_bare_sec_uid(self) -> None:
        assert extract_sec_uid(_SEC_UID) == _SEC_UID

    def test_profile_url(self) -> None:
        url = f"https://www.douyin.com/user/{_SEC_UID}?fid=1234"
        assert extract_sec_uid(url) == _SEC_UID

    def test_share_text(self) -> None:
        text = f"7.20 复制打开抖音看看 {_SEC_UID} 的作品"
        assert extract_sec_uid(text) == _SEC_UID

    def test_no_match_returns_none(self) -> None:
        assert extract_sec_uid("https://v.douyin.com/iRNBho6u/") is None


@pytest.mark.unit
class TestResolveSecUid:
    async def test_short_link_expanded(self) -> None:
        from unittest.mock import patch

        with patch.object(
            account_service,
            "_expand_short_link",
            return_value=f"https://www.douyin.com/user/{_SEC_UID}",
        ):
            assert await resolve_sec_uid("https://v.douyin.com/iRNBho6u/") == _SEC_UID

    async def test_unparseable_raises(self) -> None:
        from unittest.mock import patch

        with patch.object(account_service, "_expand_short_link", return_value=""):
            with pytest.raises(BadRequestError):
                await resolve_sec_uid("https://v.douyin.com/xyz/")


@pytest.mark.unit
class TestCreateAccount:
    async def test_duplicate_raises_conflict(self) -> None:
        session = _session()
        existing = MagicMock()
        existing.alias = "已存在"
        with patch.object(
            account_service.account_repository,
            "get_by_sec_uid",
            AsyncMock(return_value=existing),
        ):
            with pytest.raises(ConflictError):
                await create_account(
                    session,
                    platform="douyin",
                    sec_uid_or_url=_SEC_UID,
                    alias="新名字",
                    category="finance_kol",
                    poll_interval_minutes=60,
                )

    async def test_invalid_category_raises(self) -> None:
        with pytest.raises(BadRequestError):
            await create_account(
                _session(),
                platform="douyin",
                sec_uid_or_url=_SEC_UID,
                alias="名",
                category="unknown",
                poll_interval_minutes=60,
            )

    async def test_interval_below_floor_raises(self) -> None:
        with pytest.raises(BadRequestError):
            await create_account(
                _session(),
                platform="douyin",
                sec_uid_or_url=_SEC_UID,
                alias="名",
                category="finance_kol",
                poll_interval_minutes=SOCIAL_MIN_POLL_INTERVAL_MINUTES - 1,
            )

    async def test_unknown_platform_raises(self) -> None:
        with pytest.raises(BadRequestError):
            await create_account(
                _session(),
                platform="weibo",
                sec_uid_or_url=_SEC_UID,
                alias="名",
                category="finance_kol",
                poll_interval_minutes=60,
            )


@pytest.mark.unit
class TestUpdateAccount:
    async def test_missing_account_raises(self) -> None:
        from unittest.mock import AsyncMock, patch

        with patch.object(
            account_service.account_repository, "get", AsyncMock(return_value=None)
        ):
            with pytest.raises(NotFoundError):
                await update_account(_session(), 1, alias="新名")

    async def test_bad_category_raises(self) -> None:
        from unittest.mock import AsyncMock, patch

        account = {"id": 1}
        with patch.object(
            account_service.account_repository, "get", AsyncMock(return_value=account)
        ):
            with pytest.raises(BadRequestError):
                await update_account(_session(), 1, category="wrong")

    async def test_bad_interval_raises(self) -> None:
        from unittest.mock import AsyncMock, patch

        with patch.object(
            account_service.account_repository, "get", AsyncMock(return_value={"id": 1})
        ):
            with pytest.raises(BadRequestError):
                await update_account(_session(), 1, poll_interval_minutes=1)


@pytest.mark.unit
class TestAccountAudit:
    async def test_create_writes_audit(self) -> None:
        session = _session()
        with (
            patch.object(
                account_service.account_repository,
                "get_by_sec_uid",
                AsyncMock(return_value=None),
            ),
            patch.object(account_service, "record_audit", AsyncMock()) as mock_audit,
        ):
            await create_account(
                session,
                platform="douyin",
                sec_uid_or_url=_SEC_UID,
                alias="财经大V",
                category="finance_kol",
                poll_interval_minutes=60,
                actor_id=1,
                ip="1.2.3.4",
            )
        kwargs = mock_audit.await_args.kwargs
        assert kwargs["actor_id"] == 1
        assert kwargs["action"] == "social.account.create"
        assert kwargs["ip"] == "1.2.3.4"
        assert kwargs["detail"] == {
            "alias": "财经大V",
            "category": "finance_kol",
            "platform": "douyin",
        }

    async def test_create_without_actor_skips_audit(self) -> None:
        session = _session()
        with (
            patch.object(
                account_service.account_repository,
                "get_by_sec_uid",
                AsyncMock(return_value=None),
            ),
            patch.object(account_service, "record_audit", AsyncMock()) as mock_audit,
        ):
            await create_account(
                session,
                platform="douyin",
                sec_uid_or_url=_SEC_UID,
                alias="财经大V",
                category="finance_kol",
                poll_interval_minutes=60,
            )
        mock_audit.assert_not_called()

    async def test_update_writes_audit_with_field_list(self) -> None:
        session = _session()
        account = SimpleNamespace(
            alias="旧名",
            category="finance_kol",
            poll_interval_minutes=60,
            is_active=True,
            remark=None,
        )
        with (
            patch.object(
                account_service.account_repository,
                "get",
                AsyncMock(return_value=account),
            ),
            patch.object(account_service, "record_audit", AsyncMock()) as mock_audit,
        ):
            await update_account(
                session, 3, actor_id=1, ip="1.2.3.4", alias="新名", is_active=False
            )
        kwargs = mock_audit.await_args.kwargs
        assert kwargs["action"] == "social.account.update"
        assert kwargs["detail"]["accountId"] == 3
        assert kwargs["detail"]["fields"] == ["alias", "is_active"]
        assert account.alias == "新名"
        assert account.is_active is False

    async def test_delete_writes_audit(self) -> None:
        session = _session()
        account = SimpleNamespace(id=5)
        with (
            patch.object(
                account_service.account_repository,
                "get",
                AsyncMock(return_value=account),
            ),
            patch.object(account_service, "record_audit", AsyncMock()) as mock_audit,
        ):
            await delete_account(session, 5, actor_id=1, ip="1.2.3.4")
        kwargs = mock_audit.await_args.kwargs
        assert kwargs["action"] == "social.account.delete"
        assert kwargs["detail"] == {"accountId": 5}
        session.delete.assert_called_once_with(account)


@pytest.mark.unit
class TestTriggerBackfill:
    async def test_dispatches_backfill_with_audit(self) -> None:
        session = _session()
        fake_log = SimpleNamespace(id=42, celery_task_id="celery-abc")
        with (
            patch.object(
                account_service.account_repository,
                "get",
                AsyncMock(return_value=SimpleNamespace(id=3)),
            ),
            patch.object(account_service, "record_audit", AsyncMock()) as mock_audit,
            patch(
                "collector.runtime.dispatcher.dispatch_collector_task",
                AsyncMock(return_value=fake_log),
            ) as mock_dispatch,
        ):
            log = await account_service.trigger_backfill(
                session, 3, actor_id=1, ip="1.2.3.4"
            )
        assert log is fake_log
        assert mock_dispatch.await_args.args == (session,)
        assert mock_dispatch.await_args.kwargs["task_name"] == "social-video"
        assert mock_dispatch.await_args.kwargs["params"] == {
            "account_id": 3,
            "backfill": True,
            "preferred_source": "douyin",
        }
        audit_kwargs = mock_audit.await_args.kwargs
        assert audit_kwargs["action"] == "social.account.backfill"
        assert audit_kwargs["detail"] == {"accountId": 3}
        assert audit_kwargs["actor_id"] == 1
        assert audit_kwargs["ip"] == "1.2.3.4"

    async def test_missing_account_raises(self) -> None:
        session = _session()
        with (
            patch.object(
                account_service.account_repository,
                "get",
                AsyncMock(return_value=None),
            ),
            patch.object(account_service, "record_audit", AsyncMock()) as mock_audit,
        ):
            with pytest.raises(NotFoundError):
                await account_service.trigger_backfill(session, 99, actor_id=1)
        mock_audit.assert_not_called()
