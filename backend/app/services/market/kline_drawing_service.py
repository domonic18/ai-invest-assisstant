"""K 线画线服务（F-DRAW）：用户画线 CRUD 与 AI 画线集读写（均为 per-user 私有）。

锚点一律数据坐标 (date, price)；payload JSONB 内为 camelCase 结构，
与 shared/types/drawing.ts 契约同构。事务边界在本层（显式 commit）。
"""

import math
from datetime import date
from typing import Any, Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.drawing import DRAWING_LABEL_MAX, REQUIRED_ANCHORS
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.kline_drawing import AiKlineDrawing, UserKlineDrawing
from app.repositories.market.kline_drawing_repository import (
    AiKlineDrawingRepository,
    UserKlineDrawingRepository,
)
from app.schemas.drawing import (
    AiKlineDrawingAdoptRequest,
    AiKlineDrawingGroupResponse,
    AiKlineDrawingItemSchema,
    KlineDrawingsResponse,
    UserKlineDrawingCreateRequest,
    UserKlineDrawingResponse,
    UserKlineDrawingUpdateRequest,
)

# DB CHECK 约束保证取值域；ORM 列是宽 str，wire 层收窄为 Literal
TargetTypeLiteral = Literal["stock", "index", "sector"]
PeriodLiteral = Literal["daily", "weekly", "monthly"]
DrawingTypeLiteral = Literal["trendline", "ray", "hline", "box", "text"]


def _format_price(price: float) -> str:
    """价格格式化：最多两位小数，去除尾零。"""
    return f"{price:.2f}".rstrip("0").rstrip(".")


def _validate_anchors(drawing_type: str, anchors: list[dict[str, Any]]) -> None:
    """按类型校验锚点数量与取值（date 可解析、price 有限值）。

    Raises:
        BadRequestError: 锚点数量或取值不合法。
    """
    expected = REQUIRED_ANCHORS[drawing_type]
    if len(anchors) != expected:
        raise BadRequestError(f"画线类型 {drawing_type} 需要 {expected} 个锚点，收到 {len(anchors)} 个")
    for anchor in anchors:
        price = anchor.get("price")
        if not isinstance(price, (int, float)) or not math.isfinite(price):
            raise BadRequestError("锚点 price 必须是有限数值")
        anchor_date = anchor.get("date") or ""
        if drawing_type == "hline":
            if anchor_date:
                raise BadRequestError("水平线锚点不需要 date")
            continue
        if not anchor_date:
            raise BadRequestError("锚点 date 不能为空")
        try:
            date.fromisoformat(anchor_date)
        except ValueError as exc:
            raise BadRequestError(f"锚点 date 非法：{anchor_date}") from exc


def _payload_from_parts(
    anchors: list[dict[str, Any]],
    style: dict[str, Any],
    direction: str | None,
    text: str | None,
) -> dict[str, Any]:
    """构造 payload JSONB（camelCase，与 wire 契约同构）。"""
    payload: dict[str, Any] = {"anchors": anchors, "style": style}
    if direction:
        payload["direction"] = direction
    if text:
        payload["text"] = text
    return payload


def _drawing_from_row(row: UserKlineDrawing) -> UserKlineDrawingResponse:
    """payload 行 → wire 响应（扁平展开）。"""
    payload = row.payload or {}
    return UserKlineDrawingResponse(
        id=str(row.id),
        target_type=cast(TargetTypeLiteral, row.target_type),
        target_code=row.target_code,
        period=cast(PeriodLiteral, row.period),
        drawing_type=cast(DrawingTypeLiteral, row.drawing_type),
        anchors=payload.get("anchors", []),
        direction=payload.get("direction"),
        text=payload.get("text"),
        style=payload["style"],
    )


def _ai_items_from_group(group: AiKlineDrawing) -> AiKlineDrawingGroupResponse:
    """AI 画线集行 → wire 响应。"""
    return AiKlineDrawingGroupResponse(
        target_type=cast(TargetTypeLiteral, group.target_type),
        target_code=group.target_code,
        period=cast(PeriodLiteral, group.period),
        skill_id=group.skill_id,
        trade_date=group.trade_date,
        summary=group.summary,
        drawings=[AiKlineDrawingItemSchema.model_validate(item) for item in group.drawings or []],
    )


class KlineDrawingService:
    """画线服务：用户画线 CRUD + AI 画线集读写 + 上下文序列化。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserKlineDrawingRepository(session)
        self.ai_repo = AiKlineDrawingRepository(session)

    # ---------- 查询 ----------

    async def list_drawings(
        self, user_id: int, target_type: str, target_code: str
    ) -> KlineDrawingsResponse:
        """该标的全周期 user + ai 画线（周期切换前端过滤，零请求）。"""
        rows = await self.user_repo.list_by_user_target(user_id, target_type, target_code)
        groups = await self.ai_repo.list_by_user_target(user_id, target_type, target_code)
        return KlineDrawingsResponse(
            user=[_drawing_from_row(row) for row in rows],
            ai=[_ai_items_from_group(group) for group in groups],
        )

    # ---------- 用户画线 ----------

    async def create_user_drawing(
        self, user_id: int, request: UserKlineDrawingCreateRequest
    ) -> UserKlineDrawingResponse:
        """创建用户画线（实时落库）。"""
        anchors = [anchor.model_dump() for anchor in request.anchors]
        _validate_anchors(request.drawing_type, anchors)
        row = UserKlineDrawing(
            user_id=user_id,
            target_type=request.target_type,
            target_code=request.target_code,
            period=request.period,
            drawing_type=request.drawing_type,
            payload=_payload_from_parts(
                anchors,
                request.style.model_dump(),
                request.direction,
                request.text,
            ),
        )
        self.user_repo.add(row)
        await self.session.commit()
        return _drawing_from_row(row)

    async def update_user_drawing(
        self, user_id: int, drawing_id: int, request: UserKlineDrawingUpdateRequest
    ) -> UserKlineDrawingResponse:
        """部分更新用户画线（形态/样式/文字），校验归属。"""
        row = await self.user_repo.get_for_user(user_id, drawing_id)
        if row is None:
            raise NotFoundError("画线不存在")
        payload: dict[str, Any] = dict(row.payload or {})
        if request.anchors is not None:
            anchors = [anchor.model_dump() for anchor in request.anchors]
            _validate_anchors(row.drawing_type, anchors)
            payload["anchors"] = anchors
        if request.style is not None:
            payload["style"] = request.style.model_dump()
        if request.direction is not None:
            payload["direction"] = request.direction
        if request.text is not None:
            payload["text"] = request.text or None
        row.payload = payload
        await self.session.commit()
        return _drawing_from_row(row)

    async def delete_user_drawing(self, user_id: int, drawing_id: int) -> None:
        """删除用户画线，校验归属。"""
        row = await self.user_repo.get_for_user(user_id, drawing_id)
        if row is None:
            raise NotFoundError("画线不存在")
        await self.user_repo.delete(row)
        await self.session.commit()

    # ---------- AI 画线集（Agent 工具写路径，per-user 私有工作区） ----------

    async def upsert_ai_group(
        self,
        *,
        user_id: int,
        target_type: str,
        target_code: str,
        period: str,
        skill_id: str,
        trade_date: date | None,
        drawings: list[AiKlineDrawingItemSchema],
        mode: str = "replace",
        summary: str | None = None,
    ) -> AiKlineDrawingGroupResponse:
        """整组写入当前用户的 AI 画线集：replace 全量重画 / append 保留并新增。

        append 时 label 撞名即原位替换（label 组内唯一由本方法维护）。
        """
        group = await self.ai_repo.get_group(user_id, target_type, target_code, period)
        new_items = [item.model_dump() for item in drawings]
        if group is None:
            group = AiKlineDrawing(
                user_id=user_id,
                target_type=target_type,
                target_code=target_code,
                period=period,
                skill_id=skill_id,
                trade_date=trade_date,
                drawings=new_items,
                summary=summary,
            )
            self.ai_repo.add(group)
        else:
            if mode == "append":
                merged = {item["label"]: item for item in group.drawings or []}
                for item in new_items:
                    merged[item["label"]] = item
                group.drawings = list(merged.values())
            else:
                group.drawings = new_items
            group.skill_id = skill_id
            group.trade_date = trade_date
            if summary is not None:
                group.summary = summary
        await self.session.commit()
        return _ai_items_from_group(group)

    async def clear_ai_group(
        self, user_id: int, target_type: str, target_code: str, period: str
    ) -> None:
        """清空当前用户在标的+周期的 AI 画线集（对话重新生成即可恢复）。"""
        group = await self.ai_repo.get_group(user_id, target_type, target_code, period)
        if group is not None:
            await self.ai_repo.delete(group)
            await self.session.commit()

    # ---------- AI 画线单条编辑（F-DRAW-08 人工原位编辑，per-user 工作区） ----------

    async def update_ai_item(
        self,
        user_id: int,
        target_type: str,
        target_code: str,
        period: str,
        label: str,
        *,
        anchors: list[dict[str, Any]] | None = None,
        new_label: str | None = None,
    ) -> AiKlineDrawingItemSchema:
        """按 label 定位单条 AI 画线：改锚点（拖拽）与改名（双击）。

        label 是组内唯一键：改名先腾位（防撞名），锚点按画线类型校验后落表。
        """
        group = await self._require_ai_group(user_id, target_type, target_code, period)
        items = [dict(item) for item in group.drawings or []]
        index = next((i for i, item in enumerate(items) if item.get("label") == label), None)
        if index is None:
            raise NotFoundError(f"AI 画线 {label} 不存在")
        drawing_type = items[index].get("drawing_type", "")
        if new_label:
            new_label = new_label.strip()
            if not new_label or len(new_label) > DRAWING_LABEL_MAX:
                raise BadRequestError(
                    f"new_label 必须为 1-{DRAWING_LABEL_MAX} 字符"
                )
            if any(item.get("label") == new_label for i, item in enumerate(items) if i != index):
                raise BadRequestError(f"AI 画线组内已存在 label「{new_label}」")
            items[index]["label"] = new_label
        if anchors is not None:
            anchors = [dict(anchor) for anchor in anchors]
            _validate_anchors(drawing_type, anchors)
            items[index]["anchors"] = anchors
        group.drawings = items
        await self.session.commit()
        return AiKlineDrawingItemSchema.model_validate(items[index])

    async def delete_ai_item(
        self, user_id: int, target_type: str, target_code: str, period: str, label: str
    ) -> None:
        """按 label 删除单条 AI 画线（Delete 键）。"""
        group = await self._require_ai_group(user_id, target_type, target_code, period)
        items = [item for item in group.drawings or [] if item.get("label") != label]
        if len(items) == len(group.drawings or []):
            raise NotFoundError(f"AI 画线 {label} 不存在")
        group.drawings = items
        await self.session.commit()

    async def _require_ai_group(
        self, user_id: int, target_type: str, target_code: str, period: str
    ) -> AiKlineDrawing:
        group = await self.ai_repo.get_group(user_id, target_type, target_code, period)
        if group is None:
            raise NotFoundError("AI 画线组不存在")
        return group

    # ---------- 采纳 ----------

    async def adopt_ai_drawing(
        self, user_id: int, request: AiKlineDrawingAdoptRequest
    ) -> UserKlineDrawingResponse:
        """AI 画线单条采纳：按 label 定位，复制为用户画线（原 AI 画线保留）。"""
        group = await self.ai_repo.get_group(
            user_id, request.target_type, request.target_code, request.period
        )
        if group is None:
            raise NotFoundError("AI 画线组不存在")
        item = next(
            (entry for entry in group.drawings or [] if entry.get("label") == request.label),
            None,
        )
        if item is None:
            raise NotFoundError(f"AI 画线 {request.label} 不存在")
        anchors = [dict(anchor) for anchor in item.get("anchors", [])]
        _validate_anchors(item.get("drawing_type", ""), anchors)
        row = UserKlineDrawing(
            user_id=user_id,
            target_type=request.target_type,
            target_code=request.target_code,
            period=request.period,
            drawing_type=item["drawing_type"],
            payload=_payload_from_parts(
                anchors,
                request.style.model_dump(),
                item.get("direction"),
                item.get("label"),
            ),
        )
        self.user_repo.add(row)
        await self.session.commit()
        return _drawing_from_row(row)
