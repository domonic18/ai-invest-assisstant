"""用户自备 API Key（BYOK）与模型出口分流（arch/10 §5）。

出口分流在解析层：``resolve_llm`` 统一决定本次调用走 BYOK 还是系统模型
（显式 user_id 优先，否则取当前计量上下文属主，无属主即系统维度走系统默认）。
解析之后不存在任何回退路径——BYOK 端点调用失败由调用层原样上抛。

加密复用 ``app/utils/crypto.py``（与 llm_config 同一 Fernet 路径）；
读路径只返回脱敏视图，永不回明文；api_key 不进任何日志字段。
"""

from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_quota import UserLlmConfig
from app.services.admin.llm_config_service import (
    ResolvedLLMConfig,
    resolve_default_llm,
    resolve_vision_llm,
)
from app.services.quota.constants import BYOK_PROVIDER, OUTLET_BYOK, OUTLET_SYSTEM
from app.services.quota.context import current_meter_context
from app.utils.crypto import encrypt_token, mask_token

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class UserLlmConfigView:
    """BYOK 配置脱敏视图（读路径）。"""

    protocol: str
    base_url: str
    model_name: str
    api_key_masked: str


def _to_resolved(row: UserLlmConfig) -> ResolvedLLMConfig:
    """BYOK 行 → ResolvedLLMConfig（延迟解密在构造处一次完成，不落日志）。"""
    from app.utils.crypto import decrypt_token

    return ResolvedLLMConfig(
        config_id=-row.id,  # 负数区分 BYOK 与 llm_config 行 id
        provider=BYOK_PROVIDER,
        protocol=row.protocol,  # type: ignore[arg-type]
        base_url=row.base_url,
        api_key=decrypt_token(row.api_key_encrypted),
        model_name=row.model_name,
        extra={},
    )


async def resolve_llm(
    session: AsyncSession,
    user_id: int | None = None,
    *,
    vision: bool = False,
) -> tuple[ResolvedLLMConfig, str]:
    """解析本次调用的模型出口，返回 (config, outlet)。

    Args:
        user_id: 显式属主；缺省取当前计量上下文的属主（助手工具内二次生成）。
        vision: 无 BYOK 时是否解析视觉能力配置（截图识别）。

    BYOK 生效（含 vision 路径，单一出口）：不占配额、失败不回退。
    """
    if user_id is None:
        ctx = current_meter_context()
        user_id = ctx.user_id if ctx is not None else None
    if user_id is not None:
        row = await session.get(UserLlmConfig, user_id)
        if row is not None:
            return _to_resolved(row), OUTLET_BYOK
    if vision:
        return await resolve_vision_llm(session), OUTLET_SYSTEM
    return await resolve_default_llm(session), OUTLET_SYSTEM


async def get_user_llm_config(session: AsyncSession, user_id: int) -> UserLlmConfigView | None:
    """读取 BYOK 配置脱敏视图；未配置返回 None。"""
    row = await session.get(UserLlmConfig, user_id)
    if row is None:
        return None
    return UserLlmConfigView(
        protocol=row.protocol,
        base_url=row.base_url,
        model_name=row.model_name,
        api_key_masked=row.api_key_masked,
    )


async def save_user_llm_config(
    session: AsyncSession,
    user_id: int,
    *,
    protocol: str,
    base_url: str,
    model_name: str,
    api_key: str,
) -> UserLlmConfigView:
    """保存（upsert）BYOK 配置；同一时间仅一套生效（user_id UNIQUE）。

    Raises:
        ValueError: 协议不合法。
    """
    if protocol not in ("openai", "anthropic"):
        raise ValueError("protocol 仅支持 openai / anthropic")
    row = await session.get(UserLlmConfig, user_id)
    if row is None:
        row = UserLlmConfig(user_id=user_id)
        session.add(row)
    row.protocol = protocol
    row.base_url = base_url.rstrip("/")
    row.model_name = model_name
    row.api_key_encrypted = encrypt_token(api_key)
    row.api_key_masked = mask_token(api_key)
    await session.commit()
    logger.info("user_llm_config_saved", user_id=user_id, protocol=protocol)
    return UserLlmConfigView(
        protocol=row.protocol,
        base_url=row.base_url,
        model_name=row.model_name,
        api_key_masked=row.api_key_masked,
    )


async def clear_user_llm_config(session: AsyncSession, user_id: int) -> bool:
    """清除 BYOK 配置（立即回落系统模型）；未配置返回 False。"""
    row = await session.get(UserLlmConfig, user_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    logger.info("user_llm_config_cleared", user_id=user_id)
    return True


async def test_user_llm_connection(
    *, protocol: str, base_url: str, model_name: str, api_key: str
) -> tuple[str, str]:
    """草稿参数连通性测试（不落库）：按协议手拼极小请求。

    Returns:
        (status, detail)：status ∈ success / failed。
    """
    base = base_url.rstrip("/")
    payload: dict[str, Any] = {
        "model": model_name,
        "max_tokens": 8,
        "messages": [{"role": "user", "content": "ping"}],
    }
    if protocol == "anthropic":
        url = f"{base}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    else:
        url = f"{base}/chat/completions"
        headers = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return "success", f"模型 {model_name} 连通正常"
        return "failed", f"HTTP {response.status_code}: {response.text[:200]}"
    except Exception as exc:  # noqa: BLE001
        return "failed", str(exc)
