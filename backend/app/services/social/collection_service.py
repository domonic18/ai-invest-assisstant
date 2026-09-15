"""采集服务：遍历启用账号拉取新视频并组装 social_post 行。

职责边界：本服务只做「取数 + 行组装（含 ASR 转写降级）+ 账号簿记」，不写
social_post——行由 spider 的 PostgresCollector 以 (platform, video_id) 冲突键
幂等入库；账号 last_* 字段在此提交。通道级失败（风控/签名/结构漂移）向上
传播使任务置 FAILED（F-MON 告警），账号级失败（AccountInvalid）记账后继续。
"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.douyin import DouyinTransport, DouyinVideo, DouyinWebApi
from app.adapters.douyin.cookies import decrypt_jar_payload, is_cookie_usable
from app.adapters.douyin.exceptions import AccountInvalidError
from app.constants.social import SOCIAL_MAX_LIST_PAGES
from app.core.clock import utc_now
from app.models.account_quota import SystemSetting
from app.models.social import SocialAccount
from app.repositories.social import account_repository, post_repository
from app.services.social.asr_service import TranscribeOutcome, transcribe_from_url

logger = structlog.get_logger(__name__)

#: Cookie jar 池的 SystemSetting KV 键（管理端 Cookie 导入写，采集侧读）
COOKIE_SETTING_KEY = "social.douyin.cookie_jars"


async def load_cookie_jars(session: AsyncSession) -> list[str]:
    """读取 Cookie jar 池（Fernet 解密 + 可用性过滤；未配置返回空列表）。"""
    setting = await session.get(SystemSetting, COOKIE_SETTING_KEY)
    if setting is None or not isinstance(setting.value, str) or not setting.value:
        return []
    try:
        jars = decrypt_jar_payload(setting.value)
    except Exception:  # noqa: BLE001 —— 解密失败视同未配置
        logger.warning("social_cookie_decrypt_failed")
        return []
    return [jar for jar in jars if is_cookie_usable(jar)]


async def collect_all_accounts(
    session: AsyncSession, *, account_id: int | None = None
) -> list[dict[str, Any]]:
    """遍历启用账号逐个采集，返回待入库的 post 行（调用方负责入库）。

    Args:
        session: 数据库会话。
        account_id: 只采指定账号（手动补跑单账号用），缺省全部启用账号。

    Returns:
        social_post 行字典列表（含 ASR 转写字段）。
    """
    transport = DouyinTransport(cookies=await load_cookie_jars(session))
    accounts = await account_repository.list_accounts(session, active_only=True)
    if account_id is not None:
        accounts = [a for a in accounts if a.id == account_id]
    rows: list[dict[str, Any]] = []
    for account in accounts:
        try:
            rows.extend(await collect_account(session, transport, account))
        except AccountInvalidError as exc:
            await _record_account_error(session, account, str(exc))
    return rows


async def collect_account(
    session: AsyncSession,
    transport: DouyinTransport,
    account: SocialAccount,
) -> list[dict[str, Any]]:
    """采集单账号新视频（增量判新 + 上限续拉 + ASR），并提交账号簿记。

    库存判新用「已入库 video_id 集合 + last_post_at 地板」双保险；作品按时间
    倒序返回，新内容优先，毒丸与历史内容自然沉出续拉窗口。

    Raises:
        RiskControlError / SignatureError / StructureDriftError: 通道级失败，
            向上传播使本轮任务 FAILED。
        AccountInvalidError: 账号不可用（sec_uid 失效等）。
    """
    api = DouyinWebApi(transport)
    existing = set(await post_repository.list_video_ids(session, account.id))
    floor = account.last_post_at
    rows: list[dict[str, Any]] = []
    cursor = 0
    for _ in range(SOCIAL_MAX_LIST_PAGES):
        page = await api.get_user_posts(account.sec_uid, max_cursor=cursor)
        for video in page.videos:
            if video.video_id in existing:
                continue
            if floor is not None and video.published_at and video.published_at <= floor:
                continue
            if video.published_at is None:
                continue
            rows.append(await _build_post_row(session, account, video))
        if not page.has_more:
            break
        cursor = page.max_cursor
    _touch_account(account, rows)
    await session.commit()
    return rows


async def _build_post_row(
    session: AsyncSession, account: SocialAccount, video: DouyinVideo
) -> dict[str, Any]:
    """组装单条 post 行（口播转写失败按降级原因记账，不阻塞内容入库）。"""
    if video.play_url:
        outcome = await transcribe_from_url(session, video.play_url)
    else:
        outcome = TranscribeOutcome(None, None, "play_addr_missing")
    return {
        "account_id": account.id,
        "platform": account.platform,
        "video_id": video.video_id,
        "title": video.title,
        "caption": video.caption,
        "topic_tags": video.topic_tags,
        "cover_url": video.cover_url,
        "duration_seconds": video.duration_seconds,
        "published_at": video.published_at,
        "digg_count": video.digg_count,
        "comment_count": video.comment_count,
        "share_count": video.share_count,
        "transcript_status": "ok" if outcome.text else "missing",
        "transcript_text": outcome.text,
        "transcript_meta": outcome.meta if outcome.text else {"reason": outcome.reason},
    }


def _touch_account(account: SocialAccount, rows: list[dict[str, Any]]) -> None:
    """采集成功后的账号簿记（commit 由调用方完成）。"""
    account.last_collected_at = utc_now()
    if rows:
        account.last_post_at = max(row["published_at"] for row in rows)
    account.last_error = None
    account.last_error_at = None


async def _record_account_error(
    session: AsyncSession, account: SocialAccount, message: str
) -> None:
    """账号级失败记账（不停用，管理端诊断列可见；立即提交）。"""
    logger.warning(
        "social_account_collect_failed", account_id=account.id, error=message
    )
    account.last_error = message[:1000]
    account.last_error_at = utc_now()
    await session.commit()
