"""代理服务器配置服务。

管理后台 CRUD 与连通性测试；采集运行时经
``collector.runtime.resolver`` 消费渠道绑定的代理（见批次 3）。
"""

import asyncio
from datetime import datetime, timezone

import structlog
from celery.exceptions import TimeoutError as CeleryTimeoutError
from cryptography.fernet import InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.collector import CollectorQueue
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.proxy_config import ProxyConfig
from app.repositories.admin.proxy_config_repository import ProxyConfigRepository
from app.schemas.proxy_config import (
    ProxyConfigCreate,
    ProxyConfigResponse,
    ProxyConfigTestResponse,
    ProxyConfigUpdate,
)
from app.utils.crypto import decrypt_token, encrypt_token, mask_token
from app.utils.proxy import build_proxy_url

logger = structlog.get_logger()

# worker 探测 8s + 派发/调度余量；SCF API 网关超时内必须返回
_PROXY_TEST_WAIT_SECONDS = 15.0


class ProxyConfigNotFoundError(NotFoundError):
    """请求的代理配置不存在时抛出。"""

    default_message = "代理配置不存在"


class ProxyConfigService:
    """面向管理后台的代理服务器配置服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProxyConfigRepository(session)

    async def list_configs(self) -> list[ProxyConfigResponse]:
        """列出全部代理配置。"""
        rows = await self.repo.list_ordered()
        return [self._to_response(row) for row in rows]

    async def get_config(self, config_id: int) -> ProxyConfigResponse:
        """按 ID 查询代理配置，缺失时抛 ProxyConfigNotFoundError。"""
        config = await self._get_or_404(config_id)
        return self._to_response(config)

    async def create_config(self, data: ProxyConfigCreate) -> ProxyConfigResponse:
        """创建新的代理配置。"""
        if await self.repo.exists_by_name(data.name):
            raise BadRequestError(f"代理名称已存在: {data.name}")
        config = ProxyConfig(
            name=data.name,
            protocol=data.protocol,
            host=data.host,
            port=data.port,
            username=data.username,
            password_encrypted=encrypt_token(data.password) if data.password else None,
            is_enabled=data.is_enabled,
        )
        self.repo.add(config)
        await self.session.commit()
        await self.repo.refresh(config)
        logger.info("proxy_config_created", proxy_id=config.id, name=config.name)
        return self._to_response(config)

    async def update_config(
        self, config_id: int, data: ProxyConfigUpdate
    ) -> ProxyConfigResponse:
        """更新已有代理配置，缺失时抛 ProxyConfigNotFoundError。"""
        config = await self._get_or_404(config_id)
        if data.name is not None and data.name != config.name:
            if await self.repo.exists_by_name(data.name, exclude_id=config_id):
                raise BadRequestError(f"代理名称已存在: {data.name}")
            config.name = data.name
        if data.protocol is not None:
            config.protocol = data.protocol
        if data.host is not None:
            config.host = data.host
        if data.port is not None:
            config.port = data.port
        if data.username is not None:
            config.username = data.username
        if data.is_enabled is not None:
            config.is_enabled = data.is_enabled
        if data.password:
            config.password_encrypted = encrypt_token(data.password)
        config.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.repo.refresh(config)
        return self._to_response(config)

    async def delete_config(self, config_id: int) -> None:
        """删除代理配置；引用它的渠道由外键 ON DELETE SET NULL 自动解绑。"""
        config = await self._get_or_404(config_id)
        await self.repo.delete(config)
        await self.session.commit()
        logger.info("proxy_config_deleted", proxy_id=config_id, name=config.name)

    async def test_config(self, config_id: int) -> ProxyConfigTestResponse:
        """派发探测任务到采集 worker，经代理请求探测端点并返回连通状态与延迟。

        代理的消费方是采集 worker：API 侧（SCF）出口 IP 不在代理白名单内，
        从 API 直接探测会被安全组拦截，故必须经 Celery 在 worker 上执行。
        """
        config = await self._get_or_404(config_id)
        proxy_url, error = self._build_url_or_error(config)
        if error is not None:
            return ProxyConfigTestResponse(
                ok=False, status_code=None, latency_ms=0, error=error
            )

        # 延迟导入：celery_tasks 聚合了采集运行时，避免服务模块顶层拉起整链
        from collector.celery_tasks import run_proxy_test

        result = run_proxy_test.apply_async(
            args=[proxy_url], queue=CollectorQueue.REALTIME.value
        )
        try:
            payload = await asyncio.to_thread(
                result.get, timeout=_PROXY_TEST_WAIT_SECONDS
            )
        except CeleryTimeoutError:
            logger.warning(
                "proxy_config_test_timeout", proxy_id=config.id
            )
            return ProxyConfigTestResponse(
                ok=False,
                status_code=None,
                latency_ms=0,
                error=(
                    f"采集 worker {_PROXY_TEST_WAIT_SECONDS:.0f}s 内未返回探测结果"
                    "（worker 未运行或队列阻塞）"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "proxy_config_test_failed", proxy_id=config.id, error=str(exc)
            )
            return ProxyConfigTestResponse(
                ok=False,
                status_code=None,
                latency_ms=0,
                error=f"{type(exc).__name__}: {exc}",
            )
        return ProxyConfigTestResponse(**payload)

    async def _get_or_404(self, config_id: int) -> ProxyConfig:
        config = await self.repo.get(config_id)
        if not config:
            raise ProxyConfigNotFoundError(f"Proxy config {config_id} not found")
        return config

    @staticmethod
    def _build_url_or_error(config: ProxyConfig) -> tuple[str | None, str | None]:
        """解密凭据并组装代理 URL；解密失败返回错误说明。"""
        password: str | None = None
        if config.password_encrypted:
            try:
                password = decrypt_token(config.password_encrypted)
            except InvalidToken:
                logger.error(
                    "proxy_config_decryption_failed",
                    proxy_id=config.id,
                    message="Stored password cannot be decrypted with current key",
                )
                return None, "存储的密码无法用当前加密密钥解密"
        return (
            build_proxy_url(
                config.protocol,
                config.host,
                config.port,
                config.username,
                password,
            ),
            None,
        )

    def _to_response(self, config: ProxyConfig) -> ProxyConfigResponse:
        password_masked: str | None = None
        if config.password_encrypted:
            try:
                password_masked = mask_token(decrypt_token(config.password_encrypted))
            except InvalidToken:
                password_masked = "[无法解密]"
        return ProxyConfigResponse(
            id=config.id,
            name=config.name,
            protocol=config.protocol,
            host=config.host,
            port=config.port,
            username=config.username,
            password_masked=password_masked,
            is_enabled=config.is_enabled,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
