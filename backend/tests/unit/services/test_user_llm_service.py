"""BYOK 服务单测：加密往返、脱敏、出口优先级（BYOK > 默认/视觉）、清除回落。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.account_quota import UserLlmConfig
from app.models.llm_config import LLMConfig
from app.models.user import User
from app.services.quota.constants import OUTLET_BYOK, OUTLET_SYSTEM
from app.services.quota.user_llm_service import (
    clear_user_llm_config,
    get_user_llm_config,
    resolve_llm,
    save_user_llm_config,
)
from app.utils.crypto import decrypt_token, encrypt_token

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
            tables=[User.__table__, UserLlmConfig.__table__, LLMConfig.__table__],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed_user_with_default_llm(session: AsyncSession) -> int:
    user = User(username="u", email="u@x.com", password_hash="x", role="user")
    session.add(user)
    session.add(
        LLMConfig(
            name="default",
            provider="openai",
            protocol="openai",
            base_url="https://default.example.com/v1",
            api_key_encrypted=encrypt_token("sk-default"),
            model_name="sys-model",
            is_default=True,
            is_active=True,
        )
    )
    await session.flush()
    return user.id


async def test_save_encrypts_and_masks(session: AsyncSession) -> None:
    user_id = await _seed_user_with_default_llm(session)
    view = await save_user_llm_config(
        session,
        user_id,
        protocol="anthropic",
        base_url="https://byok.example.com/v1/",
        model_name="user-model",
        api_key="sk-my-own-key-123456",
    )
    assert view.protocol == "anthropic"
    assert view.base_url == "https://byok.example.com/v1"  # 尾斜杠归一
    assert view.api_key_masked.startswith("sk-m")
    assert "sk-my-own-key" not in view.api_key_masked

    row = await session.get(UserLlmConfig, user_id)
    assert row is not None
    assert "sk-my-own-key-123456" not in row.api_key_encrypted
    assert decrypt_token(row.api_key_encrypted) == "sk-my-own-key-123456"


async def test_resolve_byok_takes_priority(session: AsyncSession) -> None:
    user_id = await _seed_user_with_default_llm(session)
    await save_user_llm_config(
        session,
        user_id,
        protocol="openai",
        base_url="https://byok.example.com/v1",
        model_name="user-model",
        api_key="sk-own",
    )
    cfg, outlet = await resolve_llm(session, user_id)
    assert outlet == OUTLET_BYOK
    assert cfg.provider == "byok"
    assert cfg.model_name == "user-model"
    assert cfg.api_key == "sk-own"


async def test_resolve_without_byok_uses_default(session: AsyncSession) -> None:
    user_id = await _seed_user_with_default_llm(session)
    cfg, outlet = await resolve_llm(session, user_id)
    assert outlet == OUTLET_SYSTEM
    assert cfg.model_name == "sys-model"


async def test_clear_falls_back(session: AsyncSession) -> None:
    user_id = await _seed_user_with_default_llm(session)
    await save_user_llm_config(
        session,
        user_id,
        protocol="openai",
        base_url="https://byok.example.com/v1",
        model_name="user-model",
        api_key="sk-own",
    )
    assert await clear_user_llm_config(session, user_id) is True
    assert await get_user_llm_config(session, user_id) is None
    # 再清一次返回 False；解析回落系统默认
    assert await clear_user_llm_config(session, user_id) is False
    _cfg, outlet = await resolve_llm(session, user_id)
    assert outlet == OUTLET_SYSTEM


async def test_resolve_no_user_is_default(session: AsyncSession) -> None:
    await _seed_user_with_default_llm(session)
    _cfg, outlet = await resolve_llm(session, None)
    assert outlet == OUTLET_SYSTEM
