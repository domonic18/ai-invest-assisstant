from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/{code}")
async def get_kline(code: str) -> dict[str, Any]:
    return {"code": code, "data": []}
