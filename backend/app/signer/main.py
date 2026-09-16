"""签名 sidecar HTTP 面：三个端点，无鉴权。

服务只监听 compose 私有网络；两个共享内网的容器之间加鉴权只会增加
密钥轮换与一项配置错误面，不移动信任边界。路由保持薄：
parse → service → shape reply，每个值得测的决策都在 service/slots。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.signer.backend import BrowserUnavailableError, SignPageError
from app.signer.models import HealthResponse, SignRequest, SignResponse
from app.signer.service import SignerService
from app.signer.settings import SignerSettings
from app.signer.slots import SlotManager
from app.signer.validation import (
    SignRequestError,
    parse_cookie_header,
    validate_path,
    validate_query,
    validate_user_agent,
)

logger = structlog.get_logger(__name__)


def create_app(settings: SignerSettings | None = None) -> FastAPI:
    """构建应用；settings/service 可注入（测试用 fake slots）。"""
    settings = settings or SignerSettings()

    async def _build_service() -> SignerService:
        from app.signer.backend import PlaywrightBackend

        backend = PlaywrightBackend(settings)
        return SignerService(SlotManager(backend, settings), settings)

    # 类型上 service 由 lifespan 前赋值；路由仅 lifespan 期间可达
    service_holder: dict[str, SignerService] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        service = await _build_service()
        service_holder["service"] = service
        await service.start()
        try:
            yield
        finally:
            await service.close()

    app = FastAPI(
        title="zjz douyin-signer",
        description="抖音页面 SDK 签名 sidecar：capture-shim 让 warm 页给请求签名。",
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.exception_handler(SignRequestError)
    async def _rejected(_: Request, exc: SignRequestError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(SignPageError)
    async def _backend_failure(_: Request, exc: SignPageError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(BrowserUnavailableError)
    async def _backend_unavailable(_: Request, exc: BrowserUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.post("/sign", response_model=SignResponse)
    async def sign(payload: SignRequest) -> SignResponse:
        validate_path(payload.path)
        validate_query(payload.query)
        validate_user_agent(payload.user_agent)
        cookies = parse_cookie_header(payload.cookies)
        # parse 后以规范化形状回填，避免调用方携带无法装配的键值对
        normalized = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        return await service_holder["service"].sign(
            payload.path, payload.query, payload.user_agent.strip(), normalized
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        # health 必须永远可答；service 未挂载（启动早期）也返回可用形状
        holder = service_holder.get("service")
        if holder is None:
            return HealthResponse(status="starting")
        return holder.health()

    return app


app = create_app()
