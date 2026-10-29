"""用户 API Key 服务（多租户 MCP 访问凭证）。

- token 格式 ``inv_<8位hex前缀>_<32位随机串>``，明文只在签发响应出现一次；
- 库内只存 ``HMAC-SHA256(pepper, token)``，校验按 hash 精确查行；
- 校验同时要求 Key 未吊销/未过期、用户启用且审批通过；
- ``last_used_at`` 按节流窗口更新，避免每个 MCP 请求写库。

设计见 ``docs/requirement/10-mcp-multi-tenant-requirement.md``。
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import structlog
from mcp.server.auth.provider import AccessToken
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.schemas.api_key import ApiKeyIssuedResponse, ApiKeyResponse

logger = structlog.get_logger(__name__)

_TOKEN_PREFIX = "inv_"
_PREFIX_HEX_CHARS = 8
_SECRET_BYTES = 24  # token_urlsafe(24) 约 32 字符


def _pepper() -> str:
    settings = get_settings()
    return settings.mcp_api_key_pepper or settings.secret_key


def hash_api_key(token: str) -> str:
    """计算 token 的存储哈希（pepper 由配置决定）。"""
    return hmac.new(_pepper().encode(), token.encode(), hashlib.sha256).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """生成 (明文 token, 可展示前缀)。"""
    prefix = f"{_TOKEN_PREFIX}{secrets.token_hex(_PREFIX_HEX_CHARS // 2)}"
    return f"{prefix}_{secrets.token_urlsafe(_SECRET_BYTES)}", prefix


def _to_response(row: UserApiKey, username: str | None = None) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=row.id,
        user_id=row.user_id,
        username=username,
        name=row.name,
        key_prefix=row.key_prefix,
        scopes=list(row.scopes or []),
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
    )


class ApiKeyService:
    """管理员侧 API Key 签发 / 列表 / 吊销。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_keys(self, user_id: int | None = None) -> list[ApiKeyResponse]:
        """列出 Key（按创建时间倒序，含所属用户名）。"""
        stmt = (
            select(UserApiKey, User.username)
            .join(User, User.id == UserApiKey.user_id)
            .order_by(UserApiKey.created_at.desc(), UserApiKey.id.desc())
        )
        if user_id is not None:
            stmt = stmt.where(UserApiKey.user_id == user_id)
        rows = (await self._session.execute(stmt)).all()
        return [_to_response(row, username) for row, username in rows]

    async def create_key(
        self,
        *,
        user_id: int,
        name: str,
        scopes: list[str],
        expires_at: datetime | None = None,
    ) -> ApiKeyIssuedResponse:
        """签发 Key 并返回一次性明文。"""
        user = await self._session.get(User, user_id)
        if user is None:
            raise NotFoundError(f"用户 {user_id} 不存在")
        if expires_at is not None:
            if expires_at.tzinfo is None:
                raise BadRequestError("expires_at 须带时区（如 2026-12-31T00:00:00Z）")
            if expires_at <= utc_now():
                raise BadRequestError("expires_at 必须晚于当前时间")

        token, prefix = generate_api_key()
        row = UserApiKey(
            user_id=user_id,
            name=name,
            key_prefix=prefix,
            key_hash=hash_api_key(token),
            scopes=list(dict.fromkeys(scopes)),
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        response = _to_response(row, user.username)
        logger.info(
            "api_key.created",
            api_key_id=row.id,
            user_id=user_id,
            scopes=row.scopes,
        )
        return ApiKeyIssuedResponse(**response.model_dump(), token=token)

    async def revoke_key(self, key_id: int) -> None:
        """吊销 Key（管理员路径，幂等：已吊销直接返回）。"""
        row = await self._session.get(UserApiKey, key_id)
        if row is None:
            raise NotFoundError(f"API Key {key_id} 不存在")
        await self._revoke(row)

    async def revoke_own_key(self, key_id: int, user_id: int) -> None:
        """个人设置吊销：非本人 Key 一律按不存在处理，不泄露他人 Key 存在性。"""
        row = await self._session.get(UserApiKey, key_id)
        if row is None or row.user_id != user_id:
            raise NotFoundError(f"API Key {key_id} 不存在")
        await self._revoke(row)

    async def _revoke(self, row: UserApiKey) -> None:
        if row.revoked_at is not None:
            return
        row.revoked_at = utc_now()
        await self._session.commit()
        logger.info("api_key.revoked", api_key_id=row.id, user_id=row.user_id)


async def verify_api_key(token: str) -> AccessToken | None:
    """校验 Bearer token；无效返回 None（TokenVerifier 协议实现入口）。

    MCP 请求频率低，每次独立 session 查库；``last_used_at`` 节流写回，
    写失败不影响本次鉴权结果。
    """
    if not token.startswith(_TOKEN_PREFIX):
        return None

    async with AsyncSessionLocal() as session:
        row = await session.scalar(
            select(UserApiKey).where(UserApiKey.key_hash == hash_api_key(token))
        )
        if row is None or row.revoked_at is not None:
            return None
        now = utc_now()
        if row.expires_at is not None and row.expires_at <= now:
            return None
        user = await session.get(User, row.user_id)
        if user is None or not user.is_active or user.status != "approved":
            return None

        await _touch_last_used(session, row, now)
        return AccessToken(
            token=token,
            client_id=f"user:{user.id}",
            scopes=list(row.scopes or []),
            expires_at=int(row.expires_at.timestamp()) if row.expires_at else None,
            subject=str(user.id),
            claims={
                "user_id": user.id,
                "api_key_id": row.id,
                "username": user.username,
            },
        )


async def _touch_last_used(
    session: AsyncSession, row: UserApiKey, now: datetime
) -> None:
    """按节流窗口回写 last_used_at；失败只告警，不阻断鉴权。"""
    throttle = timedelta(
        seconds=get_settings().mcp_api_key_last_used_throttle_seconds
    )
    if row.last_used_at is not None and now - row.last_used_at < throttle:
        return
    try:
        await session.execute(
            update(UserApiKey)
            .where(UserApiKey.id == row.id)
            .values(last_used_at=now)
        )
        await session.commit()
    except Exception:  # noqa: BLE001 - 观测写入不阻断鉴权
        await session.rollback()
        logger.warning("api_key.touch_last_used_failed", api_key_id=row.id, exc_info=True)
