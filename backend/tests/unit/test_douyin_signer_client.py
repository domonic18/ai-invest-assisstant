"""签名 sidecar HTTP 客户端测试：MockTransport 驱动异常归类、UA 回显与禁用工厂。"""

from typing import Any

import httpx
import pytest

from app.adapters.douyin.signer_client import (
    DouyinSignerClient,
    SignerRejectedError,
    SignerUnavailableError,
    build_signer,
)

pytestmark = pytest.mark.unit

UA = "Mozilla/5.0 TestUA"
_OK_BODY: dict[str, Any] = {
    "params": {"a_bogus": "sig", "msToken": "mt"},
    "user_agent": UA,
}


def make_client(handler: Any) -> DouyinSignerClient:
    return DouyinSignerClient(
        "http://signer.test", transport=httpx.MockTransport(handler)
    )


def sign_request(client: DouyinSignerClient) -> dict[str, str]:
    return client.sign("/aweme/v1/web/aweme/post/", "aid=6383", UA, "ttwid=abc")


class TestSign:
    async def test_ok_returns_params(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = request.read()
            assert b"ttwid=abc" in payload
            return httpx.Response(200, json=_OK_BODY)

        assert await sign_request(make_client(handler)) == {"a_bogus": "sig", "msToken": "mt"}

    async def test_502_is_rejected(self) -> None:
        client = make_client(
            lambda _: httpx.Response(502, text="页面 SDK 未产出签名")
        )
        with pytest.raises(SignerRejectedError, match="签名页失败"):
            await sign_request(client)

    async def test_503_is_unavailable(self) -> None:
        client = make_client(lambda _: httpx.Response(503, json={"detail": "browser 未启动"}))
        with pytest.raises(SignerUnavailableError):
            await sign_request(client)

    async def test_422_is_rejected(self) -> None:
        client = make_client(lambda _: httpx.Response(422, json={"detail": "非法路径形状"}))
        with pytest.raises(SignerRejectedError):
            await sign_request(client)

    async def test_connect_error_is_unavailable(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with pytest.raises(SignerUnavailableError, match="不可达"):
            await sign_request(make_client(handler))

    async def test_user_agent_echo_mismatch_is_rejected(self) -> None:
        body = {"params": {"a_bogus": "sig"}, "user_agent": "Other/UA"}
        client = make_client(lambda _: httpx.Response(200, json=body))
        with pytest.raises(SignerRejectedError, match="UA 不一致"):
            await sign_request(client)

    async def test_empty_params_is_rejected(self) -> None:
        client = make_client(lambda _: httpx.Response(200, json={"params": {}, "user_agent": UA}))
        with pytest.raises(SignerRejectedError, match="空参数"):
            await sign_request(client)

    async def test_200_non_json_is_rejected(self) -> None:
        client = make_client(lambda _: httpx.Response(200, text="<html>proxy</html>"))
        with pytest.raises(SignerRejectedError, match="非 JSON"):
            await sign_request(client)


class TestHealth:
    async def test_ok_returns_payload(self) -> None:
        body = {"status": "ok", "driver": "playwright", "warm_slots": 2}
        client = make_client(lambda _: httpx.Response(200, json=body))
        assert await client.health() == body

    async def test_unreachable_raises_unavailable(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        client = make_client(handler)
        with pytest.raises(SignerUnavailableError):
            await client.health()

    async def test_200_non_json_is_unavailable(self) -> None:
        client = make_client(lambda _: httpx.Response(200, text="<html>proxy</html>"))
        with pytest.raises(SignerUnavailableError, match="非 JSON"):
            await client.health()


class TestBuildSigner:
    def test_empty_url_disables(self) -> None:
        assert build_signer("") is None
        assert build_signer(None) is None

    def test_url_builds_client(self) -> None:
        client = build_signer("http://douyin-signer:8010/")
        assert isinstance(client, DouyinSignerClient)
