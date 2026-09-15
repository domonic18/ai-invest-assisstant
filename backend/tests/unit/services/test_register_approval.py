"""注册审批流单测：申请冲突判定、双拦截、审批动作与审计、惰性过期。"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.clock import utc_now
from app.core.database import Base
from app.core.exceptions import (
    AccountPendingError,
    AccountRejectedError,
    ConflictError,
)
from app.core.security import get_password_hash, verify_password
from app.models.account_quota import AdminAuditLog, SystemSetting, UserAiQuota
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.admin.approval_service import ApprovalService
from app.services.user.register_service import RegisterService
from app.services.user.user_service import UserService

pytestmark = pytest.mark.unit


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[User.__table__, UserAiQuota.__table__, AdminAuditLog.__table__, SystemSetting.__table__],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


def _request(username: str = "alice", email: str = "a@x.com", note: str | None = None) -> RegisterRequest:
    return RegisterRequest(
        username=username, email=email, password="secret123", application_note=note
    )


async def _submit(session: AsyncSession, data: RegisterRequest) -> None:
    with patch("app.core.register_throttle.check_ip_allowed", AsyncMock(return_value=True)):
        await RegisterService(session).submit(data, "1.2.3.4")


async def test_submit_creates_pending(session: AsyncSession) -> None:
    await _submit(session, _request(note="想做研究"))
    user = await RegisterService(session)._find_conflict("alice", "a@x.com")
    assert user is not None
    assert user.status == "pending"
    assert user.application_note == "想做研究"


async def test_pending_conflict_rejected_with_409(session: AsyncSession) -> None:
    await _submit(session, _request())
    with pytest.raises(ConflictError, match="在审"):
        await _submit(session, _request(username="alice", email="other@x.com"))


async def test_rejected_resubmission_resets_to_pending(session: AsyncSession) -> None:
    await _submit(session, _request())
    user = await RegisterService(session)._find_conflict("alice", "a@x.com")
    assert user is not None
    user.status = "rejected"
    user.reject_reason = "资料不足"
    await session.commit()

    await _submit(session, _request(note="补充说明"))
    refreshed = await RegisterService(session)._find_conflict("alice", "a@x.com")
    assert refreshed is not None
    assert refreshed.status == "pending"
    assert refreshed.reject_reason is None
    assert verify_password("secret123", refreshed.password_hash)


async def test_approved_conflict(session: AsyncSession) -> None:
    await _submit(session, _request())
    user = await RegisterService(session)._find_conflict("alice", "a@x.com")
    assert user is not None
    user.status = "approved"
    await session.commit()
    with pytest.raises(ConflictError, match="已注册"):
        await _submit(session, _request(email="different@x.com"))


async def test_login_blocked_by_status(session: AsyncSession) -> None:
    await _submit(session, _request())
    service = UserService(session)
    with (
        patch("app.core.login_throttle.locked_seconds", AsyncMock(return_value=0)),
        patch("app.core.login_throttle.reset_failures", AsyncMock()),
    ):
        with pytest.raises(AccountPendingError):
            await service.attempt_login("alice", "secret123", "1.2.3.4")

        user = await service.get_user_by_username("alice")
        assert user is not None
        user.status = "rejected"
        user.reject_reason = "不符合定位"
        await session.commit()
        with pytest.raises(AccountRejectedError) as exc_info:
            await service.attempt_login("alice", "secret123", "1.2.3.4")
        assert "不符合定位" in exc_info.value.message


async def test_lazy_expiry_cleans_old_pending(session: AsyncSession) -> None:
    await _submit(session, _request(username="old", email="old@x.com"))
    user = await RegisterService(session)._find_conflict("old", "old@x.com")
    assert user is not None
    user.created_at = utc_now() - timedelta(days=31)
    await session.commit()
    await _submit(session, _request(username="fresh", email="fresh@x.com"))

    assert await RegisterService(session)._find_conflict("old", "old@x.com") is None
    assert await RegisterService(session)._find_conflict("fresh", "fresh@x.com") is not None


async def _admin(session: AsyncSession) -> User:
    admin = User(
        username="admin",
        email="admin@x.com",
        password_hash=get_password_hash("secret123"),
        role="admin",
        status="approved",
    )
    session.add(admin)
    await session.flush()
    return admin


async def test_approve_grants_default_quota_and_audits(session: AsyncSession) -> None:
    await _submit(session, _request())
    user = await RegisterService(session)._find_conflict("alice", "a@x.com")
    assert user is not None
    admin = await _admin(session)

    await ApprovalService(session).approve(admin, user.id)

    refreshed = await session.get(User, user.id)
    assert refreshed is not None
    assert refreshed.status == "approved"
    assert refreshed.reviewed_by == admin.id
    quota = await session.get(UserAiQuota, user.id)
    assert quota is not None
    assert quota.total_tokens == 100000  # system_setting 缺省（行缺失回退默认）
    audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert len(audits) == 1
    assert audits[0].action == "register.approve"
    assert audits[0].detail == {"initialQuotaTokens": 100000}


async def test_reject_requires_reason_and_audits(session: AsyncSession) -> None:
    from app.core.exceptions import BadRequestError

    await _submit(session, _request())
    user = await RegisterService(session)._find_conflict("alice", "a@x.com")
    assert user is not None
    admin = await _admin(session)
    service = ApprovalService(session)

    with pytest.raises(BadRequestError):
        await service.reject(admin, user.id, "  ")
    await service.reject(admin, user.id, "资料不足")

    refreshed = await session.get(User, user.id)
    assert refreshed is not None
    assert refreshed.status == "rejected"
    assert refreshed.reject_reason == "资料不足"


async def test_adjust_quota_reset_and_audit(session: AsyncSession) -> None:
    from sqlalchemy import select

    await _submit(session, _request())
    user = await RegisterService(session)._find_conflict("alice", "a@x.com")
    assert user is not None
    admin = await _admin(session)
    service = ApprovalService(session)
    await service.approve(admin, user.id, 50000)

    invalidated: list[int] = []
    with patch(
        "app.services.admin.approval_service.quota_service.invalidate",
        side_effect=lambda uid: invalidated.append(uid),
    ):
        quota = await service.adjust_quota(admin, user.id, action="adjust", delta_tokens=20000)
        assert quota.total_tokens == 70000
        await service.adjust_quota(admin, user.id, action="reset")
    refreshed = await session.get(UserAiQuota, user.id)
    assert refreshed is not None
    assert refreshed.total_tokens == 100000
    assert invalidated == [user.id, user.id]
    adjust_audits = (
        await session.execute(select(AdminAuditLog).where(AdminAuditLog.action == "quota.adjust"))
    ).scalars().all()
    assert len(adjust_audits) == 2


async def test_apply_settings_upserts_audits_and_invalidates_on_exempt(
    session: AsyncSession,
) -> None:
    """设置 upsert + 审计记录新旧值；仅豁免开关变更触发全局镜像失效；空更新跳过。"""
    admin = await _admin(session)
    service = ApprovalService(session)

    invalidated: list[bool] = []
    with patch(
        "app.services.admin.approval_service.quota_service.invalidate_all",
        side_effect=lambda: invalidated.append(True),
    ):
        await service.apply_settings(admin, {"account.pending_expire_days": 15})
        await service.apply_settings(admin, {"quota.admin_exempt": False})
        await service.apply_settings(admin, {})

    rows = {
        row.key: row.value
        for row in (await session.execute(select(SystemSetting))).scalars().all()
    }
    assert rows["account.pending_expire_days"] == 15
    assert rows["quota.admin_exempt"] is False
    audits = (
        await session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "account_setting.update"
            )
        )
    ).scalars().all()
    assert len(audits) == 2  # 空更新不审计
    assert audits[0].detail == {
        "account.pending_expire_days": {"oldValue": 30, "newValue": 15}
    }
    assert invalidated == [True]  # 仅豁免开关变更触发全局失效
