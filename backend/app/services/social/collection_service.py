"""采集服务：遍历启用账号拉取新视频，两阶段落库（listing shell 行 → 逐条转写回写）。

阶段一 listing 秒级完成：新视频 shell 行（含封面/元数据，transcript_status='pending'）
立即以 (platform, video_id) DO NOTHING 入库并推进账号水位——行已持久后再推进水位，
任务中途被杀不丢单；阶段二逐条下载/ASR 并即时回写（每条一 commit），进度可在
采集日志与作品排查面板实时观察，中断后重触发自动续传剩余 pending。
通道级失败（风控/签名/结构漂移）向上传播使任务置 FAILED（F-MON 告警），
账号级失败（AccountInvalid）记账后继续。
"""

from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.douyin import DouyinTransport, DouyinVideo, DouyinWebApi
from app.adapters.douyin.cookies import (
    decrypt_jar_payload,
    encrypt_jar_payload,
    is_cookie_usable,
)
from app.adapters.douyin.exceptions import AccountInvalidError
from app.adapters.douyin.signer_client import (
    DouyinSignerClient,
    SignerUnavailableError,
    build_signer,
)
from app.constants.social import (
    SOCIAL_BACKFILL_MAX_LIST_PAGES,
    SOCIAL_MAX_LIST_PAGES,
)
from app.core.clock import now_cn, utc_now
from app.core.config import get_settings
from app.core.exceptions import BadRequestError
from app.models.account_quota import SystemSetting
from app.models.collector_log import CollectorLog
from app.models.social import SocialAccount
from app.repositories.social import account_repository, post_repository
from app.schemas.social import (
    AsrStatusResponse,
    DouyinStatusResponse,
    SignerStatusResponse,
    SocialStatusResponse,
)
from app.services.admin.audit_service import record_audit
from app.services.social import asr_config_service
from app.services.social.asr_service import TranscribeOutcome, transcribe_from_url

logger = structlog.get_logger(__name__)

#: Cookie jar 池的 SystemSetting KV 键（管理端 Cookie 导入写，采集侧读）
COOKIE_SETTING_KEY = "social.douyin.cookie_jars"

#: 采集健康聚合的渠道身份（collector_log 按 (task_type, source) 查询）
_SOCIAL_TASK_TYPE = "social-video"
_SOCIAL_SOURCE = "douyin"

#: 完整浏览器 Cookie 的最少键值对数：作品接口对 ttwid-only/双键薄 jar 返回 200 空响应
#: （2026-09-16 走查实测），完整 Cookie 动辄数十键，3 为宽松下限
MIN_COOKIE_PAIRS = 3

AUDIT_COOKIE_IMPORT = "social.cookie.import"


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


def _cookie_value(cookie: str, name: str) -> str | None:
    """取 cookie 串中指定键的值（无则 None）。"""
    for part in cookie.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key == name:
            return value
    return None


async def import_cookie(
    session: AsyncSession, raw: str, *, actor_id: int, ip: str | None = None
) -> int:
    """手动导入 Cookie 串（ttwid 必需；按 ttwid 去重合并入 jar 池，Fernet 落库，写审计）。

    Raises:
        BadRequestError: Cookie 缺少 ttwid，或键值对数低于完整浏览器 Cookie 下限
            （薄 jar 过作品接口风控会拿到 200 空响应，混入池会轮换污染采集）。
    """
    cleaned = raw.strip()
    if cleaned.lower().startswith("cookie:"):
        cleaned = cleaned[len("Cookie:") :].strip()
    cleaned = "; ".join(part.strip() for part in cleaned.split(";") if part.strip())
    if not is_cookie_usable(cleaned):
        raise BadRequestError("Cookie 缺少 ttwid，请从已登录浏览器完整复制 Cookie 串")
    pair_count = len(cleaned.split(";"))
    if pair_count < MIN_COOKIE_PAIRS:
        raise BadRequestError(
            f"Cookie 只有 {pair_count} 组键值——作品接口要求完整浏览器身份，"
            "请在 douyin.com 页面按 F12 → 网络 → 点首个请求 → 复制请求标头中 Cookie 整串"
        )

    incoming_ttwid = _cookie_value(cleaned, "ttwid")
    jars = [
        jar
        for jar in await load_cookie_jars(session)
        if _cookie_value(jar, "ttwid") != incoming_ttwid
    ]
    jars.append(cleaned)

    setting = await session.get(SystemSetting, COOKIE_SETTING_KEY)
    if setting is None:
        setting = SystemSetting(key=COOKIE_SETTING_KEY, value="")
        session.add(setting)
    setting.value = encrypt_jar_payload(jars)
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_COOKIE_IMPORT,
        detail={"cookieJars": len(jars)},
        ip=ip,
    )
    await session.commit()
    return len(jars)


async def collect_all_accounts(
    session: AsyncSession,
    *,
    account_id: int | None = None,
    backfill: bool = False,
) -> dict[str, int]:
    """遍历启用账号逐个采集，返回汇总统计。

    Args:
        session: 数据库会话。
        account_id: 只采指定账号（手动补跑单账号用），缺省全部启用账号。
        backfill: 回填模式——忽略增量地板、放宽翻页上限（见 collect_account）。

    Returns:
        {listed: 新发现条数, resumed: 续传条数, ok: 转写成功条数,
        degraded: 降级条数}。
    """
    transport = DouyinTransport(
        cookies=await load_cookie_jars(session),
        signer=build_signer(get_settings().douyin_signer_url),
    )
    accounts = await account_repository.list_accounts(session, active_only=True)
    if account_id is not None:
        accounts = [a for a in accounts if a.id == account_id]
    stats = {"listed": 0, "resumed": 0, "ok": 0, "degraded": 0}
    for account in accounts:
        try:
            result = await collect_account(
                session, transport, account, backfill=backfill
            )
        except AccountInvalidError as exc:
            await _record_account_error(session, account, str(exc))
            continue
        for key in stats:
            stats[key] += result[key]
    return stats


async def collect_account(
    session: AsyncSession,
    transport: DouyinTransport,
    account: SocialAccount,
    *,
    backfill: bool = False,
) -> dict[str, int]:
    """采集单账号（两阶段）：listing shell 行入库 + 逐条 ASR 回写。

    库存判新用「已入库 video_id 集合 + last_post_at 地板」双保险；作品按时间
    倒序返回，新内容优先，毒丸与历史内容自然沉出续拉窗口。阶段一提交后
    （shell 行已持久），水位推进才安全——任务中途被杀只丢转写进度，不丢内容，
    重触发时 pending 行经 listing 窗口恢复 play_url 续传。

    回填模式（backfill=True）忽略地板并放宽翻页上限，拉取存量历史视频；
    幂等由 video_id 去重保证，可重复触发；成功后地板随 max(published_at)
    自然推进到最新作品。

    Returns:
        {listed, resumed, ok, degraded}（语义见 collect_all_accounts）。

    Raises:
        RiskControlError / SignatureError / StructureDriftError: 通道级失败，
            向上传播使本轮任务 FAILED。
        AccountInvalidError: 账号不可用（sec_uid 失效等）。
    """
    api = DouyinWebApi(transport)
    existing = set(await post_repository.list_video_ids(session, account.id))
    floor = None if backfill else account.last_post_at
    max_pages = (
        SOCIAL_BACKFILL_MAX_LIST_PAGES if backfill else SOCIAL_MAX_LIST_PAGES
    )
    seen: dict[str, DouyinVideo] = {}
    new_videos: list[DouyinVideo] = []
    cursor = 0
    for _ in range(max_pages):
        page = await api.get_user_posts(account.sec_uid, max_cursor=cursor)
        for video in page.videos:
            if video.video_id in seen:  # 单轮去重：异常分页下不重复处理同一视频
                continue
            seen[video.video_id] = video
            if video.video_id in existing:
                continue
            if floor is not None and video.published_at and video.published_at <= floor:
                continue
            if video.published_at is None:
                continue
            new_videos.append(video)
        if not page.has_more:
            break
        cursor = page.max_cursor

    # 阶段一：shell 行立即持久化（pending），水位随行落库推进（不丢单的关键次序）
    if new_videos:
        await post_repository.insert_posts(
            session, [_build_shell_row(account, video) for video in new_videos]
        )
        _touch_account(
            account,
            [{"published_at": video.published_at} for video in new_videos],
        )
    else:
        account.last_collected_at = utc_now()
        account.last_error = None
        account.last_error_at = None
    await session.commit()

    # 阶段二：逐条转写回写；库内 pending 行经本次 listing 窗口恢复 play_url 续传
    pending_ids = set(await post_repository.list_pending_video_ids(session, account.id))
    new_ids = {video.video_id for video in new_videos}
    targets = list(new_videos) + [
        seen[video_id] for video_id in pending_ids if video_id in seen and video_id not in new_ids
    ]
    ok = degraded = 0
    for done, video in enumerate(targets, start=1):
        if video.play_url:
            outcome = await transcribe_from_url(session, video.play_url)
        else:
            outcome = TranscribeOutcome(None, None, "play_addr_missing")
        try:
            await post_repository.update_transcript(
                session,
                account.platform,
                video.video_id,
                status="ok" if outcome.text else "missing",
                text=outcome.text,
                meta=outcome.meta if outcome.text else {"reason": outcome.reason},
            )
            await session.commit()
        except Exception as exc:  # noqa: BLE001 —— 单条回写失败不停轮，下轮续传兜底
            await session.rollback()
            degraded += 1
            logger.warning(
                "social_transcribe_write_failed",
                account_id=account.id,
                video_id=video.video_id,
                error=str(exc),
            )
            continue
        if outcome.text:
            ok += 1
        else:
            degraded += 1
        logger.info(
            "social_transcribe_progress",
            account_id=account.id,
            done=done,
            total=len(targets),
            video_id=video.video_id,
            status="ok" if outcome.text else f"degraded:{outcome.reason}",
        )
    return {
        "listed": len(new_videos),
        "resumed": len(targets) - len(new_videos),
        "ok": ok,
        "degraded": degraded,
    }


def _build_shell_row(account: SocialAccount, video: DouyinVideo) -> dict[str, Any]:
    """组装 listing 阶段 shell 行（元数据齐备，转写置 pending 待阶段二回写）。"""
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
        "transcript_status": "pending",
        "transcript_text": None,
        "transcript_meta": {"reason": "pending"},
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


async def get_status_aggregate(session: AsyncSession) -> SocialStatusResponse:
    """管理端采集健康聚合：Cookie 池 + 今日采集量 + ASR 记账 + signer 探测。"""
    day_start = now_cn().replace(hour=0, minute=0, second=0, microsecond=0)

    cookie_setting = await session.get(SystemSetting, COOKIE_SETTING_KEY)
    jars = await load_cookie_jars(session)

    today_collected = (
        await session.execute(
            select(func.coalesce(func.sum(CollectorLog.records_count), 0)).where(
                CollectorLog.task_name == _SOCIAL_TASK_TYPE,
                CollectorLog.source == _SOCIAL_SOURCE,
                CollectorLog.status == "success",
                CollectorLog.started_at >= day_start,
            )
        )
    ).scalar_one()
    today_failed = (
        await session.execute(
            select(func.count())
            .select_from(CollectorLog)
            .where(
                CollectorLog.task_name == _SOCIAL_TASK_TYPE,
                CollectorLog.source == _SOCIAL_SOURCE,
                CollectorLog.status == "failed",
                CollectorLog.started_at >= day_start,
            )
        )
    ).scalar_one()
    latest_error = (
        await session.execute(
            select(CollectorLog.error_msg)
            .where(
                CollectorLog.task_name == _SOCIAL_TASK_TYPE,
                CollectorLog.source == _SOCIAL_SOURCE,
                CollectorLog.status == "failed",
            )
            .order_by(CollectorLog.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    transcript_counts = await post_repository.count_transcripts_since(session, day_start)

    config = await asr_config_service.get_or_create_config(session)
    return SocialStatusResponse(
        douyin=DouyinStatusResponse(
            cookie_configured=bool(jars),
            cookie_jars_available=len(jars),
            last_bootstrap_at=cookie_setting.updated_at if cookie_setting else None,
            signature_warning=bool(latest_error and "SignatureError" in str(latest_error)),
            today_collected=int(today_collected or 0),
            today_failed=int(today_failed or 0),
        ),
        asr=AsrStatusResponse(
            enabled=config.enabled,
            configured=bool(config.api_key_encrypted),
            today_transcribed=transcript_counts.get("ok", 0),
            today_degraded=transcript_counts.get("missing", 0),
            today_pending=transcript_counts.get("pending", 0),
        ),
        signer=await _probe_signer(),
    )


async def _probe_signer() -> SignerStatusResponse:
    """探测签名 sidecar（短超时；异常降级为 reachable=False，不影响 status 可用）。"""
    url = get_settings().douyin_signer_url
    if not url:
        return SignerStatusResponse(enabled=False, reachable=False)
    try:
        health = await DouyinSignerClient(url).health()
    except SignerUnavailableError as exc:
        return SignerStatusResponse(enabled=True, reachable=False, detail=str(exc)[:300])
    reachable = health.get("status") == "ok"
    warm_slots = health.get("warm_slots")
    return SignerStatusResponse(
        enabled=True,
        reachable=reachable,
        warm_slots=warm_slots if reachable and isinstance(warm_slots, int) else None,
        detail=None if reachable else str(health.get("detail") or health.get("status")),
    )
