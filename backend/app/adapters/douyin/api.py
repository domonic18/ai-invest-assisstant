"""抖音 Web API 封装：用户主页 / 作品列表 / 短链展开，含 aweme 归一化与故障归因。

适配层依赖方向：api → transport/signing/cookies；本模块不依赖服务层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from app.adapters.douyin.exceptions import (
    AccountInvalidError,
    RiskControlError,
    StructureDriftError,
)
from app.adapters.douyin.transport import DouyinTransport

_PROFILE_PATH = "/aweme/v1/web/user/profile/other/"
_POSTS_PATH = "/aweme/v1/web/user/post/"

POSTS_PAGE_SIZE = 20

# 与桌面 Web 端一致的固定环境参数（参与签名，顺序保持稳定）
_COMMON_PARAMS: list[tuple[str, str]] = [
    ("device_platform", "webapp"),
    ("aid", "6383"),
    ("channel", "channel_pc_web"),
    ("update_version_code", "170400"),
    ("pc_client_type", "1"),
    ("pc_libra_divert", "Windows"),
    ("version_code", "290100"),
    ("version_name", "29.1.0"),
    ("cookie_enabled", "true"),
    ("screen_width", "1920"),
    ("screen_height", "1080"),
    ("browser_language", "zh-CN"),
    ("browser_platform", "Win32"),
    ("browser_name", "Edge"),
    ("browser_version", "130.0.0.0"),
    ("browser_online", "true"),
    ("engine_name", "Blink"),
    ("engine_version", "130.0.0.0"),
    ("os_name", "Windows"),
    ("os_version", "10"),
    ("cpu_core_num", "12"),
    ("device_memory", "8"),
    ("platform", "PC"),
    ("downlink", "10"),
    ("effective_type", "4g"),
    ("round_trip_time", "50"),
]


@dataclass(slots=True)
class DouyinProfile:
    """用户主页归一化结果。"""

    sec_uid: str
    nickname: str
    douyin_id: str | None = None
    signature: str | None = None
    avatar_url: str | None = None


@dataclass(slots=True)
class DouyinVideo:
    """作品归一化结果（与 social_post 落库字段对应）。"""

    video_id: str
    caption: str | None
    topic_tags: list[str] = field(default_factory=list)
    cover_url: str | None = None
    play_url: str | None = None
    duration_seconds: int | None = None
    published_at: datetime | None = None
    digg_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None

    @property
    def title(self) -> str | None:
        """标题取口播描述首行。"""
        if not self.caption:
            return None
        return self.caption.splitlines()[0][:500] or None


@dataclass(slots=True)
class DouyinPostsPage:
    """作品列表分页结果。"""

    videos: list[DouyinVideo]
    has_more: bool
    max_cursor: int


def _build_params(extra: list[tuple[str, str]]) -> str:
    return urlencode(_COMMON_PARAMS + extra)


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_aweme(raw: dict) -> DouyinVideo | None:
    """把单条 aweme 归一化；缺 aweme_id 的条目丢弃。

    Args:
        raw: aweme_list 中的原始条目。

    Returns:
        归一化结果；无法归一化返回 None。
    """
    video_id = raw.get("aweme_id")
    if not video_id:
        return None
    video = raw.get("video") or {}
    cover = (video.get("cover") or {}).get("url_list") or []
    play_addr = (video.get("play_addr") or {}).get("url_list") or []
    statistics = raw.get("statistics") or {}
    create_time = _to_int(raw.get("create_time"))
    duration_ms = _to_int(video.get("duration"))
    topic_tags = [
        tag
        for tag in (
            item.get("hashtag_name")
            for item in raw.get("text_extra") or []
            if isinstance(item, dict)
        )
        if tag
    ]
    return DouyinVideo(
        video_id=str(video_id),
        caption=raw.get("desc") or None,
        topic_tags=topic_tags,
        cover_url=cover[0] if cover else None,
        play_url=play_addr[0] if play_addr else None,
        duration_seconds=max(duration_ms // 1000, 0) if duration_ms else None,
        published_at=(
            datetime.fromtimestamp(create_time, tz=timezone.utc) if create_time else None
        ),
        digg_count=_to_int(statistics.get("digg_count")),
        comment_count=_to_int(statistics.get("comment_count")),
        share_count=_to_int(statistics.get("share_count")),
    )


class DouyinWebApi:
    """抖音 Web 接口客户端（签名/ Cookie 由 transport 承担）。"""

    def __init__(self, transport: DouyinTransport) -> None:
        self._transport = transport

    async def get_user_profile(self, sec_uid: str) -> DouyinProfile:
        """拉取用户主页。

        Args:
            sec_uid: 用户 sec_uid。

        Returns:
            主页归一化结果。

        Raises:
            AccountInvalidError: 账号不存在/注销/转私密（非零 status_code 且无 user，
                或 user 结构为空）。
            StructureDriftError: 顶层结构变化。
            RiskControlError: 风控/频控。
        """
        params = _build_params([("sec_user_id", sec_uid), ("publish_video_strategy_type", "2")])
        data = await self._transport.get_json(_PROFILE_PATH, params)
        if not isinstance(data, dict):
            raise StructureDriftError("profile 响应不是对象")

        user = data.get("user")
        if data.get("status_code") and not user:
            raise AccountInvalidError(f"sec_uid={sec_uid} status_code={data.get('status_code')}")
        if "user" not in data:
            raise StructureDriftError(f"profile 缺少 user 键: {str(data)[:200]}")
        if not isinstance(user, dict) or not user.get("sec_uid"):
            raise AccountInvalidError(f"sec_uid={sec_uid} 主页为空或转私密")
        return DouyinProfile(
            sec_uid=str(user.get("sec_uid")),
            nickname=str(user.get("nickname") or sec_uid),
            douyin_id=user.get("unique_id") or None,
            signature=user.get("signature") or None,
            avatar_url=((user.get("avatar_thumb") or {}).get("url_list") or [None])[0],
        )

    async def get_user_posts(
        self, sec_uid: str, max_cursor: int = 0, count: int = POSTS_PAGE_SIZE
    ) -> DouyinPostsPage:
        """拉取作品列表一页。

        Args:
            sec_uid: 用户 sec_uid。
            max_cursor: 翻页游标（上一页返回值，首页传 0）。
            count: 单页条数上限。

        Returns:
            分页归一化结果（无效条目已过滤）。

        Raises:
            StructureDriftError: 缺少 aweme_list 键。
            RiskControlError: 风控/频控（含非零 status_code）。
        """
        params = _build_params(
            [
                ("sec_user_id", sec_uid),
                ("max_cursor", str(max_cursor)),
                ("locate_query", "false"),
                ("show_live_replay_strategy", "1"),
                ("need_time_list", "1"),
                ("time_list_query", "0"),
                ("whale_cut_token", ""),
                ("cut_version", "1"),
                ("count", str(count)),
                ("publish_video_strategy_type", "2"),
                ("from_user_page", "1"),
                ("support_h265", "1"),
                ("support_dash", "0"),
            ]
        )
        data = await self._transport.get_json(_POSTS_PATH, params)
        if not isinstance(data, dict) or "aweme_list" not in data:
            raise StructureDriftError(f"posts 缺少 aweme_list 键: {str(data)[:200]}")
        if data.get("status_code"):
            raise RiskControlError(
                f"posts status_code={data.get('status_code')} {data.get('status_msg', '')}"
            )
        aweme_list = data.get("aweme_list") or []
        videos = [
            video
            for video in (normalize_aweme(item) for item in aweme_list if isinstance(item, dict))
            if video is not None
        ]
        return DouyinPostsPage(
            videos=videos,
            has_more=bool(data.get("has_more")),
            max_cursor=_to_int(data.get("max_cursor")) or 0,
        )

    async def expand_short_link(self, url: str) -> str:
        """展开分享短链，取跳转目标地址。"""
        return await self._transport.resolve_redirect(url)
