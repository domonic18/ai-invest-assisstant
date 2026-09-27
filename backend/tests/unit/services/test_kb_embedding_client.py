"""embedding 客户端单测：分片批量、按 index 排序、usage 入账与错误路径（httpx 全 mock）。"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.kb.embedding_client import EmbeddingClient

pytestmark = pytest.mark.unit


def _client() -> EmbeddingClient:
    return EmbeddingClient(
        config_id=3,
        provider="custom",
        base_url="https://gw.example.com/v1",
        api_key="sk-test",
        model_name="embedding-3",
    )


def _response(status: int = 200, payload: dict[str, Any] | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload or {}
    resp.text = "err-body"
    return resp


def _payload(count: int, *, dim: int = 4, usage: dict[str, int] | None = None) -> dict[str, Any]:
    # index 乱序返回，钉死客户端按 index 重排
    order = list(reversed(range(count)))
    return {
        "data": [
            {"index": i, "embedding": [float(i)] * dim} for i in order
        ],
        "usage": usage,
    }


async def test_embed_orders_by_index_and_records_usage() -> None:
    client = _client()
    with (
        patch(
            "app.services.kb.embedding_client.enqueue", new=MagicMock()
        ) as p_enqueue,
        patch(
            "app.services.kb.embedding_client.httpx.AsyncClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(payload=_payload(3, usage={"prompt_tokens": 42, "total_tokens": 42}))
        )
        vectors = await client.embed(["a", "b", "c"], detail={"sourceId": 1})

    assert [v[0] for v in vectors] == [0.0, 1.0, 2.0]
    record = p_enqueue.call_args.args[0]
    assert record.prompt_tokens == 42
    assert record.estimated is False
    assert record.feature == "kb_embed"
    assert record.detail == {"sourceId": 1}


async def test_base_url_with_endpoint_suffix_is_normalized() -> None:
    """用户粘贴 …/embeddings 完整端点时归一化剥离，不拼出双重路径。"""
    client = EmbeddingClient(
        config_id=3,
        provider="custom",
        base_url="https://open.bigmodel.cn/api/paas/v4/embeddings",
        api_key="sk-test",
        model_name="embedding-3",
    )
    assert client.base_url == "https://open.bigmodel.cn/api/paas/v4"

    with patch("app.services.kb.embedding_client.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(payload=_payload(1))
        )
        await client.embed(["ping"])

    posted_url = mock_client_cls.return_value.__aenter__.return_value.post.call_args.args[0]
    assert posted_url == "https://open.bigmodel.cn/api/paas/v4/embeddings"


async def test_embed_truncates_overlong_texts() -> None:
    """超厂商单条上限的文本截断后发送（ASR 退化重复 / 截图 OCR 全量场景）。"""
    client = _client()
    with patch("app.services.kb.embedding_client.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(payload=_payload(2))
        )
        await client.embed(["长" * 5000, "短"])

    sent = mock_client_cls.return_value.__aenter__.return_value.post.call_args.kwargs["json"][
        "input"
    ]
    assert len(sent[0]) == 2048
    assert sent[1] == "短"


async def test_embed_usage_missing_falls_back_to_chars() -> None:
    client = _client()
    with (
        patch("app.services.kb.embedding_client.enqueue", new=MagicMock()) as p_enqueue,
        patch(
            "app.services.kb.embedding_client.httpx.AsyncClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(payload=_payload(2))
        )
        await client.embed(["abcd", "ef"])

    record = p_enqueue.call_args.args[0]
    assert record.prompt_tokens == 6  # 字符数估算
    assert record.estimated is True


async def test_embed_batched_chunks_by_64() -> None:
    client = _client()
    post = AsyncMock(
        side_effect=lambda url, **kwargs: _response(
            payload=_payload(len(kwargs["json"]["input"]))
        )
    )
    with (
        patch("app.services.kb.embedding_client.enqueue", new=MagicMock()),
        patch(
            "app.services.kb.embedding_client.httpx.AsyncClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__.return_value.post = post
        vectors = await client.embed_batched([f"t{i}" for i in range(65)])

    assert len(vectors) == 65
    sizes = [c.kwargs["json"]["input"] for c in post.call_args_list]
    assert [len(s) for s in sizes] == [64, 1]
    # 各分片内按 index 重排后顺序拼接（第二片向量值取分片内 index）
    assert [v[0] for v in vectors] == [float(i) for i in range(64)] + [0.0]


async def test_embed_rejects_count_mismatch() -> None:
    client = _client()
    with (
        patch("app.services.kb.embedding_client.enqueue", new=MagicMock()),
        patch(
            "app.services.kb.embedding_client.httpx.AsyncClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(payload=_payload(2))
        )
        with pytest.raises(Exception, match="返回数量不符"):
            await client.embed(["a", "b", "c"])


async def test_embed_non_200_raises() -> None:
    from app.services.kb.embedding_client import KbEmbeddingError

    client = _client()
    with patch(
        "app.services.kb.embedding_client.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(status=429)
        )
        with pytest.raises(KbEmbeddingError, match="429"):
            await client.embed(["a"])


async def test_embed_quota_failure_marks_unhealthy() -> None:
    """429/额度类失败标记配置进冷却；非额度类失败不标记。"""
    from app.services.kb.embedding_client import KbEmbeddingError

    client = _client()
    with (
        patch(
            "app.services.kb.embedding_client.mark_unhealthy", new=AsyncMock()
        ) as p_mark,
        patch(
            "app.services.kb.embedding_client.httpx.AsyncClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(status=429)
        )
        with pytest.raises(KbEmbeddingError):
            await client.embed(["a"])
    p_mark.assert_awaited_once_with(3)

    with (
        patch(
            "app.services.kb.embedding_client.mark_unhealthy", new=AsyncMock()
        ) as p_mark_500,
        patch(
            "app.services.kb.embedding_client.httpx.AsyncClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(status=500)
        )
        with pytest.raises(KbEmbeddingError):
            await client.embed(["a"])
    p_mark_500.assert_not_awaited()


async def test_discover_dims() -> None:
    client = _client()
    with (
        patch("app.services.kb.embedding_client.enqueue", new=MagicMock()),
        patch(
            "app.services.kb.embedding_client.httpx.AsyncClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_response(payload=_payload(1, dim=2048))
        )
        assert await client.discover_dims() == 2048
