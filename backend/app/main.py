"""FastAPI 应用入口：路由注册、CORS、生命周期与全局异常处理。"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动
    try:
        async with AsyncSessionLocal() as session:
            await seed_default_channels(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed_to_seed_collector_channels: %s", str(exc))
    try:
        await setup_assistant_runtime()
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed_to_setup_assistant_runtime: %s", str(exc))
    yield
    # 关闭
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
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
