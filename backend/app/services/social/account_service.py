"""追踪账号服务：sec_uid 解析与账号 CRUD（管理端「社媒追踪」页）。

sec_uid 支持四种输入形态：裸 sec_uid / 主页长链 / 分享短链 / 带文案的分享口令，
统一正则提取；短链先经适配层 302 展开再提取。
"""

import re

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.douyin import DouyinTransport, DouyinWebApi
from app.constants.social import (
    SOCIAL_MIN_POLL_INTERVAL_MINUTES,
    SocialCategory,
    SocialPlatform,
)
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.social import SocialAccount
from app.repositories.social import account_repository

logger = structlog.get_logger(__name__)

#: 抖音 sec_uid 形态：MS4wLjABAAAA 前缀 + base64 变体字符
_SEC_UID_PATTERN = re.compile(r"MS4wLjABAAAA[A-Za-z0-9_-]{20,}")

_VALID_CATEGORIES = {c.value for c in SocialCategory}
_VALID_PLATFORMS = {p.value for p in SocialPlatform}


def extract_sec_uid(text: str) -> str | None:
    """从任意文本（链接/分享口令/裸 sec_uid）提取抖音 sec_uid。"""
    match = _SEC_UID_PATTERN.search(text)
    return match.group(0) if match else None


async def resolve_sec_uid(raw: str) -> str:
    """归一解析 sec_uid；短链先展开（302 不带 Cookie 不签名）。

    Args:
        raw: 用户粘贴的任意形态输入。

    Returns:
        解析出的 sec_uid。

    Raises:
        BadRequestError: 无法从输入解析出 sec_uid。
    """
    sec_uid = extract_sec_uid(raw)
    if sec_uid:
        return sec_uid
    expanded = await _expand_short_link(raw.strip())
    sec_uid = extract_sec_uid(expanded)
    if not sec_uid:
        raise BadRequestError("无法从输入解析抖音 sec_uid，请粘贴主页链接或 sec_uid")
    return sec_uid


async def _expand_short_link(url: str) -> str:
    """分享短链展开；展开失败返回空串（按解析失败处理）。"""
    transport = DouyinTransport()
    try:
        return await DouyinWebApi(transport).expand_short_link(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("social_sec_uid_expand_failed", url=url, error=str(exc))
        return ""


async def create_account(
    session: AsyncSession,
    *,
    platform: str,
    sec_uid_or_url: str,
    alias: str,
    category: str,
    poll_interval_minutes: int,
    remark: str | None = None,
) -> SocialAccount:
    """登记追踪账号（sec_uid 自动解析，重复登记 409）。

    Raises:
        BadRequestError: 平台/分类非法或轮询间隔低于下限或解析失败。
        ConflictError: (platform, sec_uid) 已登记。
    """
    if platform not in _VALID_PLATFORMS:
        raise BadRequestError(f"不支持的平台: {platform}")
    if category not in _VALID_CATEGORIES:
        raise BadRequestError(f"未知的账号分类: {category}")
    if poll_interval_minutes < SOCIAL_MIN_POLL_INTERVAL_MINUTES:
        raise BadRequestError(
            f"轮询间隔不能低于 {SOCIAL_MIN_POLL_INTERVAL_MINUTES} 分钟"
        )
    sec_uid = await resolve_sec_uid(sec_uid_or_url)
    existing = await account_repository.get_by_sec_uid(session, platform, sec_uid)
    if existing is not None:
        raise ConflictError(f"该账号已登记：{existing.alias}")
    account = SocialAccount(
        platform=platform,
        sec_uid=sec_uid,
        alias=alias,
        category=category,
        poll_interval_minutes=poll_interval_minutes,
        remark=remark,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def update_account(
    session: AsyncSession, account_id: int, **fields: str | bool | int | None
) -> SocialAccount:
    """更新账号（alias/category/poll_interval_minutes/is_active/remark）。

    Raises:
        NotFoundError: 账号不存在。
        BadRequestError: 分类非法或轮询间隔低于下限。
    """
    account = await account_repository.get(session, account_id)
    if account is None:
        raise NotFoundError("追踪账号不存在")
    category = fields.get("category")
    if category is not None and category not in _VALID_CATEGORIES:
        raise BadRequestError(f"未知的账号分类: {category}")
    interval = fields.get("poll_interval_minutes")
    if isinstance(interval, int) and interval < SOCIAL_MIN_POLL_INTERVAL_MINUTES:
        raise BadRequestError(
            f"轮询间隔不能低于 {SOCIAL_MIN_POLL_INTERVAL_MINUTES} 分钟"
        )
    for key in ("alias", "category", "poll_interval_minutes", "is_active", "remark"):
        if key in fields:
            setattr(account, key, fields[key])
    await session.commit()
    await session.refresh(account)
    return account


async def delete_account(session: AsyncSession, account_id: int) -> None:
    """删除账号（social_post 级联删除；历史判断随 post 级联清除）。

    Raises:
        NotFoundError: 账号不存在。
    """
    account = await account_repository.get(session, account_id)
    if account is None:
        raise NotFoundError("追踪账号不存在")
    await session.delete(account)
    await session.commit()
