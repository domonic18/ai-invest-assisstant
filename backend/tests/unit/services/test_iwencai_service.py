"""iwencai_service 单测：query2data 协议、空结果改写重试与 Redis 缓存。"""

import json
from contextlib import ExitStack
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import iwencai_service as isvc

pytestmark = pytest.mark.unit


def _settings_mock() -> SimpleNamespace:
    return SimpleNamespace(iwencai_api_key="test-key", iwencai_timeout_seconds=5.0)


def _http_mock(payloads: list[Any]) -> tuple[MagicMock, MagicMock]:
    """构造 httpx 模块替身：AsyncClient(timeout=...) 按调用次序返回 payloads。"""
    responses = []
    for item in payloads:
        response = MagicMock()
        if isinstance(item, Exception):
            response.raise_for_status.side_effect = item
        else:
            response.raise_for_status.return_value = None
            response.json.return_value = item
        responses.append(response)
    client = MagicMock()
    client.post = AsyncMock(side_effect=responses)
    ctx = AsyncMock()
    ctx.__aenter__.return_value = client
    factory = MagicMock(return_value=ctx)
    return MagicMock(AsyncClient=factory), client


def _gateway_payload(datas: list[dict[str, Any]]) -> dict[str, Any]:
    return {"status_code": 0, "status_msg": "success", "datas": datas,
            "code_count": len(datas), "chunks_info": []}


@pytest.fixture
def cache() -> SimpleNamespace:
    """cache_get/cache_set 替身：默认无缓存命中、写入成功。"""
    return SimpleNamespace(
        get=AsyncMock(return_value=None), set=AsyncMock(return_value=True)
    )


def _patch_cache(cache: SimpleNamespace) -> ExitStack:
    """同时替换 cache_get/cache_set（with 块内单行使用）。"""
    stack = ExitStack()
    stack.enter_context(patch.object(isvc, "cache_get", cache.get))
    stack.enter_context(patch.object(isvc, "cache_set", cache.set))
    return stack


async def test_query2data_happy_path(cache: SimpleNamespace) -> None:
    httpx_mock, client = _http_mock([_gateway_payload([{"股票代码": "000523.SZ"}])])
    with (
        patch.object(isvc, "httpx", httpx_mock),
        patch.object(isvc, "get_settings", lambda: _settings_mock()),
        _patch_cache(cache),
    ):
        result = await isvc.query2data("市盈率<20", limit=30)

    assert result["datas"] == [{"股票代码": "000523.SZ"}]
    assert result["code_count"] == 1
    assert client.post.await_count == 1
    kwargs = client.post.await_args.kwargs
    assert kwargs["json"] == {
        "query": "市盈率<20", "page": "1", "limit": "30",
        "is_cache": "1", "expand_index": "true",
    }
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["X-Claw-Call-Type"] == "normal"
    assert headers["X-Claw-Skill-Id"] == "hithink-zhishu-query"
    assert headers["X-Claw-Skill-Version"] == "2.0.0"
    assert len(headers["X-Claw-Trace-Id"]) == 64
    cache.set.assert_awaited_once()


async def test_query2data_cache_hit(cache: SimpleNamespace) -> None:
    cached = _gateway_payload([{"股票代码": "600000.SH"}])
    cache.get.return_value = json.dumps(cached, ensure_ascii=False).encode()
    httpx_mock, client = _http_mock([])
    with (
        patch.object(isvc, "httpx", httpx_mock),
        patch.object(isvc, "get_settings", lambda: _settings_mock()),
        _patch_cache(cache),
    ):
        result = await isvc.query2data("市盈率<20", limit=30)

    assert result["datas"] == [{"股票代码": "600000.SH"}]
    client.post.assert_not_awaited()


async def test_query2data_empty_retries_with_rewrite(cache: SimpleNamespace) -> None:
    httpx_mock, client = _http_mock(
        [_gateway_payload([]), _gateway_payload([{"股票代码": "600000.SH"}])]
    )
    with (
        patch.object(isvc, "httpx", httpx_mock),
        patch.object(isvc, "get_settings", lambda: _settings_mock()),
        _patch_cache(cache),
    ):
        result = await isvc.query2data(
            "原问句", limit=30, rewrite_candidates=["放宽问句"]
        )

    assert len(result["datas"]) == 1
    assert client.post.await_count == 2
    first_query = client.post.await_args_list[0].kwargs
    second_query = client.post.await_args_list[1].kwargs
    assert first_query["json"]["query"] == "原问句"
    assert first_query["headers"]["X-Claw-Call-Type"] == "normal"
    assert second_query["json"]["query"] == "放宽问句"
    assert second_query["headers"]["X-Claw-Call-Type"] == "retry"


async def test_query2data_rewrites_capped_at_two(cache: SimpleNamespace) -> None:
    httpx_mock, client = _http_mock([_gateway_payload([]) for _ in range(4)])
    with (
        patch.object(isvc, "httpx", httpx_mock),
        patch.object(isvc, "get_settings", lambda: _settings_mock()),
        _patch_cache(cache),
    ):
        result = await isvc.query2data(
            "原问句", limit=30, rewrite_candidates=["改写一", "改写二", "改写三"]
        )

    assert result["datas"] == []
    assert client.post.await_count == 3


async def test_query2data_gateway_error(cache: SimpleNamespace) -> None:
    httpx_mock, _ = _http_mock([{"status_code": 401, "status_msg": "unauthorized"}])
    with (
        patch.object(isvc, "httpx", httpx_mock),
        patch.object(isvc, "get_settings", lambda: _settings_mock()),
        _patch_cache(cache),
    ):
        with pytest.raises(isvc.IwencaiError, match="unauthorized"):
            await isvc.query2data("市盈率<20")


async def test_query2data_requires_api_key(cache: SimpleNamespace) -> None:
    settings = SimpleNamespace(iwencai_api_key="", iwencai_timeout_seconds=5.0)
    httpx_mock, client = _http_mock([])
    with (
        patch.object(isvc, "httpx", httpx_mock),
        patch.object(isvc, "get_settings", lambda: settings),
        _patch_cache(cache),
    ):
        with pytest.raises(isvc.IwencaiError, match="IWENCAI_API_KEY"):
            await isvc.query2data("市盈率<20")

    client.post.assert_not_awaited()
