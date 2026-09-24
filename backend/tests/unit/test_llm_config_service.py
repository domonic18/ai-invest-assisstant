"""LLM 配置服务契约测试（默认配置唯一性、凭证脱敏与连通性探测路径）。"""

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.llm_config import LLMConfig
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate
from app.services.admin import llm_config_service as llm_config_service_module
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


def _stub_http(captured: dict[str, Any], *, status: int = 200, body: dict[str, Any] | None = None):
    """替换 httpx.AsyncClient 的桩：捕获请求并返回固定响应。"""

    class _StubClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_StubClient":
            return self

        async def __aexit__(self, *exc: Any) -> None:
            return None

        async def post(self, url: str, headers: Any = None, json: Any = None) -> Any:
            captured["url"] = url
            captured["json"] = json
            return SimpleNamespace(
                status_code=status,
                text="",
                json=lambda: body or {},
            )

    return _StubClient


async def test_embedding_config_probes_embeddings_endpoint_and_reports_dims(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """embedding 条目测试连接走 /embeddings（归一化剥离用户粘贴的端点后缀）并回报维度。"""
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="Zhipu embed",
            provider="custom",
            base_url="https://open.bigmodel.cn/api/paas/v4/embeddings",
            api_key="sk-embed",
            model_name="embedding-3",
            purpose="embedding",
        )
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        llm_config_service_module.httpx,
        "AsyncClient",
        _stub_http(captured, body={"data": [{"index": 0, "embedding": [0.0] * 2048}]}),
    )

    result = await service.test_config_connection(created.id)

    assert result.status == "success"
    assert "2048 维" in result.detail
    assert captured["url"] == "https://open.bigmodel.cn/api/paas/v4/embeddings"
    assert captured["json"] == {"model": "embedding-3", "input": ["ping"]}


async def test_chat_config_normalizes_full_endpoint_suffix(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chat 条目粘贴 …/chat/completions 完整端点时归一化后按根地址拼接。"""
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="Full endpoint",
            provider="custom",
            base_url="https://api.example.com/v1/chat/completions",
            api_key="sk-chat",
            model_name="gpt-test",
            purpose="chat",
        )
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        llm_config_service_module.httpx,
        "AsyncClient",
        _stub_http(captured, body={"choices": []}),
    )

    result = await service.test_config_connection(created.id)

    assert result.status == "success"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"


async def test_embedding_config_missing_vector_marks_failed(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """200 但缺向量字段（如误配到 chat 模型）判失败并回显响应片段。"""
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="Broken embed",
            provider="custom",
            base_url="https://api.example.com/v1",
            api_key="sk-broken",
            model_name="not-an-embedding",
            purpose="embedding",
        )
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        llm_config_service_module.httpx,
        "AsyncClient",
        _stub_http(captured, body={"error": "model not found"}),
    )

    result = await service.test_config_connection(created.id)

    assert result.status == "failed"
    assert "缺少向量字段" in result.detail
