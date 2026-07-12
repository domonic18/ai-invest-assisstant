from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/me")
async def get_me() -> dict[str, Any]:
    return {"message": "get me placeholder"}


@router.put("/me")
async def update_me() -> dict[str, Any]:
    return {"message": "update me placeholder"}


@router.get("/watchlist")
async def get_watchlist() -> dict[str, Any]:
    return {"items": []}


@router.post("/watchlist")
async def add_watchlist() -> dict[str, Any]:
    return {"message": "add watchlist placeholder"}
