"""K 线画线 API schema（camelCase wire 契约，与 shared/types/drawing.ts 镜像同构）。

锚点一律数据坐标 (date, price)；DB 侧 payload JSONB 扁平存 anchors+direction+
style+text，wire 层与 shared 契约同构展开。
"""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel

KlineDrawingTargetType = Literal["stock", "index", "sector"]
KlineDrawingPeriod = Literal["daily", "weekly", "monthly"]
KlineDrawingType = Literal["trendline", "ray", "hline", "box", "text"]
KlineDrawingDirection = Literal["left", "right", "both"]


class KlineDrawingAnchorSchema(CamelModel):
    """画线锚点（数据坐标）；hline 不需要 x 锚点，date 存空串。"""

    date: str
    price: float


class KlineDrawingStyleSchema(CamelModel):
    """用户画线样式；AI 画线样式由前端固定渲染，不进契约。"""

    color: str
    line_style: Literal["solid", "dashed", "dotted"]
    width: Literal[1, 2, 3]


class UserKlineDrawingCreateRequest(CamelModel):
    """用户画线创建请求。"""

    target_type: KlineDrawingTargetType
    target_code: str = Field(min_length=1, max_length=16)
    period: KlineDrawingPeriod
    drawing_type: KlineDrawingType
    anchors: list[KlineDrawingAnchorSchema] = Field(min_length=1, max_length=2)
    direction: KlineDrawingDirection | None = None
    text: str | None = Field(default=None, max_length=100)
    style: KlineDrawingStyleSchema


class UserKlineDrawingUpdateRequest(CamelModel):
    """用户画线部分更新：仅提交变更字段。"""

    anchors: list[KlineDrawingAnchorSchema] | None = Field(default=None, min_length=1, max_length=2)
    direction: KlineDrawingDirection | None = None
    text: str | None = Field(default=None, max_length=100)
    style: KlineDrawingStyleSchema | None = None


class UserKlineDrawingResponse(CamelModel):
    """用户画线（用户态）。"""

    id: str
    target_type: KlineDrawingTargetType
    target_code: str
    period: KlineDrawingPeriod
    drawing_type: KlineDrawingType
    anchors: list[KlineDrawingAnchorSchema]
    direction: KlineDrawingDirection | None = None
    text: str | None = None
    style: KlineDrawingStyleSchema


class AiKlineDrawingItemSchema(CamelModel):
    """AI 画线单项（label 组内唯一）。"""

    drawing_type: KlineDrawingType
    anchors: list[KlineDrawingAnchorSchema]
    direction: KlineDrawingDirection | None = None
    label: str
    reason: str


class AiKlineDrawingGroupResponse(CamelModel):
    """AI 画线集（全局共享、可变工作区，每标的每周期一套）。"""

    target_type: KlineDrawingTargetType
    target_code: str
    period: KlineDrawingPeriod
    skill_id: str
    trade_date: date | None = None
    summary: str | None = None
    drawings: list[AiKlineDrawingItemSchema]


class KlineDrawingsResponse(CamelModel):
    """GET /kline-drawings：该标的全部周期的 user + ai 两组。"""

    user: list[UserKlineDrawingResponse]
    ai: list[AiKlineDrawingGroupResponse]


class AiKlineDrawingAdoptRequest(CamelModel):
    """AI 画线单条采纳：按 label 定位（组内唯一），复制为用户画线。"""

    target_type: KlineDrawingTargetType
    target_code: str = Field(min_length=1, max_length=16)
    period: KlineDrawingPeriod
    label: str = Field(min_length=1, max_length=100)
    style: KlineDrawingStyleSchema
