"""用量查询服务单测：配额视图口径 + BYOK 误配回归 + 北京时间日分桶口径。"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.account_quota import (
    SystemSetting,
    UserAiQuota,
    UserLlmConfig,
    UserTokenUsage,
)
from app.models.user import User
from app.services.quota import usage_query_service
from app.services.quota.constants import OUTLET_SYSTEM
from app.services.quota.usage_query_service import cn_bucket_day

pytestmark = pytest.mark.unit


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                UserAiQuota.__table__,
                UserTokenUsage.__table__,
                UserLlmConfig.__table__,
                SystemSetting.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _add_user(session: AsyncSession, **kwargs: object) -> User:
    username = kwargs.pop("username", "u")
    user = User(
        username=username,
        email=kwargs.pop("email", f"{username}@x.com"),
        password_hash="x",
        role=kwargs.pop("role", "user"),
    )
    for key, value in kwargs.items():
        setattr(user, key, value)
    session.add(user)
    await session.flush()
    return user


async def _add_usage(
    session: AsyncSession, user_id: int | None, total: int, *, outlet: str = OUTLET_SYSTEM
) -> None:
    session.add(
        UserTokenUsage(
            user_id=user_id,
            feature="assistant",
            model_name="m",
            provider="openai",
            outlet=outlet,
            prompt_tokens=total // 2,
            completion_tokens=total - total // 2,
            total_tokens=total,
            estimated=False,
        )
    )
    await session.flush()


async def test_quota_view_no_row_means_zero(session: AsyncSession) -> None:
    user = await _add_user(session)
    view = await usage_query_service.get_quota_view(session, user)
    assert (view["total_tokens"], view["used_tokens"], view["remaining_tokens"]) == (0, 0, 0)
    assert view["unlimited"] is False


async def test_quota_view_null_total_is_unlimited(session: AsyncSession) -> None:
    user = await _add_user(session)
    session.add(UserAiQuota(user_id=user.id, total_tokens=None))
    await session.flush()
    view = await usage_query_service.get_quota_view(session, user)
    assert view["unlimited"] is True
    assert view["remaining_tokens"] is None


async def test_quota_view_admin_exempt_is_unlimited(session: AsyncSession) -> None:
    user = await _add_user(session, role="admin")
    session.add(UserAiQuota(user_id=user.id, total_tokens=100))
    session.add(SystemSetting(key="quota.admin_exempt", value=True))
    await session.flush()
    view = await usage_query_service.get_quota_view(session, user)
    assert view["unlimited"] is True


async def test_quota_view_subtracts_system_outlet_only(session: AsyncSession) -> None:
    user = await _add_user(session)
    session.add(UserAiQuota(user_id=user.id, total_tokens=1000))
    await _add_usage(session, user.id, 200)
    await _add_usage(session, user.id, 100, outlet="byok")
    await session.flush()
    view = await usage_query_service.get_quota_view(session, user)
    assert view["used_tokens"] == 200
    assert view["remaining_tokens"] == 800


async def test_quota_view_byok_flag_matches_user_id_not_pk(session: AsyncSession) -> None:
    """回归：BYOK 行按 user_id 命中，而非主键 id 误配他人配置。"""
    user_a = await _add_user(session, username="a")
    user_b = await _add_user(session, username="b")
    session.add(
        UserLlmConfig(
            user_id=user_a.id,
            protocol="openai",
            base_url="https://api.x.com",
            model_name="m",
            api_key_encrypted="enc",
            api_key_masked="sk-***",
        )
    )
    await session.flush()
    view_b = await usage_query_service.get_quota_view(session, user_b)
    assert view_b["byok_enabled"] is False
    view_a = await usage_query_service.get_quota_view(session, user_a)
    assert view_a["byok_enabled"] is True


async def test_list_usage_items_and_by_feature(session: AsyncSession) -> None:
    user = await _add_user(session)
    await _add_usage(session, user.id, 200)
    await _add_usage(session, user.id, 50)
    await session.flush()
    result = await usage_query_service.list_usage(session, user.id)
    assert len(result["items"]) == 2
    assert result["by_feature"] == {"assistant": 250}
    # 新在前
    assert result["items"][0]["total_tokens"] == 50


def test_cn_bucket_day_boundary() -> None:
    """UTC 16:00 = 北京次日 00:00；15:59 仍属当日——SQL AT TIME ZONE 同口径。"""
    assert cn_bucket_day(datetime(2026, 9, 13, 16, 0, tzinfo=UTC)).isoformat() == "2026-09-14"
    assert cn_bucket_day(datetime(2026, 9, 13, 15, 59, tzinfo=UTC)).isoformat() == "2026-09-13"
