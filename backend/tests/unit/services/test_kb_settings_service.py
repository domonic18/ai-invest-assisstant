"""知识库设置服务单测：角色槽位 purpose 校验与 resolve_role_model 读侧二次校验。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.kb import KbSettings
from app.models.llm_config import LLMConfig
from app.schemas.kb import KbSettingsUpdateRequest
from app.services.kb.settings_service import (
    get_settings_view,
    resolve_role_model,
    update_settings,
)

pytestmark = pytest.mark.unit


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[KbSettings.__table__, LLMConfig.__table__],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


def _config(purpose: str, *, name: str = "cfg", is_active: bool = True) -> LLMConfig:
    return LLMConfig(
        name=name,
        provider="openai",
        protocol="openai",
        base_url="https://example.com/v1",
        api_key_encrypted="enc",
        model_name="m",
        is_active=is_active,
        purpose=purpose,
    )


async def _seed_config(session: AsyncSession, purpose: str) -> LLMConfig:
    row = _config(purpose)
    session.add(row)
    await session.flush()
    return row


@pytest.mark.parametrize(
    ("field", "role", "wrong_purpose"),
    [
        ("embedding_config_id", "embedding", "chat"),
        ("clean_model_id", "clean", "embedding"),
        ("extract_model_id", "extract", "vision"),
        ("vision_model_id", "vision", "chat"),
    ],
)
async def test_update_rejects_purpose_mismatch(
    session: AsyncSession, field: str, role: str, wrong_purpose: str
) -> None:
    """四个角色槽位各一条负例：purpose 不匹配的条目拒绝绑定。"""
    cfg = await _seed_config(session, wrong_purpose)
    data = KbSettingsUpdateRequest(**{field: cfg.id})
    with pytest.raises(UnprocessableEntityError, match=role):
        await update_settings(session, admin_id=1, data=data)


async def test_update_rejects_missing_and_inactive(session: AsyncSession) -> None:
    cfg = await _seed_config(session, "embedding")
    with pytest.raises(NotFoundError):
        await update_settings(
            session,
            admin_id=1,
            data=KbSettingsUpdateRequest(embedding_config_id=9999),
        )
    cfg.is_active = False
    await session.commit()
    with pytest.raises(UnprocessableEntityError, match="停用"):
        await update_settings(
            session,
            admin_id=1,
            data=KbSettingsUpdateRequest(embedding_config_id=cfg.id),
        )


async def test_update_happy_path_and_patch_semantics(session: AsyncSession) -> None:
    """合法槽位保存成功；仅提交的字段更新，未提交的角色槽位不被清空。"""
    embedding = await _seed_config(session, "embedding")
    clean = await _seed_config(session, "chat")
    view = await update_settings(
        session,
        admin_id=1,
        data=KbSettingsUpdateRequest(
            embedding_config_id=embedding.id,
            clean_model_id=clean.id,
            top_k=12,
        ),
    )
    assert view.embedding_config_id == embedding.id
    assert view.clean_model_id == clean.id
    assert view.top_k == 12

    again = await update_settings(
        session, admin_id=1, data=KbSettingsUpdateRequest(top_k=5)
    )
    assert again.top_k == 5
    assert again.embedding_config_id == embedding.id
    assert again.clean_model_id == clean.id


async def test_resolve_role_model_returns_config(session: AsyncSession) -> None:
    cfg = await _seed_config(session, "embedding")
    await update_settings(
        session,
        admin_id=1,
        data=KbSettingsUpdateRequest(embedding_config_id=cfg.id),
    )
    resolved = await resolve_role_model(session, "embedding")
    assert resolved.id == cfg.id


async def test_resolve_role_model_unset_raises(session: AsyncSession) -> None:
    with pytest.raises(UnprocessableEntityError, match="未配置"):
        await resolve_role_model(session, "vision")


async def test_resolve_role_model_revalidates_after_deactivation(
    session: AsyncSession,
) -> None:
    """保存后再停用/改用途：读侧二次校验显式失败而非静默走错模型。"""
    cfg = await _seed_config(session, "embedding")
    await update_settings(
        session,
        admin_id=1,
        data=KbSettingsUpdateRequest(embedding_config_id=cfg.id),
    )
    cfg.is_active = False
    await session.commit()
    with pytest.raises(UnprocessableEntityError, match="不可用"):
        await resolve_role_model(session, "embedding")


async def test_get_settings_view_defaults(session: AsyncSession) -> None:
    """迁移未 seed（如新库走兜底创建）时视图返回默认值且槽位为空。"""
    view = await get_settings_view(session)
    assert view.top_k == 8
    assert view.embedding_config_id is None
    assert view.hotwords == []
