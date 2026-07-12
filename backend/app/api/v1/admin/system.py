from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def system_status() -> dict[str, Any]:
    return {"status": "ok"}
