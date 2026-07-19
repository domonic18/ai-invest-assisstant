import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from collector.runtime.channels import seed_default_channels

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    try:
        async with AsyncSessionLocal() as session:
            await seed_default_channels(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed_to_seed_collector_channels: %s", str(exc))
    yield
    # Shutdown


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


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
