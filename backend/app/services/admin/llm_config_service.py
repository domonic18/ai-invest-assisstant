"""LLM 配置服务与默认模型解析。

提供管理后台 CRUD、默认模型切换、连通性测试，以及供 AI Skill 调用的
``resolve_default_llm`` 辅助函数。没有环境变量回退：若不存在已启用的
默认配置，调用方将收到 ``LLMConfigNotConfiguredError``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InternalError, NotFoundError
from app.models.llm_config import LLMConfig
from app.repositories.admin.llm_config_repository import LLMConfigRepository
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestResponse,
    LLMConfigUpdate,
)
from app.utils.crypto import decrypt_token, encrypt_token, mask_token

logger = structlog.get_logger()


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
        return [self._to_response(row) for row in rows]

    async def get_config(self, config_id: int) -> LLMConfigResponse | None:
        """按 ID 查询 LLM 配置。"""
        config = await self.repo.get(config_id)
        if not config:
            return None
        return self._to_response(config)

    async def create_config(self, data: LLMConfigCreate) -> LLMConfigResponse:
        """创建新配置。"""
        config = LLMConfig(
            name=data.name,
            provider=data.provider,
            base_url=data.base_url,
            api_key_encrypted=encrypt_token(data.api_key),
            model_name=data.model_name,
            is_active=data.is_active,
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
        return self._to_response(config)

    async def update_config(
        self, config_id: int, data: LLMConfigUpdate
    ) -> LLMConfigResponse | None:
        """更新已有配置。"""
        config = await self.repo.get(config_id)
        if not config:
            return None

        if data.name is not None:
            config.name = data.name
        if data.provider is not None:
            config.provider = data.provider
        if data.base_url is not None:
            config.base_url = data.base_url
        if data.model_name is not None:
            config.model_name = data.model_name
        if data.is_active is not None:
            config.is_active = data.is_active
        if data.extra is not None:
            config.extra = data.extra
        if data.api_key:
            config.api_key_encrypted = encrypt_token(data.api_key)
        if data.is_default:
            await self.repo.clear_other_defaults(exclude_id=config_id)
            config.is_default = True
            config.is_active = True

        await self.session.commit()
        await self.repo.refresh(config)
        return self._to_response(config)

    async def delete_config(self, config_id: int) -> None:
        """删除配置，必要时重新指定默认模型。"""
        config = await self.repo.get(config_id)
        if not config:
            raise ValueError(f"LLM config {config_id} not found")
        was_default = config.is_default
        await self.repo.delete(config)
        if was_default:
            nxt = await self.repo.get_first_active()
            if nxt:
                nxt.is_default = True
        await self.session.commit()

    async def set_default_config(self, config_id: int) -> LLMConfigResponse:
        """将某配置设为全局默认。"""
        config = await self.repo.get(config_id)
        if not config:
            raise ValueError(f"LLM config {config_id} not found")
        await self.repo.clear_other_defaults(exclude_id=config_id)
        config.is_default = True
        config.is_active = True
        await self.session.commit()
        await self.repo.refresh(config)
        logger.info("llm_config_set_default", config_id=config.id, name=config.name)
        return self._to_response(config)

    async def test_config_connection(self, config_id: int) -> LLMConfigTestResponse:
        """测试连通性并持久化结果。"""
        config = await self.repo.get(config_id)
        if not config:
            raise ValueError(f"LLM config {config_id} not found")

        api_key = decrypt_token(config.api_key_encrypted)
        test_status, detail = await self._call_model(config, api_key)
        now = datetime.now(timezone.utc)
        config.last_tested_at = now
        config.last_test_status = test_status
        config.last_test_error = None if test_status == "success" else detail
        await self.session.commit()
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
        """发送轻量 Anthropic 兼容探测请求以验证连通性。"""
        url = f"{config.base_url.rstrip('/')}/v1/messages"
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
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return "success", f"模型 {config.model_name} 连通正常"
            return "failed", f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm_config_test_failed", config_id=config.id, error=str(exc))
            return "failed", str(exc)

    def _to_response(self, config: LLMConfig) -> LLMConfigResponse:
        return LLMConfigResponse(
            id=config.id,
            name=config.name,
            provider=config.provider,
            base_url=config.base_url,
            model_name=config.model_name,
            api_key_masked=mask_token(decrypt_token(config.api_key_encrypted)),
            is_default=config.is_default,
            is_active=config.is_active,
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
    return ResolvedLLMConfig(
        config_id=config.id,
        provider=config.provider,
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
    config = configs[0]
    return ResolvedLLMConfig(
        config_id=config.id,
        provider=config.provider,
        base_url=config.base_url,
        api_key=decrypt_token(config.api_key_encrypted),
        model_name=config.model_name,
        extra=config.extra or {},
    )
