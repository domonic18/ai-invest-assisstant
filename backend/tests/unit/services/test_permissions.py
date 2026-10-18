"""权限解析与功能模块门控契约测试。"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.constants.features import FEATURE_KEYS
from app.core.exceptions import ForbiddenError
from app.dependencies import require_feature
from app.services.permissions import build_user_response, resolve_permissions


def _group(permissions: list[str], is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        name="测试组", is_active=is_active, permissions=list(permissions)
    )


def _full_user(**overrides) -> SimpleNamespace:
    payload = {
        "id": 1,
        "username": "u",
        "email": "u@example.com",
        "role": "user",
        "is_active": True,
        "status": "approved",
        "application_note": None,
        "reject_reason": None,
        "last_login_at": None,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "group": None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


@pytest.mark.unit
class TestResolvePermissions:
    @pytest.mark.asyncio
    async def test_admin_gets_all_features(self) -> None:
        user = _full_user(role="admin")
        assert await resolve_permissions(user) == set(FEATURE_KEYS)

    @pytest.mark.asyncio
    async def test_grouped_user_gets_group_permissions(self) -> None:
        user = _full_user(group=_group(["kb", "news"]))
        assert await resolve_permissions(user) == {"kb", "news"}

    @pytest.mark.asyncio
    async def test_ungrouped_user_restricted(self) -> None:
        assert await resolve_permissions(_full_user()) == set()

    @pytest.mark.asyncio
    async def test_inactive_group_restricted(self) -> None:
        user = _full_user(group=_group(["kb"], is_active=False))
        assert await resolve_permissions(user) == set()

    @pytest.mark.asyncio
    async def test_stub_without_group_attr_treated_ungrouped(self) -> None:
        user = SimpleNamespace(role="user")
        assert await resolve_permissions(user) == set()


@pytest.mark.unit
class TestRequireFeature:
    @pytest.mark.asyncio
    async def test_allowed_passes_user_through(self) -> None:
        user = _full_user(group=_group(["kb"]))
        assert await require_feature("kb")(user) is user

    @pytest.mark.asyncio
    async def test_denied_raises_forbidden(self) -> None:
        user = _full_user(group=_group([]))
        with pytest.raises(ForbiddenError) as exc:
            await require_feature("kb")(user)
        assert "未开通" in str(exc.value)

    @pytest.mark.asyncio
    async def test_admin_always_passes(self) -> None:
        user = _full_user(role="admin")
        assert await require_feature("kb")(user) is user


@pytest.mark.unit
class TestBuildUserResponse:
    @pytest.mark.asyncio
    async def test_grouped_user_payload(self) -> None:
        user = _full_user(group=_group(["news", "kb"]))
        resp = await build_user_response(user)
        assert resp.permissions == ["kb", "news"]
        assert resp.group_name == "测试组"

    @pytest.mark.asyncio
    async def test_admin_payload_full_permissions(self) -> None:
        resp = await build_user_response(_full_user(role="admin"))
        assert resp.permissions == sorted(FEATURE_KEYS)
        assert resp.group_name is None

    @pytest.mark.asyncio
    async def test_ungrouped_payload_empty_permissions(self) -> None:
        resp = await build_user_response(_full_user())
        assert resp.permissions == []
        assert resp.group_name is None
