from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_news() -> dict[str, Any]:
    return {"items": []}
