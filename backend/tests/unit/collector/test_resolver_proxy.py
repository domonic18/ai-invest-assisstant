"""渠道解析注入链的代理测试（resolve_channels_for_task 的 proxy_url 三态）。"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.collector_channel_config import CollectorChannelConfig
from app.models.collector_channel_data_type import CollectorChannelDataType
from app.models.proxy_config import ProxyConfig
from collector.runtime.resolver import resolve_channels_for_task

pytestmark = pytest.mark.unit

_TASK = "global-index"


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


async def _add_channel(
    session: AsyncSession,
    source: str,
    *,
    proxy_id: int | None = None,
) -> int:
    session.add(
        CollectorChannelConfig(
            source=source,
            name=source,
            base_url=None,
            is_enabled=True,
            supported_data_types=[_TASK],
            proxy_config_id=proxy_id,
        )
    )
    await session.flush()
    row = (
        await session.execute(
            select(CollectorChannelConfig).where(CollectorChannelConfig.source == source)
        )
    ).scalar_one()
    session.add(
        CollectorChannelDataType(channel_id=row.id, data_type=_TASK, priority=1)
    )
    await session.flush()
    return row.id


async def _add_proxy(
    session: AsyncSession, *, enabled: bool = True
) -> int:
    from app.utils.crypto import encrypt_token

    session.add(
        ProxyConfig(
            name="clash",
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
        await session.execute(select(ProxyConfig).where(ProxyConfig.name == "clash"))
    ).scalar_one()
    return row.id


async def test_bound_enabled_proxy_injects_url(session: AsyncSession) -> None:
    proxy_id = await _add_proxy(session, enabled=True)
    await _add_channel(session, "yahoo", proxy_id=proxy_id)

    configs = await resolve_channels_for_task(session, _TASK)

    assert [c.source for c in configs] == ["yahoo"]
    assert configs[0].proxy_url == "http://collector:frp-pass@175.27.167.123:17890"


async def test_bound_disabled_proxy_direct_connection(session: AsyncSession) -> None:
    proxy_id = await _add_proxy(session, enabled=False)
    await _add_channel(session, "yahoo", proxy_id=proxy_id)

    configs = await resolve_channels_for_task(session, _TASK)

    assert configs[0].proxy_url is None


async def test_unbound_channel_direct_connection(session: AsyncSession) -> None:
    await _add_channel(session, "yahoo")

    configs = await resolve_channels_for_task(session, _TASK)

    assert configs[0].proxy_url is None
