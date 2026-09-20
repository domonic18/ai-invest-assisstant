"""OpenAI 兼容 embeddings 小客户端（F-KB 索引/检索共用）。

不经 langchain：embedding 是批量短调用，直连 ``{base_url}/embeddings``
（与 ChatOpenAI 的 OpenAI SDK base_url 约定一致，``/v1`` 含在 base_url 内）。
客户端无 UsageMeterCallback 回调，按响应 usage 自行入账
（feature=kb_embed、system 维度、detail 携带知识库上下文）。
"""

from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InternalError
from app.services.kb.settings_service import resolve_role_model
from app.services.quota.constants import FEATURE_KB_EMBED, OUTLET_SYSTEM
from app.services.quota.usage_writer import UsageRecord, enqueue
from app.utils.crypto import decrypt_token

logger = structlog.get_logger(__name__)

_EMBED_BATCH_SIZE = 64
_DIMS_PROBE_TEXT = "维度探测"


class KbEmbeddingError(InternalError):
    """embedding 调用失败（索引任务显式退避 / 检索页友好报错）。"""

    default_message = "向量嵌入服务调用失败"


async def build_embedding_client(session: AsyncSession) -> "EmbeddingClient":
    """按知识库设置解析 embedding 角色槽位并构造客户端。"""
    config = await resolve_role_model(session, "embedding")
    return EmbeddingClient(
        config_id=config.id,
        provider=config.provider,
        base_url=config.base_url,
        api_key=decrypt_token(config.api_key_encrypted),
        model_name=config.model_name,
    )


class EmbeddingClient:
    """单一条目绑定的 embeddings 客户端（索引任务按批复用实例）。"""

    def __init__(
        self,
        *,
        config_id: int,
        provider: str,
        base_url: str,
        api_key: str,
        model_name: str,
    ) -> None:
        self.config_id = config_id
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name

    async def embed(
        self,
        texts: list[str],
        *,
        detail: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> list[list[float]]:
        """批量嵌入（单请求，调用方控制批量 ≤64），按 index 序返回向量。

        Raises:
            KbEmbeddingError: 非 2xx 或响应缺向量时抛出（不静默重试，
                重试策略由索引任务的退避承担）。
        """
        if not texts:
            return []
        url = f"{self.base_url}/embeddings"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    headers={"authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model_name, "input": texts},
                )
        except httpx.HTTPError as exc:
            raise KbEmbeddingError(f"embedding 请求失败：{exc}") from exc
        if response.status_code != 200:
            raise KbEmbeddingError(
                f"embedding 返回 HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            # 网关误配 base_url（缺 /v1 指到前端页）会 200 返回 HTML
            raise KbEmbeddingError(
                f"embedding 响应非 JSON（base_url 是否缺 /v1）：{response.text[:120]}"
            ) from exc
        items = payload.get("data") or []
        vectors: list[list[float]] | None = None
        try:
            ordered = sorted(items, key=lambda item: item["index"])
            vectors = [item["embedding"] for item in ordered]
        except (KeyError, TypeError) as exc:
            raise KbEmbeddingError("embedding 响应缺少 data[index]/embedding") from exc
        if len(vectors) != len(texts):
            raise KbEmbeddingError(
                f"embedding 返回数量不符：期望 {len(texts)}，实际 {len(vectors)}"
            )
        self._record_usage(payload.get("usage") or {}, texts, detail)
        return vectors

    async def embed_batched(
        self,
        texts: list[str],
        *,
        detail: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> list[list[float]]:
        """任意长度批量嵌入：按 64/请求分片顺序调用并拼接（与输入同序）。"""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH_SIZE):
            chunk = texts[start : start + _EMBED_BATCH_SIZE]
            vectors.extend(await self.embed(chunk, detail=detail, timeout=timeout))
        return vectors

    async def discover_dims(self) -> int:
        """实测模型向量维度（ES mapping 的 dims 与模型指纹绑定，禁止硬编码）。"""
        vectors = await self.embed([_DIMS_PROBE_TEXT], detail={"purpose": "dims_probe"})
        if not vectors or not vectors[0]:
            raise KbEmbeddingError("embedding 维度探测返回空向量")
        return len(vectors[0])

    def _record_usage(
        self, usage: dict[str, Any], texts: list[str], detail: dict[str, Any] | None
    ) -> None:
        """按响应 usage 入账（缺失时按字符数估算并标 estimated）。"""
        prompt_tokens = usage.get("prompt_tokens")
        if prompt_tokens is None:
            prompt_tokens = sum(len(text) for text in texts)
            estimated = True
        else:
            estimated = False
        total_tokens = usage.get("total_tokens") or prompt_tokens
        enqueue(
            UsageRecord(
                user_id=None,
                feature=FEATURE_KB_EMBED,
                model_name=self.model_name,
                provider=self.provider,
                outlet=OUTLET_SYSTEM,
                prompt_tokens=int(prompt_tokens),
                completion_tokens=0,
                total_tokens=int(total_tokens),
                estimated=estimated,
                detail=detail,
            )
        )
