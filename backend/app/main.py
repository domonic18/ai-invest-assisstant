"""FastAPI 应用入口：路由注册、CORS、生命周期与全局异常处理。"""

import asyncio
import logging
from collections.abc import AsyncIterator, MutableMapping
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Send

from app.agent.runtime.assistant_agent import (
    close_assistant_runtime,
    setup_assistant_runtime,
)
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AppError
from collector.runtime.channels import seed_default_channels

settings = get_settings()
logger = logging.getLogger(__name__)


class ForceForwardedHttpsMiddleware:
    """FORCE_FORWARDED_HTTPS=1 时强制 scheme=https。

    SCF 入口为 HTTPS 但以 HTTP 转发容器且不携带 X-Forwarded-Proto，
    导致 request.url.scheme 判定为 http。等价替代原 nginx 的
    ``proxy_set_header X-Forwarded-Proto https``。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: MutableMapping[str, Any], receive: Receive, send: Send
    ) -> None:
        if scope["type"] in ("http", "websocket"):
            scope["scheme"] = "https"
            MutableHeaders(scope=scope)["x-forwarded-proto"] = "https"
        await self.app(scope, receive, send)


async def _warmup(app: FastAPI) -> None:
    """后台预热：渠道 seeding + 助手运行时（不阻塞端口监听）。"""
    try:
        async with AsyncSessionLocal() as session:
            await seed_default_channels(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed_to_seed_collector_channels: %s", str(exc))
    try:
        await setup_assistant_runtime()
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed_to_setup_assistant_runtime: %s", str(exc))
    app.state.warmup_done = True
    logger.info("app_warmup_done")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动：立即监听端口，预热放后台任务（消除冷启动窗口内的连接拒绝）
    app.state.warmup_done = False
    warmup_task = asyncio.create_task(_warmup(app))
    yield
    # 关闭
    warmup_task.cancel()
    with suppress(asyncio.CancelledError):
        await warmup_task
    await close_assistant_runtime()


app = FastAPI(
    title=settings.app_name,
    description="AI 智能投研数据平台 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.force_forwarded_https:
    app.add_middleware(ForceForwardedHttpsMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    body = await request.body()
    logger.warning(
        "request_validation_failed: %s %s errors=%s body=%s",
        request.method,
        request.url.path,
        exc.errors(),
        body[:500],
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """业务异常统一转 JSONResponse `{detail: message}`，格式与 HTTPException 一致。"""
    logger.warning(
        "app_error: %s %s status=%s msg=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.message,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    return {
        "status": "ok",
        "warmup_done": bool(getattr(request.app.state, "warmup_done", False)),
    }


def _spa_file_response(path: Path, cache_control: str, scheme: str) -> FileResponse:
    headers = {"Cache-Control": cache_control}
    # HSTS / CSP 仅 HTTPS 下发：本地 http 访问不能被 upgrade-insecure-requests 破坏
    if scheme == "https":
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        headers["Content-Security-Policy"] = "upgrade-insecure-requests"
    return FileResponse(path, headers=headers)


def register_spa_routes(app: FastAPI, static_dir: Path) -> None:
    """托管 SPA 静态文件 + 前端路由 fallback（注册须晚于所有 API 路由）。"""
    index_file = static_dir / "index.html"

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(request: Request, full_path: str) -> Response:
        # API 未匹配路径保持 JSON 404，不落 index.html
        if full_path == "api" or full_path.startswith("api/"):
            # SPA catch-all 会抢在 Starlette redirect_slashes 之前接住请求，
            # 这里补回"缺尾斜杠"重定向，使集合根路由（如 /api/v1/admin/users/）
            # 的无斜杠形式可达；带尾斜杠的未知路径仍 404，不会形成重定向环
            if not full_path.endswith("/"):
                return RedirectResponse(
                    str(request.url.replace(path=f"{request.url.path}/")),
                    status_code=307,
                )
            raise HTTPException(status_code=404)
        if full_path:
            candidate = (static_dir / full_path).resolve()
            if static_dir.resolve() not in candidate.parents:
                raise HTTPException(status_code=404)
            if candidate.is_file():
                cache = (
                    "public, max-age=31536000, immutable"
                    if full_path.startswith("assets/")
                    else "no-cache, must-revalidate"
                )
                return _spa_file_response(candidate, cache, request.url.scheme)
        return _spa_file_response(index_file, "no-cache, must-revalidate", request.url.scheme)


if settings.static_dir is not None and settings.static_dir.is_dir():
    register_spa_routes(app, settings.static_dir)
