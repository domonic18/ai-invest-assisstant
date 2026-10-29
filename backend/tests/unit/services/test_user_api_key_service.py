"""用户 API Key 服务测试（签发格式/校验分支/节流写回/幂等吊销）。"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.clock import utc_now
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.user import api_key_service as svc

pytestmark = pytest.mark.unit


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock()
    session.scalar = AsyncMock()
    session.execute = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


def _user(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": 7,
        "username": "alice",
        "is_active": True,
        "status": "approved",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _row(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": 11,
        "user_id": 7,
        "name": "飞书助手",
        "key_prefix": "inv_0a1b2c3d",
        "key_hash": "hash",
        "scopes": ["market:read", "kb:read"],
        "expires_at": None,
        "revoked_at": None,
        "last_used_at": None,
        "created_at": utc_now(),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_generate_api_key_format_and_hash_stability():
    token, prefix = svc.generate_api_key()

    assert token.startswith("inv_")
    assert prefix == token[: len(prefix)]
    assert len(prefix) == len("inv_") + 8
    assert token[len(prefix)] == "_"
    assert svc.hash_api_key(token) == svc.hash_api_key(token)
    assert svc.hash_api_key(token) != svc.hash_api_key(token + "x")
    assert len(svc.hash_api_key(token)) == 64


async def test_create_key_persists_hash_and_returns_plaintext_once():
    session = _session()

    async def _refresh(row: object) -> None:
        # 模拟 DB 回填自增主键与默认时间戳
        row.id = 11
        row.created_at = utc_now()

    session.refresh.side_effect = _refresh
    session.get.return_value = _user()
    service = svc.ApiKeyService(session)

    issued = await service.create_key(
        user_id=7,
        name="飞书助手",
        scopes=["kb:read", "market:read", "kb:read"],
    )

    row = session.add.call_args.args[0]
    assert row.key_hash == svc.hash_api_key(issued.token)
    assert issued.token not in row.key_hash
    assert row.scopes == ["kb:read", "market:read"]
    assert issued.scopes == ["kb:read", "market:read"]
    assert issued.username == "alice"
    assert issued.key_prefix == row.key_prefix
    session.commit.assert_awaited_once()


async def test_create_key_rejects_missing_user():
    session = _session()
    session.get.return_value = None
    service = svc.ApiKeyService(session)

    with pytest.raises(NotFoundError):
        await service.create_key(user_id=99, name="x", scopes=["kb:read"])
    session.add.assert_not_called()


async def test_create_key_validates_expiry():
    session = _session()
    session.get.return_value = _user()
    service = svc.ApiKeyService(session)

    with pytest.raises(BadRequestError):
        await service.create_key(
            user_id=7,
            name="x",
            scopes=["kb:read"],
            expires_at=utc_now() - timedelta(days=1),
        )
    with pytest.raises(BadRequestError):
        await service.create_key(
            user_id=7,
            name="x",
            scopes=["kb:read"],
            expires_at=utc_now().replace(tzinfo=None),
        )
    session.add.assert_not_called()


async def test_revoke_key_is_idempotent():
    session = _session()
    session.get.return_value = _row()
    service = svc.ApiKeyService(session)

    await service.revoke_key(11)
    assert session.get.return_value.revoked_at is not None
    session.commit.assert_awaited_once()

    session.commit.reset_mock()
    await service.revoke_key(11)
    session.commit.assert_not_awaited()


async def test_revoke_key_missing_raises():
    session = _session()
    session.get.return_value = None
    service = svc.ApiKeyService(session)

    with pytest.raises(NotFoundError):
        await service.revoke_key(404)


def _session_ctx(session: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def test_verify_api_key_success_sets_claims():
    session = _session()
    session.scalar.return_value = _row()
    session.get.return_value = _user()

    with patch.object(svc, "AsyncSessionLocal", return_value=_session_ctx(session)):
        token = "inv_0a1b2c3d_secret"
        access = await svc.verify_api_key(token)

    assert access is not None
    assert access.client_id == "user:7"
    assert access.subject == "7"
    assert access.scopes == ["market:read", "kb:read"]
    assert access.claims["user_id"] == 7
    assert access.claims["api_key_id"] == 11
    assert access.claims["username"] == "alice"
    session.commit.assert_awaited_once()  # last_used_at 首次写回


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: row.__setattr__("revoked_at", utc_now()),
        lambda row: row.__setattr__("expires_at", utc_now() - timedelta(minutes=1)),
    ],
)
async def test_verify_api_key_rejects_revoked_or_expired(mutate):
    row = _row()
    mutate(row)
    session = _session()
    session.scalar.return_value = row
    session.get.return_value = _user()

    with patch.object(svc, "AsyncSessionLocal", return_value=_session_ctx(session)):
        assert await svc.verify_api_key("inv_0a1b2c3d_secret") is None
    session.commit.assert_not_awaited()


async def test_verify_api_key_rejects_bad_user_state():
    session = _session()
    session.scalar.return_value = _row()
    session.get.return_value = _user(status="pending")

    with patch.object(svc, "AsyncSessionLocal", return_value=_session_ctx(session)):
        assert await svc.verify_api_key("inv_0a1b2c3d_secret") is None


async def test_verify_api_key_rejects_foreign_prefix_without_query():
    with patch.object(svc, "AsyncSessionLocal") as session_local:
        assert await svc.verify_api_key("sk-other") is None
    session_local.assert_not_called()


async def test_verify_api_key_skips_touch_within_throttle():
    session = _session()
    session.scalar.return_value = _row(last_used_at=utc_now())
    session.get.return_value = _user()

    with patch.object(svc, "AsyncSessionLocal", return_value=_session_ctx(session)):
        assert await svc.verify_api_key("inv_0a1b2c3d_secret") is not None
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_touch_failure_does_not_break_verification():
    session = _session()
    session.scalar.return_value = _row()
    session.get.return_value = _user()
    session.execute.side_effect = RuntimeError("db down")

    with patch.object(svc, "AsyncSessionLocal", return_value=_session_ctx(session)):
        access = await svc.verify_api_key("inv_0a1b2c3d_secret")

    assert access is not None
    session.rollback.assert_awaited_once()
