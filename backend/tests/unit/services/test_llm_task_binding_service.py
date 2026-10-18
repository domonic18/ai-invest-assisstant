"""AI 任务级模型绑定服务契约测试（解析三态、降级告警、整表单替换校验、目录一致性）。"""

from typing import Any, get_args
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.exceptions import UnprocessableEntityError
from app.models.llm_config import LLMConfig
from app.models.llm_task_binding import LLMTaskBinding
from app.schemas.llm_config import (
    TASK_KEY,
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigUpdate,
    TaskBindingItem,
    TaskBindingReplaceRequest,
)
from app.services.admin.llm_config_service import LLMConfigService
from app.services.admin.llm_task_binding_service import (
    TASK_SLOTS,
    get_task_bindings_view,
    replace_task_bindings,
    resolve_task_config_id,
    resolve_task_llm,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "a-32-byte-secret-key-for-tests!")


@pytest.fixture(autouse=True)
def _hermetic_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """隔离 redis：健康门/冷却查询打桩（同 test_llm_config_service）。"""
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
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[LLMConfig.__table__, LLMTaskBinding.__table__],
        )
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as db:
        yield db
    await engine.dispose()


async def _create_chat(
    session: AsyncSession, name: str, **kw: Any
) -> LLMConfigResponse:
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
    await LLMConfigService(session).update_config(
        config_id, LLMConfigUpdate(is_active=False)
    )


async def _bind(session: AsyncSession, task_key: str, config_id: int) -> None:
    session.add(LLMTaskBinding(task_key=task_key, config_id=config_id, updated_by=1))
    await session.commit()


# ---------- catalog 一致性 ----------


def test_catalog_matches_schema_literal() -> None:
    """TASK_SLOTS 键集合与 schemas TASK_KEY Literal 互为镜像（API 边界钉死）。"""
    literal_keys = set(get_args(TASK_KEY))
    assert literal_keys == set(TASK_SLOTS)
    assert len(TASK_SLOTS) == 10
    assert all(spec.label and spec.description for spec in TASK_SLOTS.values())


# ---------- resolve_task_config_id 三态 ----------


async def test_config_id_unbound_returns_none(session: AsyncSession) -> None:
    await _create_chat(session, "Default", is_default=True)
    assert await resolve_task_config_id(session, "news_score") is None


async def test_config_id_bound_returns_entry(session: AsyncSession) -> None:
    bound = await _create_chat(session, "Cheap")
    await _bind(session, "news_score", bound.id)
    assert await resolve_task_config_id(session, "news_score") == bound.id


async def test_config_id_missing_entry_returns_none(session: AsyncSession) -> None:
    """绑定行指向已删除条目：降级 None（跟随默认），不抛异常。"""
    await _bind(session, "news_score", 9999)
    assert await resolve_task_config_id(session, "news_score") is None


async def test_config_id_inactive_entry_returns_none(session: AsyncSession) -> None:
    bound = await _create_chat(session, "Disabled")
    await _deactivate(session, bound.id)
    await _bind(session, "news_score", bound.id)
    assert await resolve_task_config_id(session, "news_score") is None


async def test_config_id_non_chat_purpose_returns_none(session: AsyncSession) -> None:
    embed = await _create_chat(session, "Embed", purpose="embedding")
    await _bind(session, "news_score", embed.id)
    assert await resolve_task_config_id(session, "news_score") is None


async def test_config_id_unknown_key_returns_none(session: AsyncSession) -> None:
    assert await resolve_task_config_id(session, "no_such_task") is None


# ---------- resolve_task_llm 绑定与回退 ----------


async def test_llm_unbound_follows_system_default(session: AsyncSession) -> None:
    default = await _create_chat(session, "Default", is_default=True)
    resolved = await resolve_task_llm(session, "news_score")
    assert resolved.config_id == default.id


async def test_llm_bound_resolves_bound_entry(session: AsyncSession) -> None:
    await _create_chat(session, "Default", is_default=True)
    bound = await _create_chat(session, "Cheap")
    await _bind(session, "news_score", bound.id)
    resolved = await resolve_task_llm(session, "news_score")
    assert resolved.config_id == bound.id
    assert resolved.model_name == "m-Cheap"


async def test_llm_missing_entry_degrades_to_default(session: AsyncSession) -> None:
    """绑定条目事后被删：降级系统默认（调度可用性优先），不抛异常。"""
    default = await _create_chat(session, "Default", is_default=True)
    await _bind(session, "news_score", 9999)
    resolved = await resolve_task_llm(session, "news_score")
    assert resolved.config_id == default.id


async def test_llm_unknown_key_follows_default(session: AsyncSession) -> None:
    default = await _create_chat(session, "Default", is_default=True)
    resolved = await resolve_task_llm(session, "no_such_task")
    assert resolved.config_id == default.id


# ---------- get_task_bindings_view ----------


async def test_view_lists_registry_order_with_binding_info(
    session: AsyncSession,
) -> None:
    default = await _create_chat(session, "Default", is_default=True)
    cheap = await _create_chat(session, "Cheap")
    await _bind(session, "news_score", cheap.id)

    view = await get_task_bindings_view(session)

    assert [slot.task_key for slot in view] == list(TASK_SLOTS)
    assert len(view) == 10
    by_key = {slot.task_key: slot for slot in view}
    assert by_key["news_score"].config_id == cheap.id
    assert by_key["news_score"].config_name == "Cheap"
    assert by_key["news_score"].model_name == "m-Cheap"
    assert by_key["news_score"].updated_at is not None
    unbound = by_key["social_sentiment"]
    assert (unbound.config_id, unbound.config_name, unbound.model_name) == (
        None,
        None,
        None,
    )
    assert default.id  # default 存在但不影响未绑定槽位的空态展示


# ---------- replace_task_bindings ----------


def _req(*items: TaskBindingItem) -> TaskBindingReplaceRequest:
    return TaskBindingReplaceRequest(bindings=list(items))


async def test_replace_creates_updates_and_unbinds(session: AsyncSession) -> None:
    await _create_chat(session, "Default", is_default=True)
    first = await _create_chat(session, "First")
    second = await _create_chat(session, "Second")

    await replace_task_bindings(
        session,
        admin_id=1,
        data=_req(TaskBindingItem(task_key="news_score", config_id=first.id)),
    )
    rows = (
        (await session.execute(select(LLMTaskBinding))).scalars().all()
    )
    assert [(r.task_key, r.config_id) for r in rows] == [("news_score", first.id)]

    # 已有行更新 + 新增 + 解绑删行，一事务完成
    await replace_task_bindings(
        session,
        admin_id=2,
        data=_req(
            TaskBindingItem(task_key="news_score", config_id=second.id),
            TaskBindingItem(task_key="social_sentiment", config_id=first.id),
            TaskBindingItem(task_key="news_storyline", config_id=None),
        ),
    )
    rows = {
        r.task_key: r
        for r in (await session.execute(select(LLMTaskBinding))).scalars().all()
    }
    assert set(rows) == {"news_score", "social_sentiment"}
    assert rows["news_score"].config_id == second.id
    assert rows["news_score"].updated_by == 2
    assert rows["social_sentiment"].config_id == first.id


async def test_replace_leaves_unsubmitted_slots_untouched(
    session: AsyncSession,
) -> None:
    await _create_chat(session, "Default", is_default=True)
    cfg = await _create_chat(session, "Cfg")
    await replace_task_bindings(
        session,
        admin_id=1,
        data=_req(TaskBindingItem(task_key="news_score", config_id=cfg.id)),
    )
    await replace_task_bindings(
        session,
        admin_id=1,
        data=_req(TaskBindingItem(task_key="social_sentiment", config_id=cfg.id)),
    )
    rows = {
        r.task_key for r in (await session.execute(select(LLMTaskBinding))).scalars().all()
    }
    assert rows == {"news_score", "social_sentiment"}


async def test_replace_rejects_unknown_key(session: AsyncSession) -> None:
    # Literal 在 schema 边界已拦；此处绕过校验直达服务层守卫（服务可被非 API 调用）
    bogus = TaskBindingItem.model_construct(task_key="nope", config_id=1)
    with pytest.raises(UnprocessableEntityError, match="未知任务槽位"):
        await replace_task_bindings(session, admin_id=1, data=_req(bogus))


async def test_replace_rejects_duplicate_keys(session: AsyncSession) -> None:
    with pytest.raises(UnprocessableEntityError, match="重复提交"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(
                TaskBindingItem(task_key="news_score", config_id=None),
                TaskBindingItem(task_key="news_score", config_id=None),
            ),
        )


async def test_replace_rejects_missing_config(session: AsyncSession) -> None:
    with pytest.raises(UnprocessableEntityError, match="不存在"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(TaskBindingItem(task_key="news_score", config_id=9999)),
        )


async def test_replace_rejects_inactive_config(session: AsyncSession) -> None:
    cfg = await _create_chat(session, "Disabled")
    await _deactivate(session, cfg.id)
    with pytest.raises(UnprocessableEntityError, match="已停用"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(TaskBindingItem(task_key="news_score", config_id=cfg.id)),
        )


async def test_replace_rejects_non_chat_purpose(session: AsyncSession) -> None:
    embed = await _create_chat(session, "Embed", purpose="embedding")
    with pytest.raises(UnprocessableEntityError, match="chat"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(TaskBindingItem(task_key="news_score", config_id=embed.id)),
        )
