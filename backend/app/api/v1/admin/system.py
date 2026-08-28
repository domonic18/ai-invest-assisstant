"""管理后台系统状态 API 端点。"""

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def system_status() -> dict[str, Any]:
    return {"status": "ok"}
