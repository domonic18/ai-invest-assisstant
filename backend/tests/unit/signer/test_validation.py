"""签名请求边界校验测试。"""

import pytest

from app.signer.validation import (
    SignRequestError,
    parse_cookie_header,
    validate_path,
    validate_query,
    validate_user_agent,
)

pytestmark = pytest.mark.unit


class TestValidatePath:
    def test_accepts_whitelisted_prefix(self) -> None:
        assert validate_path("/aweme/v1/web/aweme/post/") == "/aweme/v1/web/aweme/post/"

    @pytest.mark.parametrize(
        "path",
        [
            "",
            "aweme/v1/web/aweme/post/",
            "https://www.douyin.com/aweme/v1/web/aweme/post/",
            "/aweme/v1/other/",
            "/aweme/v1/web/aweme/post/ x",
        ],
    )
    def test_rejects_invalid_shapes(self, path: str) -> None:
        with pytest.raises(SignRequestError):
            validate_path(path)


class TestValidateQuery:
    def test_accepts_urlencoded_query(self) -> None:
        assert validate_query("aid=6383&sec_user_id=MS4wLjABAAAA") is not None

    @pytest.mark.parametrize("query", ["", "aid=6383 sec=1"])
    def test_rejects_empty_or_spaced(self, query: str) -> None:
        with pytest.raises(SignRequestError):
            validate_query(query)


def test_validate_user_agent_rejects_blank() -> None:
    with pytest.raises(SignRequestError):
        validate_user_agent("   ")


class TestParseCookieHeader:
    def test_parses_pairs_with_domain(self) -> None:
        cookies = parse_cookie_header("ttwid=abc; s_v_web_id=xyz")
        assert cookies == [
            {"name": "ttwid", "value": "abc", "domain": ".douyin.com", "path": "/"},
            {"name": "s_v_web_id", "value": "xyz", "domain": ".douyin.com", "path": "/"},
        ]

    def test_drops_empty_and_malformed_pairs(self) -> None:
        cookies = parse_cookie_header("; ttwid=; noeq; ok=1")
        assert [c["name"] for c in cookies] == ["ok"]

    def test_all_empty_rejected(self) -> None:
        with pytest.raises(SignRequestError):
            parse_cookie_header("; ; =x")
