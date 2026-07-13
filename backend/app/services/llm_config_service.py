"""LLM configuration service and default resolver.

Provides admin CRUD, default-model switching, connectivity testing, and a
``resolve_default_llm`` helper for AI skill callers. There is no env fallback:
if no enabled default config exists, callers receive ``LLMConfigNotConfiguredError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMConfig
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestResponse,
    LLMConfigUpdate,
)
from app.utils.crypto import decrypt_token, encrypt_token, mask_token

logger = structlog.get_logger()


class LLMConfigNotConfiguredError(Exception):
    """Raised when no enabled default LLM configuration exists."""


class LLMConfigNotFoundError(Exception):
    """Raised when a requested LLM configuration does not exist or is disabled."""


@dataclass(frozen=True)
class ResolvedLLMConfig:
    """Decrypted configuration ready for AI SDK/Agent injection."""

    config_id: int
    provider: str
    base_url: str
    api_key: str
    model_name: str
    extra: dict[str, Any]


class LLMConfigService:
    """Admin-facing LLM configuration service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_configs(self) -> list[LLMConfigResponse]:
        """List all configurations with the default model first."""
        stmt = select(LLMConfig).order_by(LLMConfig.is_default.desc(), LLMConfig.id)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_response(row) for row in rows]

    async def create_config(self, data: LLMConfigCreate) -> LLMConfigResponse:
        """Create a new configuration."""
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
            await self._clear_other_defaults(exclude_id=None)
            config.is_default = True
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
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
        """Update an existing configuration."""
        config = await self.session.get(LLMConfig, config_id)
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
            await self._clear_other_defaults(exclude_id=config_id)
            config.is_default = True
            config.is_active = True

        await self.session.flush()
        await self.session.refresh(config)
        return self._to_response(config)

    async def delete_config(self, config_id: int) -> None:
        """Delete a configuration, reassigning default if needed."""
        config = await self.session.get(LLMConfig, config_id)
        if not config:
            raise ValueError(f"LLM config {config_id} not found")
        was_default = config.is_default
        await self.session.delete(config)
        await self.session.flush()
        if was_default:
            await self._reassign_default()

    async def set_default_config(self, config_id: int) -> LLMConfigResponse:
        """Set a configuration as the global default."""
        config = await self.session.get(LLMConfig, config_id)
        if not config:
            raise ValueError(f"LLM config {config_id} not found")
        await self._clear_other_defaults(exclude_id=config_id)
        config.is_default = True
        config.is_active = True
        await self.session.flush()
        await self.session.refresh(config)
        logger.info("llm_config_set_default", config_id=config.id, name=config.name)
        return self._to_response(config)

    async def test_config_connection(self, config_id: int) -> LLMConfigTestResponse:
        """Test connectivity and persist the result."""
        config = await self.session.get(LLMConfig, config_id)
        if not config:
            raise ValueError(f"LLM config {config_id} not found")

        api_key = decrypt_token(config.api_key_encrypted)
        test_status, detail = await self._call_model(config, api_key)
        now = datetime.now(timezone.utc)
        config.last_tested_at = now
        config.last_test_status = test_status
        config.last_test_error = None if test_status == "success" else detail
        await self.session.flush()
        return LLMConfigTestResponse(status=test_status, detail=detail, tested_at=now)

    async def get_default_config(self) -> LLMConfig:
        """Return the active default configuration."""
        stmt = select(LLMConfig).where(
            LLMConfig.is_default.is_(True),
            LLMConfig.is_active.is_(True),
        )
        config = (await self.session.execute(stmt)).scalar_one_or_none()
        if not config:
            raise LLMConfigNotConfiguredError(
                "未配置默认 AI 模型，请在后台管理「LLM 配置」中添加"
            )
        return config

    async def _clear_other_defaults(self, exclude_id: int | None) -> None:
        """Clear the default flag from all other configurations."""
        stmt = update(LLMConfig).values(is_default=False)
        if exclude_id is not None:
            stmt = stmt.where(LLMConfig.id != exclude_id)
        await self.session.execute(stmt)

    async def _reassign_default(self) -> None:
        """After deleting the default, promote the first active config."""
        stmt = (
            select(LLMConfig)
            .where(LLMConfig.is_active.is_(True))
            .order_by(LLMConfig.id)
            .limit(1)
        )
        nxt = (await self.session.execute(stmt)).scalar_one_or_none()
        if nxt:
            nxt.is_default = True
            await self.session.flush()

    async def _call_model(
        self, config: LLMConfig, api_key: str
    ) -> tuple[str, str]:
        """Send a lightweight Anthropic-compatible probe to verify connectivity."""
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
    """Resolve the enabled default LLM configuration for AI callers.

    Raises:
        LLMConfigNotConfiguredError: If no enabled default config exists.
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
