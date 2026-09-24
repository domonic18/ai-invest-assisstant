"""抖音 Cookie 双轨：首页自举 + 手动导入。

本模块只提供纯 helper 与自举调用；Fernet 加密落库（system_setting）由服务层负责。
手动导入优先级高于自举：服务层把导入 jar 与自举 jar 一并交给 transport 轮换。
"""

from __future__ import annotations

import json
from typing import Any

from app.adapters.douyin.exceptions import RiskControlError
from app.adapters.douyin.signing import DEFAULT_USER_AGENT
from app.core.config import get_settings
from app.utils.crypto import decrypt_token, encrypt_token

# 可用性判定关键 cookie：ttwid 是 Web 接口刚需
ESSENTIAL_COOKIE_KEY = "ttwid"

JAR_PAYLOAD_VERSION = 1


def parse_set_cookie_header(header: str) -> dict[str, str]:
    """解析单条 Set-Cookie 头为 ``{name: value}``（取首个 k=v 属性段）。"""
    first_segment = header.split(";", 1)[0].strip()
    if "=" not in first_segment:
        return {}
    name, _, value = first_segment.partition("=")
    name = name.strip()
    if not name:
        return {}
    return {name: value.strip()}


def merge_cookies(existing: str | None, additions: dict[str, str]) -> str:
    """合并 cookie 串与新增键值（新增覆盖同名）。"""
    merged: dict[str, str] = {}
    for part in (existing or "").split(";"):
        name, sep, value = part.strip().partition("=")
        if sep:
            merged[name] = value
    merged.update(additions)
    return "; ".join(f"{name}={value}" for name, value in merged.items())


def is_cookie_usable(cookie: str | None) -> bool:
    """是否包含 ttwid 关键 cookie（失效检测的快速口径）。"""
    return f"{ESSENTIAL_COOKIE_KEY}=" in (cookie or "")


def encrypt_jar_payload(cookies: list[str]) -> str:
    """jar 池序列化为 Fernet 密文（落 system_setting 前调用）。"""
    payload = {"version": JAR_PAYLOAD_VERSION, "jars": cookies}
    return encrypt_token(json.dumps(payload, ensure_ascii=False))


def decrypt_jar_payload(token: str) -> list[str]:
    """解密 jar 池密文；损坏视为无 cookie（返回空列表，不阻断服务启动）。"""
    try:
        payload = json.loads(decrypt_token(token))
        jars = payload.get("jars", [])
        return [str(item) for item in jars if item]
    except Exception:  # noqa: BLE001 —— 密文损坏/密钥轮换后旧数据
        return []


def _extract_set_cookies(headers: Any) -> list[str]:
    try:
        items: list[tuple[str, str]] = list(headers.multi_items())
    except AttributeError:
        items = list(headers.items())
    return [value for name, value in items if name.lower() == "set-cookie"]


async def bootstrap_cookies(
    user_agent: str | None = None,
    session_factory: Any | None = None,
) -> str:
    """访问抖音首页自举 Cookie（ttwid 等）。

    Args:
        user_agent: 自定义 UA（与 transport 一致可降低风控关联性）。
        session_factory: 可注入会话工厂（测试用）。

    Returns:
        合并后的 cookie 串。

    Raises:
        RiskControlError: 首页未返回 ttwid（自举失败）。
    """
    if session_factory is None:
        from curl_cffi.requests import AsyncSession

        def session_factory() -> Any:
            return AsyncSession(impersonate="chrome")

    settings = get_settings()
    async with session_factory() as session:
        response = await session.get(
            f"{settings.douyin_base_url}/",
            headers={"User-Agent": user_agent or DEFAULT_USER_AGENT},
            timeout=settings.douyin_bootstrap_timeout,
        )
    merged: dict[str, str] = {}
    for header in _extract_set_cookies(getattr(response, "headers", {})):
        merged.update(parse_set_cookie_header(header))
    cookie = merge_cookies(None, merged)
    if not is_cookie_usable(cookie):
        raise RiskControlError("首页自举未获得 ttwid")
    return cookie
