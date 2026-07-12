from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_research() -> dict[str, Any]:
    return {"items": []}


@router.get("/{report_id}")
async def get_research(report_id: str) -> dict[str, Any]:
    return {"id": report_id}


@router.post("/{report_id}/summarize")
async def summarize_research(report_id: str) -> dict[str, Any]:
    return {"id": report_id, "summary": ""}
