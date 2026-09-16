"""抖音 Web API 封装测试：aweme 归一化、结构巨变/账号失效/风控/签名归因、jar 轮换。"""

from typing import Any

import pytest

from app.adapters.douyin.api import DouyinWebApi, normalize_aweme
from app.adapters.douyin.exceptions import (
    AccountInvalidError,
    RiskControlError,
    SignatureError,
    StructureDriftError,
)
from app.adapters.douyin.signing import generate_fingerprint
from app.adapters.douyin.transport import DouyinTransport

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: "dict[str, Any] | str | None" = None,
        headers: "dict[str, str] | None" = None,
    ) -> None:
        self.status_code = status_code
        if isinstance(payload, str):
            self.text = payload
        else:
            import json

            self.text = json.dumps(payload or {})
        self.headers = headers or {}


class FakeSession:
    def __init__(self, responses: "list[FakeResponse]") -> None:
        self._responses = responses
        self.requested_urls: list[str] = []
        self.requested_headers: list[dict[str, str]] = []

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.requested_urls.append(url)
        self.requested_headers.append(kwargs.get("headers") or {})
        return self._responses.pop(0)

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


def make_transport(responses: "list[FakeResponse]") -> tuple[DouyinTransport, FakeSession]:
    session = FakeSession(responses)
    transport = DouyinTransport(
        cookies=["ttwid=abc; sessionid=xyz"],
        fingerprint=generate_fingerprint(),
        session_factory=lambda: session,
    )
    return transport, session


def make_api(responses: "list[FakeResponse]") -> tuple[DouyinWebApi, FakeSession]:
    transport, session = make_transport(responses)
    return DouyinWebApi(transport), session


AWEME_FULL = {
    "aweme_id": "7301234567890123456",
    "desc": "看好新能源板块\n评论区聊",
    "create_time": 1757879400,
    "text_extra": [
        {"hashtag_name": "A股"},
        {"hashtag_id": 1},  # 无名称，忽略
        {"hashtag_name": "新能源"},
    ],
    "video": {
        "cover": {"url_list": ["https://p3.douyinpic.com/cover.jpeg"]},
        "duration": 152000,
    },
    "statistics": {"digg_count": 1200, "comment_count": 88, "share_count": 45},
}

AWEME_SPARSE = {"aweme_id": "7301234567890123457"}


class TestNormalizeAweme:
    def test_full_mapping(self) -> None:
        video = normalize_aweme(AWEME_FULL)
        assert video is not None
        assert video.video_id == "7301234567890123456"
        assert video.caption == "看好新能源板块\n评论区聊"
        assert video.title == "看好新能源板块"
        assert video.topic_tags == ["A股", "新能源"]
        assert video.cover_url == "https://p3.douyinpic.com/cover.jpeg"
        assert video.duration_seconds == 152
        assert video.published_at is not None
        assert video.published_at.isoformat().startswith("2025-09-14T19:50")
        assert video.digg_count == 1200
        assert video.comment_count == 88
        assert video.share_count == 45

    def test_sparse_fields_default_null(self) -> None:
        video = normalize_aweme(AWEME_SPARSE)
        assert video is not None
        assert video.caption is None
        assert video.title is None
        assert video.topic_tags == []
        assert video.cover_url is None
        assert video.duration_seconds is None
        assert video.published_at is None
        assert video.digg_count is None

    def test_missing_id_dropped(self) -> None:
        assert normalize_aweme({"desc": "无 id"}) is None


class TestPostsEndpoint:
    async def test_posts_page_parsed(self) -> None:
        api, session = make_api(
            [
                FakeResponse(
                    payload={
                        "status_code": 0,
                        "aweme_list": [AWEME_FULL, AWEME_SPARSE, {"desc": "无id"}],
                        "has_more": 1,
                        "max_cursor": 1757879000000,
                    }
                )
            ]
        )
        page = await api.get_user_posts("MS4wLjABAAAA", max_cursor=0)
        assert [v.video_id for v in page.videos] == [
            "7301234567890123456",
            "7301234567890123457",
        ]
        assert page.has_more is True
        assert page.max_cursor == 1757879000000
        assert "a_bogus=" in session.requested_urls[0]
        assert "/aweme/v1/web/aweme/post/?" in session.requested_urls[0]
        assert "sec_user_id=MS4wLjABAAAA" in session.requested_urls[0]
        assert session.requested_headers[0]["Cookie"] == "ttwid=abc; sessionid=xyz"

    async def test_missing_aweme_list_is_structure_drift(self) -> None:
        api, _ = make_api([FakeResponse(payload={"status_code": 0, "others": []})])
        with pytest.raises(StructureDriftError):
            await api.get_user_posts("MS4wLjABAAAA")

    async def test_nonzero_status_code_is_risk_control(self) -> None:
        api, _ = make_api(
            [
                FakeResponse(
                    payload={"status_code": 2483, "aweme_list": [], "status_msg": "频控"}
                )
            ]
        )
        with pytest.raises(RiskControlError):
            await api.get_user_posts("MS4wLjABAAAA")


class TestProfileEndpoint:
    async def test_profile_parsed(self) -> None:
        api, _ = make_api(
            [
                FakeResponse(
                    payload={
                        "status_code": 0,
                        "user": {
                            "sec_uid": "MS4wLjABAAAA",
                            "nickname": "财经老张",
                            "unique_id": "laozhang",
                            "avatar_thumb": {"url_list": ["https://p3/a.jpeg"]},
                        },
                    }
                )
            ]
        )
        profile = await api.get_user_profile("MS4wLjABAAAA")
        assert profile.nickname == "财经老张"
        assert profile.douyin_id == "laozhang"
        assert profile.avatar_url == "https://p3/a.jpeg"

    async def test_nonzero_status_without_user_is_account_invalid(self) -> None:
        api, _ = make_api(
            [
                FakeResponse(
                    payload={"status_code": 2113, "status_msg": "user not exist"}
                )
            ]
        )
        with pytest.raises(AccountInvalidError):
            await api.get_user_profile("MS4wLjABAAAA")

    async def test_empty_user_is_account_invalid(self) -> None:
        api, _ = make_api([FakeResponse(payload={"status_code": 0, "user": {}})])
        with pytest.raises(AccountInvalidError):
            await api.get_user_profile("MS4wLjABAAAA")

    async def test_missing_user_key_is_structure_drift(self) -> None:
        api, _ = make_api([FakeResponse(payload={"status_code": 0, "data": {}})])
        with pytest.raises(StructureDriftError):
            await api.get_user_profile("MS4wLjABAAAA")


class TestTransportAttribution:
    async def test_403_cools_jar_and_raises_risk_control(self) -> None:
        transport, session = make_transport([FakeResponse(status_code=403, payload="")])
        assert transport.jars_available == 1
        with pytest.raises(RiskControlError):
            await transport.get_json("/aweme/v1/web/aweme/post/", "aid=6383")
        assert transport.jars_available == 0

    async def test_400_is_signature_failure(self) -> None:
        transport, _ = make_transport([FakeResponse(status_code=400, payload="bad")])
        with pytest.raises(SignatureError):
            await transport.get_json("/aweme/v1/web/aweme/post/", "aid=6383")

    async def test_non_json_body_is_structure_drift(self) -> None:
        transport, _ = make_transport([FakeResponse(payload="<html>ok</html>")])
        with pytest.raises(StructureDriftError):
            await transport.get_json("/aweme/v1/web/aweme/post/", "aid=6383")

    async def test_json_body_with_verify_marker_is_parsed_not_risk_control(self) -> None:
        """成功 JSON 内含 verify 等词（aweme 的 custom_verify 字段）不得误判风控。"""
        payload = {"status_code": 0, "aweme_list": [], "custom_verify": ""}
        transport, _ = make_transport([FakeResponse(payload=payload)])
        assert await transport.get_json("/aweme/v1/web/aweme/post/", "aid=6383") == payload

    async def test_captcha_marker_is_risk_control(self) -> None:
        transport, _ = make_transport(
            [FakeResponse(status_code=200, payload="<html>请完成安全验证</html>")]
        )
        with pytest.raises(RiskControlError):
            await transport.get_json("/aweme/v1/web/aweme/post/", "aid=6383")

    async def test_no_jar_raises_risk_control(self) -> None:
        session = FakeSession([])
        transport = DouyinTransport(
            cookies=[], fingerprint=generate_fingerprint(), session_factory=lambda: session
        )
        with pytest.raises(RiskControlError, match="无可用 Cookie jar"):
            await transport.get_json("/aweme/v1/web/aweme/post/", "aid=6383")

    async def test_rotates_to_next_jar_after_risk_control(self) -> None:
        session = FakeSession(
            [
                FakeResponse(status_code=403, payload=""),
                FakeResponse(payload={"status_code": 0, "aweme_list": []}),
                FakeResponse(payload={"status_code": 0, "aweme_list": []}),
            ]
        )
        transport = DouyinTransport(
            cookies=["ttwid=a", "ttwid=b"],
            fingerprint=generate_fingerprint(),
            session_factory=lambda: session,
        )
        api = DouyinWebApi(transport)
        with pytest.raises(RiskControlError):
            await api.get_user_posts("MS4wLjABAAAA")
        # 后续请求跳过冷却中的 jar，轮换到第二份
        await api.get_user_posts("MS4wLjABAAAA")
        await api.get_user_posts("MS4wLjABAAAA")
        assert session.requested_headers[0]["Cookie"] == "ttwid=a"
        assert session.requested_headers[1]["Cookie"] == "ttwid=b"
        assert session.requested_headers[2]["Cookie"] == "ttwid=b"


class TestShortLink:
    async def test_expand_follows_location(self) -> None:
        session = FakeSession([FakeResponse(headers={"Location": "https://www.douyin.com/user/MS4wLjABAAAA"})])
        transport = DouyinTransport(
            cookies=[], fingerprint=generate_fingerprint(), session_factory=lambda: session
        )
        assert await DouyinWebApi(transport).expand_short_link("https://v.douyin.com/abc/") == (
            "https://www.douyin.com/user/MS4wLjABAAAA"
        )

    async def test_missing_location_is_structure_drift(self) -> None:
        session = FakeSession([FakeResponse(headers={})])
        transport = DouyinTransport(
            cookies=[], fingerprint=generate_fingerprint(), session_factory=lambda: session
        )
        with pytest.raises(StructureDriftError):
            await DouyinWebApi(transport).expand_short_link("https://v.douyin.com/abc/")
