from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.post("/analyze")
async def analyze_chain() -> dict[str, Any]:
    return {"message": "chain analysis placeholder"}
