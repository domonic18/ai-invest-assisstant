"""LLM 配置服务与默认模型解析。

提供管理后台 CRUD、默认模型切换、连通性测试，以及供 AI Skill 调用的
``resolve_default_llm`` 辅助函数。没有环境变量回退：若不存在已启用的
默认配置，调用方将收到 ``LLMConfigNotConfiguredError``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InternalError, NotFoundError, UnprocessableEntityError
from app.models.llm_config import LLMConfig
from app.repositories.admin.llm_config_repository import LLMConfigRepository
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestResponse,
    LLMConfigUpdate,
    LLMProtocol,
)
from app.services.admin.llm_failover import clear_unhealthy, degraded_until, resolve_healthy
from app.utils.api_base import normalize_api_base
from app.utils.crypto import decrypt_token, encrypt_token, mask_token

logger = structlog.get_logger()


def infer_protocol(provider: str) -> LLMProtocol:
    """按渠道推断默认协议：anthropic 渠道 → anthropic，其余 → openai 兼容。"""
    return "anthropic" if provider == "anthropic" else "openai"


class LLMConfigNotConfiguredError(InternalError):
    """不存在已启用的默认 LLM 配置时抛出。"""

    default_message = "未配置默认 LLM 模型，请联系管理员在后台配置"


class LLMConfigNotFoundError(NotFoundError):
    """请求的 LLM 配置不存在或已禁用时抛出。"""

    default_message = "LLM 配置不存在或已禁用"


@dataclass(frozen=True)
class ResolvedLLMConfig:
    """解密后的配置，可直接注入 AI SDK/Agent。"""

    config_id: int
    provider: str
    protocol: LLMProtocol
    base_url: str
    api_key: str
    model_name: str
    extra: dict[str, Any]


class LLMConfigService:
    """面向管理后台的 LLM 配置服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LLMConfigRepository(session)

    async def list_configs(self) -> list[LLMConfigResponse]:
        """列出全部配置，默认模型排在最前。"""
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
        await self._validate_backup(data.backup_config_id, data.purpose)
        config = LLMConfig(
            name=data.name,
            provider=data.provider,
            protocol=data.protocol or infer_protocol(data.provider),
            base_url=data.base_url,
            api_key_encrypted=encrypt_token(data.api_key),
            model_name=data.model_name,
            is_active=data.is_active,
            purpose=data.purpose,
            backup_config_id=data.backup_config_id,
            extra=data.extra,
        )
        if data.is_default:
            await self.repo.clear_other_defaults(exclude_id=None)
            config.is_default = True
        self.repo.add(config)
        await self.session.commit()
        await self.repo.refresh(config)
        logger.info(
            "llm_config_created",
            config_id=config.id,
            name=config.name,
            is_default=config.is_default,
        )
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
        if data.is_default:
            await self.repo.clear_other_defaults(exclude_id=config_id)
            config.is_default = True
            config.is_active = True
        # backup_config_id 允许显式置 null 清除（model_fields_set 区分未提供）
        if "backup_config_id" in data.model_fields_set:
            await self._validate_backup(data.backup_config_id, config.purpose, self_id=config_id)
            config.backup_config_id = data.backup_config_id
        elif data.purpose is not None and config.backup_config_id is not None:
            # purpose 变更后存量备用可能不再匹配，提前校验而非静默失效
            await self._validate_backup(config.backup_config_id, config.purpose, self_id=config_id)

        await self.session.commit()
        await self.repo.refresh(config)
        return await self._to_response(config)

    async def delete_config(self, config_id: int) -> None:
        """删除配置，必要时重新指定默认模型。"""
        config = await self.repo.get(config_id)
        if not config:
            raise LLMConfigNotFoundError(f"LLM config {config_id} not found")
        was_default = config.is_default
        await self.repo.clear_backup_references(config_id)
        await self.repo.delete(config)
        if was_default:
            nxt = await self.repo.get_first_active()
            if nxt:
                nxt.is_default = True
        await self.session.commit()
        await clear_unhealthy(config_id)

    async def set_default_config(self, config_id: int) -> LLMConfigResponse:
        """将某配置设为全局默认。"""
        config = await self.repo.get(config_id)
        if not config:
            raise LLMConfigNotFoundError(f"LLM config {config_id} not found")
        await self.repo.clear_other_defaults(exclude_id=config_id)
        config.is_default = True
        config.is_active = True
        await self.session.commit()
        await self.repo.refresh(config)
        logger.info("llm_config_set_default", config_id=config.id, name=config.name)
        return await self._to_response(config)

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

    async def get_default_config(self) -> LLMConfig:
        """返回已启用的默认配置。"""
        config = await self.repo.get_default_active()
        if not config:
            raise LLMConfigNotConfiguredError(
                "未配置默认 AI 模型，请在后台管理「LLM 配置」中添加"
            )
        return config

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

    async def _validate_backup(
        self, backup_config_id: int | None, purpose: str, *, self_id: int | None = None
    ) -> None:
        """校验备用引用：存在、启用、同 purpose、非自身（None 表示不指定）。"""
        if backup_config_id is None:
            return
        if self_id is not None and backup_config_id == self_id:
            raise UnprocessableEntityError("备用模型不能是配置自身")
        backup = await self.repo.get(backup_config_id)
        if backup is None or not backup.is_active:
            raise UnprocessableEntityError("备用模型不存在或已停用")
        if backup.purpose != purpose:
            raise UnprocessableEntityError(
                f"备用模型用途须与本配置一致（{purpose}）"
            )

    async def _to_response(self, config: LLMConfig) -> LLMConfigResponse:
        return LLMConfigResponse(
            id=config.id,
            name=config.name,
            provider=config.provider,
            protocol=config.protocol,
            base_url=config.base_url,
            model_name=config.model_name,
            api_key_masked=mask_token(decrypt_token(config.api_key_encrypted)),
            is_default=config.is_default,
            is_active=config.is_active,
            purpose=config.purpose,
            backup_config_id=config.backup_config_id,
            degraded_until=await degraded_until(config.id),
            extra=config.extra or {},
            last_tested_at=config.last_tested_at,
            last_test_status=config.last_test_status,
            last_test_error=config.last_test_error,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


async def resolve_default_llm(session: AsyncSession) -> ResolvedLLMConfig:
    """为 AI 调用方解析已启用的默认 LLM 配置。

    Raises:
        LLMConfigNotConfiguredError: 不存在已启用的默认配置时抛出。
    """
    service = LLMConfigService(session)
    config = await service.get_default_config()
    config = await resolve_healthy(session, config)
    return ResolvedLLMConfig(
        config_id=config.id,
        provider=config.provider,
        protocol=cast(LLMProtocol, config.protocol),
        base_url=config.base_url,
        api_key=decrypt_token(config.api_key_encrypted),
        model_name=config.model_name,
        extra=config.extra or {},
    )


async def resolve_vision_llm(session: AsyncSession) -> ResolvedLLMConfig:
    """为图片识别类 AI 调用解析标记了视觉能力的启用配置。

    配置在管理后台 ``extra.capabilities.vision = true`` 标记。

    Raises:
        LLMConfigNotConfiguredError: 不存在已启用的视觉配置时抛出。
    """
    service = LLMConfigService(session)
    configs = await service.repo.list_vision_active()
    if not configs:
        raise LLMConfigNotConfiguredError(
            "未配置视觉模型，请联系管理员在后台「LLM 配置」中勾选「视觉能力」"
        )
    config = await resolve_healthy(session, configs[0])
    return ResolvedLLMConfig(
        config_id=config.id,
        provider=config.provider,
        protocol=cast(LLMProtocol, config.protocol),
        base_url=config.base_url,
        api_key=decrypt_token(config.api_key_encrypted),
        model_name=config.model_name,
        extra=config.extra or {},
    )


async def resolve_llm_by_id(session: AsyncSession, config_id: int) -> ResolvedLLMConfig:
    """按条目 id 解析指定 LLM 配置（F-KB 模型角色槽位等显式引用路径）。

    Raises:
        LLMConfigNotFoundError: 条目不存在或已停用时抛出。
    """
    row = await LLMConfigRepository(session).get(config_id)
    if row is None or not row.is_active:
        raise LLMConfigNotFoundError(f"LLM 配置 {config_id} 不存在或已停用")
    row = await resolve_healthy(session, row)
    return ResolvedLLMConfig(
        config_id=row.id,
        provider=row.provider,
        protocol=cast(LLMProtocol, row.protocol),
        base_url=row.base_url,
        api_key=decrypt_token(row.api_key_encrypted),
        model_name=row.model_name,
        extra=row.extra or {},
    )
