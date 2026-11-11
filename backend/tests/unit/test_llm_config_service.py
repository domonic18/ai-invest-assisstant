"""LLM 配置服务契约测试（纯注册表：凭证脱敏、连通性探测、by-id 主备解析）。"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.llm_config import LLMConfig
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate
from app.services.admin import llm_config_service as llm_config_service_module
from app.services.admin.llm_config_service import (
    LLMConfigNotConfiguredError,
    LLMConfigNotFoundError,
    LLMConfigService,
    resolve_llm_by_id,
    resolve_vision_llm,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "a-32-byte-secret-key-for-tests!")


@pytest.fixture(autouse=True)
def _hermetic_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """隔离 redis：健康门/冷却查询打桩。

    unit 单测不打外部依赖；且本地 redis 常驻时（CI 无 redis 走 fail-open 不暴露），
    共享连接池跨事件循环复用会炸（RuntimeError: Future attached to a different loop）。
    """
    monkeypatch.setattr(
        "app.services.admin.llm_failover.is_unhealthy",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.admin.llm_config_service.degraded_until",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.admin.llm_config_service.clear_unhealthy",
        AsyncMock(),
    )


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[LLMConfig.__table__])
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as db:
        yield db
    await engine.dispose()


async def _create_chat(session: AsyncSession, name: str, **kw: Any):
    return await LLMConfigService(session).create_config(
        LLMConfigCreate(
            name=name,
            provider="custom",
            base_url="https://api.example.com/v1",
            api_key=f"sk-{name}",
            model_name=f"m-{name}",
            **kw,
        )
    )


async def _deactivate(session: AsyncSession, config_id: int) -> None:
    await LLMConfigService(session).update_config(config_id, LLMConfigUpdate(is_active=False))


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


async def test_list_configs_tolerates_undecryptable_key(session: AsyncSession) -> None:
    """密钥轮换后旧密文不可解密时列表降级展示，不得整页 500。"""
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="Rotated",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-rotated",
            model_name="gpt-4o",
        )
    )
    row = await session.get(LLMConfig, created.id)
    assert row is not None
    row.api_key_encrypted = "not-a-valid-fernet-token"
    await session.commit()

    configs = await service.list_configs()
    assert [c.api_key_masked for c in configs if c.id == created.id] == [
        "[无法解密，请重新录入]"
    ]


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


# ---------- resolve_vision_llm（能力扫描解析） ----------


async def test_resolve_vision_raises_when_missing(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    await service.create_config(
        LLMConfigCreate(
            name="Text only",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-text",
            model_name="gpt-4o",
        )
    )
    with pytest.raises(LLMConfigNotConfiguredError):
        await resolve_vision_llm(session)


async def test_resolve_vision_returns_marked_config(session: AsyncSession) -> None:
    service = LLMConfigService(session)
    await service.create_config(
        LLMConfigCreate(
            name="Text only",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-text",
            model_name="gpt-4o",
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


async def test_resolve_vision_picks_first_marked_by_id(session: AsyncSession) -> None:
    """多个标记视觉能力的条目：按注册表 id 序取首个（无默认语义）。"""
    service = LLMConfigService(session)
    await service.create_config(
        LLMConfigCreate(
            name="Vision first",
            provider="zhipu",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="sk-vision-first",
            model_name="glm-4v-plus",
            extra={"capabilities": {"vision": True}},
        )
    )
    await service.create_config(
        LLMConfigCreate(
            name="Vision second",
            provider="zhipu",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key="sk-vision-second",
            model_name="glm-4v-flash",
            extra={"capabilities": {"vision": True}},
        )
    )
    resolved = await resolve_vision_llm(session)
    assert resolved.model_name == "glm-4v-plus"


# ---------- resolve_llm_by_id（显式条目 + 备用参数） ----------


async def test_resolve_llm_by_id_returns_config(session: AsyncSession) -> None:
    primary = await _create_chat(session, "Primary")
    backup = await _create_chat(session, "Backup")
    resolved = await resolve_llm_by_id(
        session, primary.id, backup_config_id=backup.id
    )
    assert resolved.config_id == primary.id
    assert resolved.model_name == "m-Primary"
    assert resolved.api_key == "sk-Primary"
    assert resolved.name == "Primary"
    assert resolved.backup_config_id == backup.id


async def test_resolve_llm_by_id_missing_without_backup_raises(
    session: AsyncSession,
) -> None:
    with pytest.raises(LLMConfigNotFoundError, match="且无可用备用"):
        await resolve_llm_by_id(session, 9999)


async def test_resolve_llm_by_id_inactive_primary_falls_back_to_backup(
    session: AsyncSession,
) -> None:
    """主条目停用/删除：切显式备用（选择点携带的引用）。"""
    primary = await _create_chat(session, "Primary")
    backup = await _create_chat(session, "Backup")
    await _deactivate(session, primary.id)

    resolved = await resolve_llm_by_id(
        session, primary.id, backup_config_id=backup.id
    )
    assert resolved.config_id == backup.id
    assert resolved.model_name == "m-Backup"

    # 备用同时失效：fail loud
    await _deactivate(session, backup.id)
    with pytest.raises(LLMConfigNotFoundError, match="且无可用备用"):
        await resolve_llm_by_id(session, primary.id, backup_config_id=backup.id)


async def test_resolve_llm_by_id_unhealthy_primary_switches_to_backup(
    session: AsyncSession,
) -> None:
    """主条目冷却期内：健康门切备用，过期自愈回主。"""
    primary = await _create_chat(session, "Primary")
    backup = await _create_chat(session, "Backup")

    with patch(
        "app.services.admin.llm_failover.is_unhealthy",
        new=AsyncMock(return_value=True),
    ):
        resolved = await resolve_llm_by_id(
            session, primary.id, backup_config_id=backup.id
        )
    assert resolved.config_id == backup.id

    resolved_healthy = await resolve_llm_by_id(
        session, primary.id, backup_config_id=backup.id
    )
    assert resolved_healthy.config_id == primary.id


# ---------- 连通性探测（按用途分流） ----------


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


# ---------- 用途与协议对偶归一 ----------


async def test_purpose_protocol_normalization_on_create(session: AsyncSession) -> None:
    """systemone 协议 + 非 decision 用途 → 归一为 decision（对偶不变量，双向防毒）。"""
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="误选用途的判断模型",
            provider="codiv",
            protocol="systemone",
            base_url="https://api.codiv.ai",
            api_key="sk-codiv",
            model_name="openjev-0.1",
            purpose="chat",
        )
    )
    assert created.purpose == "decision"
    assert created.protocol == "systemone"


async def test_purpose_protocol_normalization_on_update(session: AsyncSession) -> None:
    """update 把 chat 条目协议改为 systemone → 用途随之归一为 decision。"""
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="Chat",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-openai",
            model_name="gpt-4o",
        )
    )
    updated = await service.update_config(created.id, LLMConfigUpdate(protocol="systemone"))
    assert updated.purpose == "decision"
    assert updated.protocol == "systemone"


async def test_embedding_purpose_forces_openai_protocol(session: AsyncSession) -> None:
    """嵌入端点为 OpenAI 形状，误选 anthropic 协议归一为 openai。"""
    service = LLMConfigService(session)
    created = await service.create_config(
        LLMConfigCreate(
            name="Embedding",
            provider="custom",
            base_url="https://gw.example.com/v1",
            api_key="sk-embed",
            model_name="embedding-3",
            purpose="embedding",
            protocol="anthropic",
        )
    )
    assert created.purpose == "embedding"
    assert created.protocol == "openai"
