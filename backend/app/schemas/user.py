"""User and watchlist related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    """用户响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class WatchlistItemCreate(BaseModel):
    """自选股创建请求。"""

    stock_code: str = Field(..., min_length=6, max_length=10)
    tags: list[str] | None = None


class WatchlistItemResponse(BaseModel):
    """自选股响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    tags: list[str] | None = None
    created_at: datetime
