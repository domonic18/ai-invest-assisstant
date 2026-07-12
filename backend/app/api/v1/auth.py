from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.post("/register")
async def register() -> dict[str, Any]:
    return {"message": "register placeholder"}


@router.post("/login")
async def login() -> dict[str, Any]:
    return {"message": "login placeholder"}


@router.post("/wx-login")
async def wx_login() -> dict[str, Any]:
    return {"message": "wx login placeholder"}
