"""采集渠道绑定代理的解析契约测试（resolve_collector_channel 的 proxy_url 三态）。"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.collector_channel_config import CollectorChannelConfig
from app.models.collector_channel_data_type import CollectorChannelDataType
from app.models.proxy_config import ProxyConfig
from app.schemas.collector_channel_config import (
    CollectorChannelConfigCreate,
    CollectorChannelConfigUpdate,
)
from app.services.admin.collector_channels import (
    CollectorChannelConfigService,
    resolve_collector_channel,
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
            Base.metadata.create_all,
            tables=[
                ProxyConfig.__table__,
                CollectorChannelConfig.__table__,
                CollectorChannelDataType.__table__,
            ],
        )
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as db:
        yield db
    await engine.dispose()


async def _create_proxy(
    session: AsyncSession, *, name: str = "clash", enabled: bool = True
) -> int:
    from app.utils.crypto import encrypt_token

    session.add(
        ProxyConfig(
            name=name,
            protocol="http",
            host="175.27.167.123",
            port=17890,
            username="collector",
            password_encrypted=encrypt_token("frp-pass"),
            is_enabled=enabled,
        )
    )
    await session.flush()
    row = (
        await session.execute(select(ProxyConfig).where(ProxyConfig.name == name))
    ).scalar_one()
    return row.id


async def test_unbound_channel_has_no_proxy(session: AsyncSession) -> None:
    service = CollectorChannelConfigService(session)
    await service.create_config(
        CollectorChannelConfigCreate(source="yahoo", name="Yahoo")
    )
    resolved = await resolve_collector_channel(session, "yahoo")
    assert resolved is not None
    assert resolved["proxy_url"] is None


async def test_bound_enabled_proxy_resolves_url(session: AsyncSession) -> None:
    proxy_id = await _create_proxy(session)
    service = CollectorChannelConfigService(session)
    created = await service.create_config(
        CollectorChannelConfigCreate(source="yahoo", name="Yahoo", proxy_config_id=proxy_id)
    )
    assert created.proxy_config_id == proxy_id

    resolved = await resolve_collector_channel(session, "yahoo")
    assert resolved is not None
    assert resolved["proxy_url"] == "http://collector:frp-pass@175.27.167.123:17890"


async def test_bound_disabled_proxy_falls_back_to_direct(
    session: AsyncSession,
) -> None:
    proxy_id = await _create_proxy(session, enabled=False)
    service = CollectorChannelConfigService(session)
    await service.create_config(
        CollectorChannelConfigCreate(source="yahoo", name="Yahoo", proxy_config_id=proxy_id)
    )
    resolved = await resolve_collector_channel(session, "yahoo")
    assert resolved is not None
    assert resolved["proxy_url"] is None


async def test_update_can_bind_and_unbind(session: AsyncSession) -> None:
    proxy_id = await _create_proxy(session)
    service = CollectorChannelConfigService(session)
    created = await service.create_config(
        CollectorChannelConfigCreate(source="yahoo", name="Yahoo")
    )

    bound = await service.update_config(
        created.id, CollectorChannelConfigUpdate(proxy_config_id=proxy_id)
    )
    assert bound.proxy_config_id == proxy_id

    unbound = await service.update_config(
        created.id, CollectorChannelConfigUpdate(proxy_config_id=None)
    )
    assert unbound.proxy_config_id is None

    # 未传字段的更新不动绑定
    untouched = await service.update_config(created.id, CollectorChannelConfigUpdate(name="Y!"))
    assert untouched.proxy_config_id is None
