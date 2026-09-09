"""代理服务器配置服务契约测试（加密落库、脱敏响应与连通性测试）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.exceptions import BadRequestError
from app.models.proxy_config import ProxyConfig
from app.schemas.proxy_config import ProxyConfigCreate, ProxyConfigUpdate
from app.services.admin.proxy_config_service import (
    ProxyConfigNotFoundError,
    ProxyConfigService,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "a-32-byte-secret-key-for-tests!")


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[ProxyConfig.__table__]
        )
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as db:
        yield db
    await engine.dispose()


async def test_create_config_encrypts_password(session: AsyncSession) -> None:
    service = ProxyConfigService(session)
    created = await service.create_config(
        ProxyConfigCreate(
            name="clash-frp",
            protocol="http",
            host="175.27.167.123",
            port=17890,
            username="collector",
            password="s3cret-pass",
        )
    )
    assert created.id is not None
    assert created.password_masked is not None
    assert created.password_masked != "s3cret-pass"
    stored = await service.repo.get(created.id)
    assert stored is not None
    assert stored.password_encrypted != "s3cret-pass"


async def test_create_without_password(session: AsyncSession) -> None:
    service = ProxyConfigService(session)
    created = await service.create_config(
        ProxyConfigCreate(name="local", host="127.0.0.1", port=7890)
    )
    assert created.password_masked is None
    assert created.protocol == "http"


async def test_create_duplicate_name_rejected(session: AsyncSession) -> None:
    service = ProxyConfigService(session)
    await service.create_config(ProxyConfigCreate(name="dup", host="h1", port=1))
    with pytest.raises(BadRequestError):
        await service.create_config(ProxyConfigCreate(name="dup", host="h2", port=2))


async def test_update_without_password_keeps_cipher(
    session: AsyncSession,
) -> None:
    service = ProxyConfigService(session)
    created = await service.create_config(
        ProxyConfigCreate(
            name="orig", host="h", port=8080, username="u", password="orig-pass"
        )
    )
    updated = await service.update_config(
        created.id, ProxyConfigUpdate(name="renamed")
    )
    assert updated.name == "renamed"
    assert updated.password_masked == created.password_masked


async def test_update_password_reencrypts(session: AsyncSession) -> None:
    service = ProxyConfigService(session)
    created = await service.create_config(
        ProxyConfigCreate(name="p", host="h", port=8080, password="old-secret-pass-1")
    )
    updated = await service.update_config(
        created.id, ProxyConfigUpdate(password="new-secret-pass-2")
    )
    assert updated.password_masked is not None
    assert updated.password_masked != created.password_masked


async def test_update_rename_conflict_rejected(session: AsyncSession) -> None:
    service = ProxyConfigService(session)
    first = await service.create_config(ProxyConfigCreate(name="a", host="h", port=1))
    await service.create_config(ProxyConfigCreate(name="b", host="h", port=2))
    with pytest.raises(BadRequestError):
        await service.update_config(first.id, ProxyConfigUpdate(name="b"))


async def test_get_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(ProxyConfigNotFoundError):
        await ProxyConfigService(session).get_config(999)


async def test_delete_config(session: AsyncSession) -> None:
    service = ProxyConfigService(session)
    created = await service.create_config(ProxyConfigCreate(name="x", host="h", port=1))
    await service.delete_config(created.id)
    with pytest.raises(ProxyConfigNotFoundError):
        await service.get_config(created.id)


@patch("app.services.admin.proxy_config_service.httpx.AsyncClient")
async def test_test_config_success(
    mock_client_cls: MagicMock, session: AsyncSession
) -> None:
    service = ProxyConfigService(session)
    created = await service.create_config(
        ProxyConfigCreate(
            name="ok",
            host="h",
            port=8080,
            username="u",
            password="p@ss",
        )
    )
    mock_client = AsyncMock()
    mock_client.get.return_value = MagicMock(status_code=204)
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    result = await service.test_config(created.id)

    assert result.ok is True
    assert result.status_code == 204
    assert result.error is None
    # 代理 URL 组装含编码后的凭据
    _, kwargs = mock_client_cls.call_args
    assert kwargs["proxy"] == "http://u:p%40ss@h:8080"


@patch("app.services.admin.proxy_config_service.httpx.AsyncClient")
async def test_test_config_connection_error(
    mock_client_cls: MagicMock, session: AsyncSession
) -> None:
    service = ProxyConfigService(session)
    created = await service.create_config(
        ProxyConfigCreate(name="bad", host="dead.host", port=1)
    )
    mock_client = AsyncMock()
    mock_client.get.side_effect = OSError("connection refused")
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    mock_client_cls.return_value.__aexit__.return_value = False

    result = await service.test_config(created.id)

    assert result.ok is False
    assert "connection refused" in (result.error or "")
