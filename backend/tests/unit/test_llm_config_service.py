"""LLM 配置服务契约测试（默认配置唯一性与凭证脱敏）。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.llm_config import LLMConfig
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate
from app.services.admin.llm_config_service import (
    LLMConfigNotConfiguredError,
    LLMConfigService,
    resolve_default_llm,
    resolve_vision_llm,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "a-32-byte-secret-key-for-tests!")


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[LLMConfig.__table__])
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as db:
        yield db
    await engine.dispose()


async def test_create_config(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="OpenAI GPT-4o",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test-api-key-12345",
            model_name="gpt-4o",
        )
    )
    assert created.id is not None
    assert created.name == "OpenAI GPT-4o"
    assert created.api_key_masked.startswith("sk-t")


async def test_default_config_unique(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    first = await service.create_config(
        LLMConfigCreate(
            name="First",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-first",
            model_name="gpt-4o",
            is_default=True,
        )
    )
    assert first.is_default
    second = await service.create_config(
        LLMConfigCreate(
            name="Second",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-second",
            model_name="gpt-4o",
            is_default=True,
        )
    )
    assert second.is_default
    configs = await service.list_configs()
    defaults = [c for c in configs if c.is_default]
    assert len(defaults) == 1
    assert defaults[0].id == second.id


async def test_resolve_default_raises_when_missing(session: AsyncSession) -> None:
    with pytest.raises(LLMConfigNotConfiguredError):
        await resolve_default_llm(session)


async def test_resolve_default_returns_config(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    await service.create_config(
        LLMConfigCreate(
            name="Default",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-default",
            model_name="gpt-4o",
            is_default=True,
        )
    )
    resolved = await resolve_default_llm(session)
    assert resolved.model_name == "gpt-4o"
    assert resolved.api_key == "sk-default"


async def test_delete_reassigns_default(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    first = await service.create_config(
        LLMConfigCreate(
            name="First",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-first",
            model_name="gpt-4o",
            is_default=True,
        )
    )
    second = await service.create_config(
        LLMConfigCreate(
            name="Second",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-second",
            model_name="gpt-4o",
        )
    )
    await service.delete_config(first.id)
    configs = await service.list_configs()
    defaults = [c for c in configs if c.is_default]
    assert len(defaults) == 1
    assert defaults[0].id == second.id


async def test_update_without_api_key_does_not_change_key(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="Original",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-original",
            model_name="gpt-4o",
        )
    )
    updated = await service.update_config(
        created.id,
        LLMConfigUpdate(name="Renamed"),
    )
    assert updated is not None
    assert updated.name == "Renamed"
    assert updated.api_key_masked == created.api_key_masked


async def test_resolve_vision_raises_when_missing(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    await service.create_config(
        LLMConfigCreate(
            name="Text only",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-text",
            model_name="gpt-4o",
            is_default=True,
        )
    )
    with pytest.raises(LLMConfigNotConfiguredError):
        await resolve_vision_llm(session)


async def test_resolve_vision_returns_marked_config(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    await service.create_config(
        LLMConfigCreate(
            name="Text default",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-text",
            model_name="gpt-4o",
            is_default=True,
        )
    )
    await service.create_config(
        LLMConfigCreate(
            name="Vision model",
            provider="zhipu",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="sk-vision",
            model_name="glm-4v-flash",
            extra={"capabilities": {"vision": True}},
        )
    )
    resolved = await resolve_vision_llm(session)
    assert resolved.model_name == "glm-4v-flash"
    assert resolved.api_key == "sk-vision"


async def test_resolve_vision_prefers_default_among_marked(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    await service.create_config(
        LLMConfigCreate(
            name="Vision default",
            provider="zhipu",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="sk-vision-default",
            model_name="glm-4v-plus",
            is_default=True,
            extra={"capabilities": {"vision": True}},
        )
    )
    await service.create_config(
        LLMConfigCreate(
            name="Vision backup",
            provider="zhipu",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="sk-vision-backup",
            model_name="glm-4v-flash",
            extra={"capabilities": {"vision": True}},
        )
    )
    resolved = await resolve_vision_llm(session)
    assert resolved.model_name == "glm-4v-plus"
