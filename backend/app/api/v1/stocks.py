from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/search")
async def search_stocks() -> dict[str, Any]:
    return {"items": []}


@router.get("/{code}")
async def get_stock(code: str) -> dict[str, Any]:
    return {"code": code}
