"""问财 AI 选股直查 API 的 Pydantic schemas。"""

from typing import Any

from pydantic import Field

from app.schemas.base import CamelModel


class ScreeningQueryRequest(CamelModel):
    """问财直查请求。"""

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=50, ge=1, le=100)


class ScreeningQueryResponse(CamelModel):
    """问财直查响应（stocks 行含问财原始中文列，键名原样透传）。"""

    query: str
    total: int
    truncated: bool
    columns: list[str] = []
    stocks: list[dict[str, Any]] = []
