from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_fund_flow() -> dict[str, Any]:
    return {"items": []}
