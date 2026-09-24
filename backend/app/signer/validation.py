"""签名请求边界校验：路径白名单与 Cookie 串解析。"""

from __future__ import annotations

ALLOWED_PATH_PREFIXES = ("/aweme/v1/web/",)


class SignRequestError(ValueError):
    """请求形状不合法（映射 HTTP 4xx，调用方不应重试）。"""


def validate_path(path: str) -> str:
    """校验待签名接口路径：仅接受抖音 Web API 白名单前缀。

    Raises:
        SignRequestError: 路径为空、带 scheme/host 或不在白名单内。
    """
    if not path.startswith("/") or "://" in path or " " in path:
        raise SignRequestError(f"非法路径形状: {path[:80]!r}")
    if not any(path.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES):
        raise SignRequestError(f"路径不在白名单内: {path[:80]!r}")
    return path


def validate_query(query: str) -> str:
    """query 串必须非空且不含空格（由调用方 urlencode 后拼接）。"""
    if not query or " " in query:
        raise SignRequestError("query 须为 urlencode 后的非空串")
    return query


def validate_user_agent(user_agent: str) -> str:
    if not user_agent.strip():
        raise SignRequestError("user_agent 不能为空")
    return user_agent


def parse_cookie_header(cookie: str) -> list[dict[str, str]]:
    """``k=v; k2=v2`` 串 → Playwright ``add_cookies`` 形状。

    空名/空值对丢弃；整批无可用对时抛 ``SignRequestError``
    （Playwright 对全空列表是 no-op，装不出身份，宁可早失败）。
    """
    cookies: list[dict[str, str]] = []
    for pair in cookie.split(";"):
        name, sep, value = pair.strip().partition("=")
        if not sep or not name or not value:
            continue
        cookies.append({"name": name, "value": value, "domain": ".douyin.com", "path": "/"})
    if not cookies:
        raise SignRequestError("Cookie 串无可解析键值对")
    return cookies
