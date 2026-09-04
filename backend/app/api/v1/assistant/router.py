"""Assistant API 子路由聚合。

保持外部 URL 不变：/v1/assistant/*
"""

from fastapi import APIRouter

from app.api.v1.assistant import runs, skills, threads

router = APIRouter()
router.include_router(threads.router, tags=["assistant"])
router.include_router(threads.sessions_router, tags=["assistant"])
router.include_router(runs.router, tags=["assistant"])
router.include_router(skills.router, tags=["assistant"])
