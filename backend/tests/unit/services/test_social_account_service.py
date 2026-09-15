"""追踪账号服务单测：sec_uid 四形态解析与 CRUD 校验。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants.social import SOCIAL_MIN_POLL_INTERVAL_MINUTES
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.services.social import account_service
from app.services.social.account_service import (
    create_account,
    extract_sec_uid,
    resolve_sec_uid,
    update_account,
)

_SEC_UID = "MS4wLjABAAAA" + "a" * 20


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
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
