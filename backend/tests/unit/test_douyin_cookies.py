"""抖音 Cookie 双轨测试：Set-Cookie 解析、合并、可用性判定、Fernet 加密落库、首页自举。"""

from typing import Any

import pytest

from app.adapters.douyin.cookies import (
    bootstrap_cookies,
    decrypt_jar_payload,
    encrypt_jar_payload,
    is_cookie_usable,
    merge_cookies,
    parse_set_cookie_header,
)
from app.adapters.douyin.exceptions import RiskControlError


class TestSetCookieParsing:
    def test_single_header(self) -> None:
        assert parse_set_cookie_header(
            "ttwid=1xYz; Path=/; Domain=.douyin.com; Max-Age=31536000"
        ) == {"ttwid": "1xYz"}

    def test_no_value_ignored(self) -> None:
        assert parse_set_cookie_header("HttpOnly") == {}

    def test_merge_overrides_and_preserves(self) -> None:
        merged = merge_cookies(
            "ttwid=old; msToken=abc", {"ttwid": "new", "sid_guard": "guard1"}
        )
        assert merged == "ttwid=new; msToken=abc; sid_guard=guard1"

    def test_usable_requires_ttwid(self) -> None:
        assert is_cookie_usable("ttwid=1; other=2")
        assert not is_cookie_usable("sessionid=1")
        assert not is_cookie_usable(None)


class TestJarPayloadEncryption:
    def test_roundtrip(self) -> None:
        jars = ["ttwid=a; sessionid=x", "ttwid=b"]
        token = encrypt_jar_payload(jars)
        assert token != str(jars)
        assert decrypt_jar_payload(token) == jars

    def test_corrupted_payload_returns_empty(self) -> None:
        assert decrypt_jar_payload("not-a-fernet-token") == []


class FakeHeaders:
    def __init__(self, set_cookies: list[str]) -> None:
        self._set_cookies = set_cookies

    def multi_items(self) -> list[tuple[str, str]]:
        return [("content-type", "text/html")] + [
            ("set-cookie", value) for value in self._set_cookies
        ]


class FakeBootstrapSession:
    def __init__(self, set_cookies: list[str]) -> None:
        self.headers = FakeHeaders(set_cookies)

    async def get(self, url: str, **kwargs: Any) -> Any:
        return self

    async def __aenter__(self) -> "FakeBootstrapSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


class TestBootstrap:
    async def test_collects_ttwid(self) -> None:
        session = FakeBootstrapSession(
            [
                "ttwid=1xYz; Path=/; Domain=.douyin.com",
                "msToken=abc; Path=/",
                "sid_guard=guard; Max-Age=0",  # 过期指令仍收值（简化口径）
            ]
        )
        cookie = await bootstrap_cookies(
            session_factory=lambda: session,
        )
        assert cookie == "ttwid=1xYz; msToken=abc; sid_guard=guard"

    async def test_missing_ttwid_raises_risk_control(self) -> None:
        session = FakeBootstrapSession(["msToken=abc; Path=/"])
        with pytest.raises(RiskControlError, match="ttwid"):
            await bootstrap_cookies(session_factory=lambda: session)
