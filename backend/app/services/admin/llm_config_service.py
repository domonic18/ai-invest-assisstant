"""LLM 配置服务与模型解析。

提供管理后台 CRUD、连通性测试，以及供调用方解析配置的辅助函数。
模型配置是**纯注册表**（2026-11-11 重构）：没有默认与主备语义，
「用哪个模型、备用是谁」由选择点决定（``llm_task_binding`` 任务槽位、
KB 角色槽位、交易 Agent 绑定）。没有环境变量回退：条目不存在或已停用
且无可用备用时，调用方将收到 ``LLMConfigNotFoundError``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

import httpx
import structlog
from cryptography.fernet import InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InternalError, NotFoundError
from app.models.llm_config import LLMConfig
from app.repositories.admin.llm_config_repository import LLMConfigRepository
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestResponse,
    LLMConfigUpdate,
    LLMProtocol,
)
from app.services.admin.llm_failover import (
    clear_unhealthy,
    degraded_until,
    resolve_healthy,
)
from app.utils.api_base import normalize_api_base
from app.utils.crypto import decrypt_token, encrypt_token, mask_token

logger = structlog.get_logger()


def infer_protocol(provider: str) -> LLMProtocol:
    """按渠道推断默认协议：anthropic 渠道 → anthropic，其余 → openai 兼容。"""
    return "anthropic" if provider == "anthropic" else "openai"


def normalize_purpose_protocol(purpose: str, protocol: str) -> tuple[str, str]:
    """用途与协议的对偶归一（systemone ⟺ decision、embedding → openai）。

    对表单误选做容错归一而非拒绝（与 decision→systemone 先例一致）：
    判断模型恒走 systemone wire（D23）；systemone 协议只有判断模型消费；
    嵌入端点（EmbeddingClient 与连通性探测）均为 OpenAI 形状，Anthropic
    无嵌入 API。UI 与 API 两条入口共用本规则，保证落库行自洽。
    """
    if purpose == "decision":
        protocol = "systemone"
    elif protocol == "systemone":
        purpose = "decision"
    if purpose == "embedding":
        protocol = "openai"
    return purpose, protocol


class LLMConfigNotConfiguredError(InternalError):
    """槽位无可用 LLM 配置（未绑定或主备皆不可用）时抛出。"""

    default_message = "无可用的 LLM 模型配置，请联系管理员在后台配置"


class LLMConfigNotFoundError(NotFoundError):
    """请求的 LLM 配置不存在或已禁用时抛出。"""

    default_message = "LLM 配置不存在或已禁用"


@dataclass(frozen=True)
class ResolvedLLMConfig:
    """解密后的配置，可直接注入 AI SDK/Agent。

    ``backup_config_id`` 是选择点携带的备用引用（主备切换重试路径
    自包含用），BYOK/无备用路径为 None。
    """

    config_id: int
    provider: str
    protocol: LLMProtocol
    base_url: str
    api_key: str
    model_name: str
    extra: dict[str, Any]
    name: str = ""
    backup_config_id: int | None = None


class LLMConfigService:
    """面向管理后台的 LLM 配置服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LLMConfigRepository(session)

    async def list_configs(self) -> list[LLMConfigResponse]:
        """列出全部配置。"""
        rows = await self.repo.list_ordered()
        return [await self._to_response(row) for row in rows]

    async def get_config(self, config_id: int) -> LLMConfigResponse:
        """按 ID 查询 LLM 配置，缺失时抛 LLMConfigNotFoundError。"""
        config = await self.repo.get(config_id)
        if not config:
            raise LLMConfigNotFoundError(f"LLM config {config_id} not found")
        return await self._to_response(config)

    async def create_config(self, data: LLMConfigCreate) -> LLMConfigResponse:
        """创建新配置。"""
        purpose, protocol = normalize_purpose_protocol(
            data.purpose, data.protocol or infer_protocol(data.provider)
        )
        config = LLMConfig(
            name=data.name,
            provider=data.provider,
            protocol=protocol,
            base_url=data.base_url,
            api_key_encrypted=encrypt_token(data.api_key),
            model_name=data.model_name,
            is_active=data.is_active,
            purpose=purpose,
            extra=data.extra,
        )
        self.repo.add(config)
        await self.session.commit()
        await self.repo.refresh(config)
        logger.info("llm_config_created", config_id=config.id, name=config.name)
        return await self._to_response(config)

    async def update_config(
        self, config_id: int, data: LLMConfigUpdate
    ) -> LLMConfigResponse:
        """更新已有配置，缺失时抛 LLMConfigNotFoundError。"""
        config = await self.repo.get(config_id)
        if not config:
            raise LLMConfigNotFoundError(f"LLM config {config_id} not found")

        if data.name is not None:
            config.name = data.name
        if data.provider is not None:
            config.provider = data.provider
        if data.protocol is not None:
            config.protocol = data.protocol
        if data.base_url is not None:
            config.base_url = data.base_url
        if data.model_name is not None:
            config.model_name = data.model_name
        if data.is_active is not None:
            config.is_active = data.is_active
        if data.purpose is not None:
            config.purpose = data.purpose
        if data.extra is not None:
            config.extra = data.extra
        if data.api_key:
            config.api_key_encrypted = encrypt_token(data.api_key)
        # 用途与协议对偶归一（与 create 同规则）：decision→systemone、
        # systemone→decision、embedding→openai，字段级赋值后统一收敛
        config.purpose, config.protocol = normalize_purpose_protocol(
            data.purpose or config.purpose, data.protocol or config.protocol
        )

        await self.session.commit()
        await self.repo.refresh(config)
        return await self._to_response(config)

    async def delete_config(self, config_id: int) -> None:
        """删除配置。

        选择点（任务槽位/KB 角色/交易 Agent）对被引用条目的失效有运行时
        防御（主失效走备用、备用失配维持主并告警），此处不做引用清理。
        """
        config = await self.repo.get(config_id)
        if not config:
            raise LLMConfigNotFoundError(f"LLM config {config_id} not found")
        await self.repo.delete(config)
        await self.session.commit()
        await clear_unhealthy(config_id)

    async def test_config_connection(self, config_id: int) -> LLMConfigTestResponse:
        """测试连通性并持久化结果。"""
        config = await self.repo.get(config_id)
        if not config:
            raise LLMConfigNotFoundError(f"LLM config {config_id} not found")

        api_key = decrypt_token(config.api_key_encrypted)
        test_status, detail = await self._call_model(config, api_key)
        now = datetime.now(timezone.utc)
        config.last_tested_at = now
        config.last_test_status = test_status
        config.last_test_error = None if test_status == "success" else detail
        await self.session.commit()
        # 连通正常即视为恢复：清除额度耗尽冷却标记，解析层切回主模型
        if test_status == "success":
            await clear_unhealthy(config_id)
        return LLMConfigTestResponse(status=test_status, detail=detail, tested_at=now)

    async def _call_model(
        self, config: LLMConfig, api_key: str
    ) -> tuple[str, str]:
        """按用途与协议发送轻量探测请求以验证连通性（与实际调用同路径）。"""
        base = normalize_api_base(config.base_url)
        if config.purpose == "embedding":
            # embedding 模型没有 chat 端点，按实际调用路径探测并回报维度
            url = f"{base}/embeddings"
            headers = {
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            }
            payload: dict[str, Any] = {"model": config.model_name, "input": ["ping"]}
        elif config.protocol == "systemone":
            # 判断模型（System One，D23）：按实际 wire 路径发最小 noul 探针，
            # 即 adapter 真实调用形状（「测试连接」= 真实冒烟）
            url = f"{base}/v1/systemone"
            headers = {
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            }
            payload = {
                "model": config.model_name,
                "state": {"ping": "连通性测试"},
                "questions": {
                    "connected": {
                        "type": "noul",
                        "instructions": "这是一次系统连通性测试。",
                        "criteria": {
                            "true": "本次调用正常送达",
                            "false": "本次调用异常",
                        },
                    }
                },
            }
        elif config.protocol == "anthropic":
            url = f"{base}/v1/messages"
            headers = {
                "x-api-key": api_key,
                "authorization": f"Bearer {api_key}",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": config.model_name,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            }
        else:
            url = f"{base}/chat/completions"
            headers = {
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            }
            payload = {
                "model": config.model_name,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                return "failed", f"HTTP {response.status_code}: {response.text[:200]}"
            if config.purpose == "embedding":
                try:
                    dims = len(response.json()["data"][0]["embedding"])
                except (ValueError, KeyError, IndexError, TypeError):
                    return "failed", f"响应缺少向量字段: {response.text[:200]}"
                return "success", f"模型 {config.model_name} 连通正常（{dims} 维）"
            return "success", f"模型 {config.model_name} 连通正常"
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm_config_test_failed", config_id=config.id, error=str(exc))
            return "failed", str(exc)

    async def _to_response(self, config: LLMConfig) -> LLMConfigResponse:
        try:
            api_key_masked = mask_token(decrypt_token(config.api_key_encrypted))
        except InvalidToken:
            # 凭据密钥轮换后旧密文无法解密：列表降级展示，不能整页 500
            logger.warning(
                "llm_config_decryption_failed",
                config_id=config.id,
                message="Stored API key cannot be decrypted with current key",
            )
            api_key_masked = "[无法解密，请重新录入]"
        return LLMConfigResponse(
            id=config.id,
            name=config.name,
            provider=config.provider,
            protocol=config.protocol,
            base_url=config.base_url,
            model_name=config.model_name,
            api_key_masked=api_key_masked,
            is_active=config.is_active,
            purpose=config.purpose,
            degraded_until=await degraded_until(config.id),
            extra=config.extra or {},
            last_tested_at=config.last_tested_at,
            last_test_status=config.last_test_status,
            last_test_error=config.last_test_error,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


async def _load_backup_row(
    session: AsyncSession, backup_config_id: int | None
) -> LLMConfig | None:
    """加载备用条目并核验可用（存在、启用）；失配返回 None。"""
    if backup_config_id is None:
        return None
    backup = await session.get(LLMConfig, backup_config_id)
    if backup is None or not backup.is_active:
        return None
    return backup


async def resolve_vision_llm(session: AsyncSession) -> ResolvedLLMConfig:
    """为图片识别类 AI 调用解析标记了视觉能力的启用配置。

    配置在管理后台 ``extra.capabilities.vision = true`` 标记（能力扫描
    解析，生产 vision 无备用、丢失无感，维持现状）。

    Raises:
        LLMConfigNotConfiguredError: 不存在已启用的视觉配置时抛出。
    """
    service = LLMConfigService(session)
    configs = await service.repo.list_vision_active()
    if not configs:
        raise LLMConfigNotConfiguredError(
            "未配置视觉模型，请联系管理员在后台「LLM 配置」中勾选「视觉能力」"
        )
    config = configs[0]
    return ResolvedLLMConfig(
        config_id=config.id,
        provider=config.provider,
        protocol=cast(LLMProtocol, config.protocol),
        base_url=config.base_url,
        api_key=decrypt_token(config.api_key_encrypted),
        model_name=config.model_name,
        extra=config.extra or {},
        name=config.name,
    )


async def resolve_llm_by_id(
    session: AsyncSession,
    config_id: int,
    *,
    backup_config_id: int | None = None,
) -> ResolvedLLMConfig:
    """按条目 id 解析指定 LLM 配置，主失效（删/停）时走显式备用。

    选择点携带的备用引用（任务槽位 backup_config_id / KB 角色备列 /
    交易 Agent 绑定）经 ``backup_config_id`` 传入；主条目冷却期内经
    健康门切备（备用失配维持主条目，由调用自然失败）。

    Raises:
        LLMConfigNotFoundError: 主条目失效且无可用备用时抛出。
    """
    repo = LLMConfigRepository(session)
    row = await repo.get(config_id)
    if row is None or not row.is_active:
        backup = await _load_backup_row(session, backup_config_id)
        if backup is None:
            raise LLMConfigNotFoundError(
                f"LLM 配置 {config_id} 不存在或已停用，且无可用备用"
            )
        logger.warning(
            "llm_failover_primary_invalid",
            config_id=config_id,
            backup_config_id=backup.id,
            backup_name=backup.name,
        )
        row = backup
    else:
        row = await resolve_healthy(session, row, backup_config_id)
    return ResolvedLLMConfig(
        config_id=row.id,
        provider=row.provider,
        protocol=cast(LLMProtocol, row.protocol),
        base_url=row.base_url,
        api_key=decrypt_token(row.api_key_encrypted),
        model_name=row.model_name,
        extra=row.extra or {},
        name=row.name,
        backup_config_id=backup_config_id,
    )
