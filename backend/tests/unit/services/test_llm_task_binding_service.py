"""AI 任务级模型绑定服务契约测试（槽位主备解析、fail loud、整表单替换校验、目录一致性）。"""

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
from app.services.admin import llm_task_binding_service as svc
from app.services.admin.llm_config_service import (
    LLMConfigNotConfiguredError,
    LLMConfigService,
)
from app.services.admin.llm_task_binding_service import (
    TASK_SLOTS,
    get_task_bindings_view,
    replace_task_bindings,
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


async def _create(
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


async def _create_chat(session: AsyncSession, name: str, **kw: Any) -> LLMConfigResponse:
    return await _create(session, name, **kw)


async def _deactivate(session: AsyncSession, config_id: int) -> None:
    await LLMConfigService(session).update_config(
        config_id, LLMConfigUpdate(is_active=False)
    )


async def _bind(
    session: AsyncSession,
    task_key: str,
    config_id: int,
    backup_config_id: int | None = None,
) -> None:
    session.add(
        LLMTaskBinding(
            task_key=task_key,
            config_id=config_id,
            backup_config_id=backup_config_id,
            updated_by=1,
        )
    )
    await session.commit()


# ---------- catalog 一致性 ----------


def test_catalog_matches_schema_literal() -> None:
    """TASK_SLOTS 键集合与 schemas TASK_KEY Literal 互为镜像（API 边界钉死）。"""
    literal_keys = set(get_args(TASK_KEY))
    assert literal_keys == set(TASK_SLOTS)
    assert len(TASK_SLOTS) == 12
    assert all(spec.label and spec.description for spec in TASK_SLOTS.values())
    assert TASK_SLOTS["assistant_chat"].purpose == "chat"
    assert TASK_SLOTS["decision"].purpose == "decision"
    assert TASK_SLOTS["news_score"].purpose == "chat"


# ---------- resolve_task_llm 主备解析 ----------


async def test_llm_bound_resolves_bound_entry(session: AsyncSession) -> None:
    bound = await _create_chat(session, "Cheap")
    await _bind(session, "news_score", bound.id)
    resolved = await resolve_task_llm(session, "news_score")
    assert resolved.config_id == bound.id
    assert resolved.model_name == "m-Cheap"
    assert resolved.backup_config_id is None


async def test_llm_unbound_raises(session: AsyncSession) -> None:
    """槽位未绑定主模型：fail loud（不再静默降级默认）。"""
    with pytest.raises(LLMConfigNotConfiguredError, match="未绑定主模型"):
        await resolve_task_llm(session, "news_score")


async def test_llm_unknown_key_raises(session: AsyncSession) -> None:
    with pytest.raises(LLMConfigNotConfiguredError, match="未知任务槽位"):
        await resolve_task_llm(session, "no_such_task")


async def test_llm_missing_entry_without_backup_raises(session: AsyncSession) -> None:
    """绑定条目事后被删且无备用：fail loud。"""
    await _bind(session, "news_score", 9999)
    with pytest.raises(LLMConfigNotConfiguredError, match="主备模型皆不可用"):
        await resolve_task_llm(session, "news_score")


async def test_llm_inactive_entry_falls_back_to_backup(session: AsyncSession) -> None:
    """主条目停用：切显式备用。"""
    primary = await _create_chat(session, "Primary")
    backup = await _create_chat(session, "Backup")
    await _deactivate(session, primary.id)
    await _bind(session, "news_score", primary.id, backup.id)
    resolved = await resolve_task_llm(session, "news_score")
    assert resolved.config_id == backup.id
    assert resolved.backup_config_id == backup.id


async def test_llm_unhealthy_primary_switches_to_backup(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """主条目冷却期内：健康门切备用。"""
    primary = await _create_chat(session, "Primary")
    backup = await _create_chat(session, "Backup")
    await _bind(session, "news_score", primary.id, backup.id)
    monkeypatch.setattr(
        "app.services.admin.llm_failover.is_unhealthy",
        AsyncMock(side_effect=lambda cid: cid == primary.id),
    )
    resolved = await resolve_task_llm(session, "news_score")
    assert resolved.config_id == backup.id


async def test_llm_decision_slot_resolves_decision_entry(session: AsyncSession) -> None:
    decision = await _create(session, "Judge", purpose="decision", protocol="systemone")
    await _bind(session, "decision", decision.id)
    resolved = await resolve_task_llm(session, "decision")
    assert resolved.config_id == decision.id
    assert resolved.protocol == "systemone"


# ---------- get_task_bindings_view ----------


async def test_view_lists_registry_order_with_binding_info(
    session: AsyncSession,
) -> None:
    primary = await _create_chat(session, "Primary")
    backup = await _create_chat(session, "Backup")
    await _bind(session, "news_score", primary.id, backup.id)

    view = await get_task_bindings_view(session)

    assert [slot.task_key for slot in view] == list(TASK_SLOTS)
    assert len(view) == 12
    by_key = {slot.task_key: slot for slot in view}
    bound = by_key["news_score"]
    assert bound.config_id == primary.id
    assert bound.config_name == "Primary"
    assert bound.model_name == "m-Primary"
    assert bound.backup_config_id == backup.id
    assert bound.backup_config_name == "Backup"
    assert bound.backup_model_name == "m-Backup"
    assert bound.updated_at is not None
    unbound = by_key["social_sentiment"]
    assert (unbound.config_id, unbound.config_name, unbound.backup_config_id) == (
        None,
        None,
        None,
    )


# ---------- replace_task_bindings ----------


def _req(*items: TaskBindingItem) -> TaskBindingReplaceRequest:
    return TaskBindingReplaceRequest(bindings=list(items))


async def test_replace_creates_updates_and_clears_backup(session: AsyncSession) -> None:
    first = await _create_chat(session, "First")
    second = await _create_chat(session, "Second")
    backup = await _create_chat(session, "Backup")

    await replace_task_bindings(
        session,
        admin_id=1,
        data=_req(
            TaskBindingItem(
                task_key="news_score", config_id=first.id, backup_config_id=backup.id
            )
        ),
    )
    rows = (
        (await session.execute(select(LLMTaskBinding))).scalars().all()
    )
    assert [(r.task_key, r.config_id, r.backup_config_id) for r in rows] == [
        ("news_score", first.id, backup.id)
    ]

    # 已有行更新 + 新增；备用可清空（None）
    await replace_task_bindings(
        session,
        admin_id=2,
        data=_req(
            TaskBindingItem(task_key="news_score", config_id=second.id),
            TaskBindingItem(
                task_key="social_sentiment", config_id=first.id, backup_config_id=backup.id
            ),
        ),
    )
    rows = {
        r.task_key: r
        for r in (await session.execute(select(LLMTaskBinding))).scalars().all()
    }
    assert set(rows) == {"news_score", "social_sentiment"}
    assert (rows["news_score"].config_id, rows["news_score"].backup_config_id) == (
        second.id,
        None,
    )
    assert rows["news_score"].updated_by == 2
    assert (rows["social_sentiment"].config_id, rows["social_sentiment"].backup_config_id) == (
        first.id,
        backup.id,
    )


async def test_replace_leaves_unsubmitted_slots_untouched(
    session: AsyncSession,
) -> None:
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
    cfg = await _create_chat(session, "Cfg")
    with pytest.raises(UnprocessableEntityError, match="重复提交"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(
                TaskBindingItem(task_key="news_score", config_id=cfg.id),
                TaskBindingItem(task_key="news_score", config_id=cfg.id),
            ),
        )


async def test_replace_rejects_null_primary(session: AsyncSession) -> None:
    """主模型必填：None（解绑语义）不再合法（schema 边界 + 服务层守卫）。"""
    item = TaskBindingItem.model_construct(task_key="news_score", config_id=None)
    with pytest.raises(UnprocessableEntityError, match="必须绑定主模型"):
        await replace_task_bindings(session, admin_id=1, data=_req(item))


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


async def test_replace_rejects_purpose_mismatch(session: AsyncSession) -> None:
    embed = await _create_chat(session, "Embed", purpose="embedding")
    with pytest.raises(UnprocessableEntityError, match="用途为 chat"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(TaskBindingItem(task_key="news_score", config_id=embed.id)),
        )


async def test_replace_decision_slot_rejects_chat_entry(session: AsyncSession) -> None:
    """decision 槽只收 decision 条目（purpose 按槽位匹配）。"""
    chat = await _create_chat(session, "Chat")
    with pytest.raises(UnprocessableEntityError, match="用途为 decision"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(TaskBindingItem(task_key="decision", config_id=chat.id)),
        )


async def test_replace_decision_slot_accepts_decision_entry(session: AsyncSession) -> None:
    decision = await _create(
        session, "Judge", purpose="decision", protocol="systemone"
    )
    await replace_task_bindings(
        session,
        admin_id=1,
        data=_req(TaskBindingItem(task_key="decision", config_id=decision.id)),
    )
    row = (
        await session.execute(
            select(LLMTaskBinding).where(LLMTaskBinding.task_key == "decision")
        )
    ).scalar_one()
    assert row.config_id == decision.id


async def test_replace_rejects_backup_equal_to_primary(session: AsyncSession) -> None:
    cfg = await _create_chat(session, "Cfg")
    with pytest.raises(UnprocessableEntityError, match="备用模型不能与主模型相同"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(
                TaskBindingItem(
                    task_key="news_score", config_id=cfg.id, backup_config_id=cfg.id
                )
            ),
        )


async def test_replace_rejects_invalid_backup(session: AsyncSession) -> None:
    cfg = await _create_chat(session, "Cfg")
    embed = await _create_chat(session, "Embed", purpose="embedding")
    with pytest.raises(UnprocessableEntityError, match="用途为 chat"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(
                TaskBindingItem(
                    task_key="news_score", config_id=cfg.id, backup_config_id=embed.id
                )
            ),
        )
    with pytest.raises(UnprocessableEntityError, match="备用模型"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(
                TaskBindingItem(
                    task_key="news_score", config_id=cfg.id, backup_config_id=9999
                )
            ),
        )


async def test_replace_backup_purpose_must_match_slot(session: AsyncSession) -> None:
    """chat 槽的备用也必须是 chat 条目。"""
    cfg = await _create_chat(session, "Cfg")
    embed = await _create_chat(session, "Embed", purpose="embedding")
    with pytest.raises(UnprocessableEntityError, match="用途为 chat"):
        await replace_task_bindings(
            session,
            admin_id=1,
            data=_req(
                TaskBindingItem(
                    task_key="news_score", config_id=cfg.id, backup_config_id=embed.id
                )
            ),
        )
    assert not svc.TASK_SLOTS.get("nope")  # 注册表未注册键返回 None（守卫路径覆盖）
