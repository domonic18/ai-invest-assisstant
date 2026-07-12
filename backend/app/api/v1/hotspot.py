from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_hotspots() -> dict[str, Any]:
    return {"items": []}
