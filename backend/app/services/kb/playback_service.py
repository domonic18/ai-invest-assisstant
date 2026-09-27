"""播放凭证签发与鉴权底座（arch/09 §8，批次 F1）。

防盗分层：一次性短时效凭证（Redis ≤30min，绑定用户+素材）→ 书页端点
凭证即身份（``<img>`` src 无法携带 header）；视频/音频按需签发同时效
预签名 GET 直链（字节流不经 SCF，网关 6MB 响应上限不可承载媒体）。
异常拉取全量审计 ``kb.security.denied`` 并按账号滑动窗口计数（阈值
告警日志）；书页渲染/字幕轨见 ``book_render`` / ``subtitles``。
"""

import json
import secrets
import time
import uuid
from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import (
    KB_IMAGE_ORIGINAL_URL_TTL_SECONDS,
    KB_PLAYBACK_TOKEN_KEY_TEMPLATE,
    KB_PLAYBACK_TOKEN_TTL_SECONDS,
    KB_SECURITY_ALERT_THRESHOLD,
    KB_SECURITY_DENIED_KEY_TEMPLATE,
    KB_SECURITY_DENIED_WINDOW_SECONDS,
    KbProcessStatus,
)
from app.core.cache import get_redis
from app.core.exceptions import (
    BadRequestError,
    InternalError,
    NotFoundError,
    UnauthorizedError,
)
from app.models.kb import KbImageAsset, KbMedia, KbSource
from app.models.user import User
from app.repositories.kb import media_repository
from app.schemas.kb import KbImageUrlResponse, KbPlaybackTokenResponse
from app.services.admin.audit_service import record_audit
from app.services.common.minio_service import get_minio_service

logger = structlog.get_logger(__name__)

_AUDIT_ACTION_DENIED = "kb.security.denied"


async def issue_playback_token(
    session: AsyncSession, *, user_id: int, media_id: int
) -> KbPlaybackTokenResponse:
    """签发播放凭证（≤30min 绑定用户+素材；携带上/下一集 id 与预签名直链）。

    凭证值带 ``{userId}.`` 前缀：书页端点无 Bearer 上下文（``<img>`` src
    无法携带 header），过期/泄露凭证的审计归属靠前缀恢复。视频/音频的
    播放凭证 = 同时效预签名 GET 直链（字节流直达 MinIO，不经后端代理），
    直链原生支持 Range/206，seek 秒级；书素材 streamUrl 为 None（书页
    仍走 token 代理以烧录水印）。

    Args:
        session: 数据库会话。
        user_id: 请求用户 id。
        media_id: 素材 id（课程集或书）。

    Returns:
        凭证视图（token/expiresIn/streamUrl/prevMediaId/nextMediaId）。

    Raises:
        NotFoundError: 素材不存在/未完成处理/知识库停用。
        InternalError: Redis / 对象存储不可用（安全凭证 fail-closed）。
    """
    media = await _load_media(session, media_id)
    token = f"{user_id}.{secrets.token_urlsafe(32)}"
    payload = json.dumps({"userId": user_id, "mediaId": media_id})
    try:
        await get_redis().set(
            KB_PLAYBACK_TOKEN_KEY_TEMPLATE.format(token=token),
            payload,
            ex=KB_PLAYBACK_TOKEN_TTL_SECONDS,
        )
    except Exception as exc:  # RedisError
        logger.error("kb_playback_redis_unavailable", error=str(exc))
        raise InternalError("播放凭证服务暂不可用，请稍后重试") from exc

    prev_id, next_id = (None, None)
    stream_url: str | None = None
    if media.media_kind in ("video", "audio"):
        prev_id, next_id = await _neighbor_episode_ids(session, media)
        stream_url = await get_minio_service().get_presigned_url(
            media.cos_key, expires=timedelta(seconds=KB_PLAYBACK_TOKEN_TTL_SECONDS)
        )
        if stream_url is None:
            raise InternalError("对象存储暂不可用，请稍后重试")
    return KbPlaybackTokenResponse(
        token=token,
        expires_in=KB_PLAYBACK_TOKEN_TTL_SECONDS,
        media_id=media_id,
        stream_url=stream_url,
        prev_media_id=prev_id,
        next_media_id=next_id,
        page_count=media.page_count if media.media_kind == "book" else None,
    )


async def _neighbor_episode_ids(
    session: AsyncSession, media: KbMedia
) -> tuple[int | None, int | None]:
    """同知识库可播集序列中当前集的相邻集 id（书素材返回 None 对）。"""
    siblings = await media_repository.list_by_source(session, media.source_id)
    playable = [
        m.id
        for m in siblings
        if m.media_kind in ("video", "audio") and m.process_status == KbProcessStatus.DONE
    ]
    if media.id not in playable:
        return None, None
    index = playable.index(media.id)
    prev_id = playable[index - 1] if index > 0 else None
    next_id = playable[index + 1] if index + 1 < len(playable) else None
    return prev_id, next_id


def _token_user_hint(token: str) -> int | None:
    """从凭证 ``{userId}.`` 前缀解析归属用户（不可解析返回 None）。"""
    head = token.split(".", 1)[0]
    return int(head) if head.isdigit() else None


async def _require_token(
    session: AsyncSession,
    *,
    token: str,
    media_id: int,
    action: str,
    ip: str | None,
) -> dict[str, Any]:
    """校验播放凭证并返回 Redis 载荷（过期/素材错配 → 401 + 审计）。

    stream/书页端点无 Bearer 上下文（``<video>``/``<img>`` src 无法携带
    header），凭证本身即身份：归属用户由凭证前缀与载荷恢复。
    """
    try:
        raw = await get_redis().get(
            KB_PLAYBACK_TOKEN_KEY_TEMPLATE.format(token=token)
        )
    except Exception as exc:  # RedisError
        logger.error("kb_playback_redis_unavailable", error=str(exc))
        raise InternalError("播放凭证服务暂不可用，请稍后重试") from exc
    if raw is None:
        await _record_denial(
            session, user_id=_token_user_hint(token), media_id=media_id, action=action,
            reason="expired_or_unknown_token", ip=ip,
        )
        raise UnauthorizedError("播放凭证无效或已过期")
    try:
        payload: dict[str, Any] = json.loads(raw)
    except (TypeError, ValueError):
        await _record_denial(
            session, user_id=_token_user_hint(token), media_id=media_id, action=action,
            reason="malformed_token", ip=ip,
        )
        raise UnauthorizedError("播放凭证无效")
    if payload.get("mediaId") != media_id:
        await _record_denial(
            session, user_id=payload.get("userId"), media_id=media_id, action=action,
            reason="media_mismatch", ip=ip,
        )
        raise UnauthorizedError("播放凭证与请求素材不匹配")
    return payload


async def _record_denial(
    session: AsyncSession,
    *,
    user_id: int | None,
    media_id: int,
    action: str,
    reason: str,
    ip: str | None,
) -> None:
    """审计 ``kb.security.denied`` 并维护账号级滑动窗口计数。

    无法归属账号的异常（凭证完全不可解析，或归属指向不存在的账号——
    凭证前缀是外部输入不可信，伪造前缀不得触发审计表 FK 违约）仅留
    结构化日志：审计表 ``actor_id`` 非空约束不允许无主记录。
    """
    if user_id is None or await session.get(User, user_id) is None:
        logger.warning(
            "kb_security_denial_unattributed",
            action=action,
            reason=reason,
            media_id=media_id,
            ip=ip,
        )
        return
    count = await _bump_denial_count(user_id)
    detail: dict[str, Any] = {
        "action": action,
        "reason": reason,
        "mediaId": media_id,
    }
    if count >= KB_SECURITY_ALERT_THRESHOLD:
        detail["alert"] = True
        logger.warning(
            "kb_security_denial_threshold",
            user_id=user_id,
            count=count,
            window_seconds=KB_SECURITY_DENIED_WINDOW_SECONDS,
        )
    await record_audit(
        session,
        actor_id=user_id,
        action=_AUDIT_ACTION_DENIED,
        target_user_id=user_id,
        detail=detail,
        ip=ip,
    )
    await session.commit()


async def _bump_denial_count(user_id: int) -> int:
    """滑动窗口计数 +1 并返回窗口内当前次数（Redis 故障返回 0 不阻塞审计）。"""
    try:
        client = get_redis()
        key = KB_SECURITY_DENIED_KEY_TEMPLATE.format(user_id=user_id)
        now = time.time()
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        async with client.pipeline(transaction=False) as pipe:
            pipe.zadd(key, {member: now})
            pipe.zremrangebyscore(
                key, 0, now - KB_SECURITY_DENIED_WINDOW_SECONDS
            )
            pipe.expire(key, KB_SECURITY_DENIED_WINDOW_SECONDS * 2)
            pipe.zcard(key)
            results = await pipe.execute()
        return int(results[-1])
    except Exception as exc:  # RedisError
        logger.warning("kb_security_count_unavailable", error=str(exc))
        return 0


async def issue_image_url(
    session: AsyncSession, *, image_id: int
) -> KbImageUrlResponse:
    """签发图片原图短时效预签名 URL（≤15min；消费侧点击原图时按需签）。

    Args:
        session: 数据库会话。
        image_id: 图片资产 id（kb_image_asset）。

    Returns:
        预签名 URL 视图（url/expiresIn）。

    Raises:
        NotFoundError: 资产不存在或所属素材不可消费。
        InternalError: 对象存储不可用。
    """
    asset = await session.get(KbImageAsset, image_id)
    if asset is None:
        raise NotFoundError("图片不存在")
    await _load_media(session, asset.media_id)
    url = await get_minio_service().get_presigned_url(
        asset.cos_key, expires=timedelta(seconds=KB_IMAGE_ORIGINAL_URL_TTL_SECONDS)
    )
    if url is None:
        raise InternalError("对象存储暂不可用，请稍后重试")
    return KbImageUrlResponse(
        url=url, expires_in=KB_IMAGE_ORIGINAL_URL_TTL_SECONDS
    )


async def _load_media(
    session: AsyncSession,
    media_id: int,
    *,
    kinds: tuple[str, ...] | None = None,
) -> KbMedia:
    """加载可消费素材（存活 + 所属库启用 + 处理完成；不满足按 404 隐藏）。"""
    media = await media_repository.get(session, media_id)
    if media is None or media.deleted_at is not None:
        raise NotFoundError("素材不存在")
    source = await session.get(KbSource, media.source_id)
    if (
        source is None
        or source.deleted_at is not None
        or not source.enabled
    ):
        raise NotFoundError("素材不存在")
    if media.process_status != KbProcessStatus.DONE:
        raise NotFoundError("素材暂不可用")
    if kinds is not None and media.media_kind not in kinds:
        raise BadRequestError("素材类型不支持该操作")
    return media
