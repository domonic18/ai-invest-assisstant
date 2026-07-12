from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    return {"tools": []}


@router.post("/invoke")
async def invoke_tool() -> dict[str, Any]:
    return {"result": ""}
