"""K 线画线服务（F-DRAW）：用户画线 CRUD、AI 画线集读写与上下文序列化。

锚点一律数据坐标 (date, price)；payload JSONB 内为 camelCase 结构，
与 shared/types/drawing.ts 契约同构。事务边界在本层（显式 commit）。
"""

import math
from collections.abc import Mapping
from datetime import date
from typing import Any, Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

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

#: 画线类型 → 锚点数（hline 只有价格锚点，date 存空串）
REQUIRED_ANCHORS: dict[str, int] = {
    "trendline": 2,
    "ray": 2,
    "box": 2,
    "hline": 1,
    "text": 1,
}

PERIOD_ORDER = {"daily": 0, "weekly": 1, "monthly": 2}
PERIOD_LABEL = {"daily": "日线", "weekly": "周线", "monthly": "月线"}


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


def serialize_user_drawings_context(
    drawings: list[UserKlineDrawingResponse],
) -> str:
    """用户画线 → 紧凑文字块（需求 4.4 读协议，纯函数可单测）。

    文字标注是一等信号：几何形态 + 用户标注语义一并注入；
    画线为空返回空提示（不阻断复盘链路）。
    """
    if not drawings:
        return "（该标的暂无用户画线）"

    by_period: dict[str, list[UserKlineDrawingResponse]] = {}
    for drawing in drawings:
        by_period.setdefault(drawing.period, []).append(drawing)

    lines: list[str] = []
    for period in sorted(by_period, key=lambda p: PERIOD_ORDER.get(p, 99)):
        lines.append(f"[用户画线·{PERIOD_LABEL.get(period, period)}]")
        for drawing in by_period[period]:
            anchors = drawing.anchors
            text = f"「{drawing.text}」" if drawing.text else ""
            if drawing.drawing_type == "hline":
                body = f"水平线：{_format_price(anchors[0].price)}"
            elif drawing.drawing_type == "box":
                body = (
                    f"箱体：{_format_price(anchors[0].price)}~{_format_price(anchors[1].price)}"
                    f"（{anchors[0].date} ~ {anchors[1].date}）"
                )
            elif drawing.drawing_type == "text":
                body = f"文字标注：{text} @ {anchors[0].date} {_format_price(anchors[0].price)}"
                lines.append(f"- {body}")
                continue
            elif drawing.drawing_type == "ray":
                direction_word = {"left": "向左延伸", "both": "双向延伸"}.get(
                    drawing.direction or "right", "向右延伸"
                )
                body = (
                    f"射线：{anchors[0].date} {_format_price(anchors[0].price)} → "
                    f"{anchors[1].date} {_format_price(anchors[1].price)} → {direction_word}"
                )
            else:  # trendline
                body = (
                    f"线段：{anchors[0].date} {_format_price(anchors[0].price)} → "
                    f"{anchors[1].date} {_format_price(anchors[1].price)}"
                )
            lines.append(f"- {body}{text}")
    return "\n".join(lines)


async def build_target_drawings_context(
    session: AsyncSession, target_type: str, target_code: str
) -> str:
    """单标的用户画线 → 复盘注入文字块（需求 4.4 读协议 ①③ 共用）。

    Agent 读取不隔离用户（单主人平台惯例，与定时复盘 watchlist 遍历一致）；
    注入失败的降级由调用方负责（复盘照常）。
    """
    repo = UserKlineDrawingRepository(session)
    rows = await repo.list_by_target(target_type, target_code)
    return serialize_user_drawings_context([_drawing_from_row(row) for row in rows])


async def build_market_index_drawings_context(
    session: AsyncSession, codes: Mapping[str, str]
) -> str:
    """大盘多标的用户画线 → 复盘注入文字块（需求 4.4 读协议 ②）。

    codes 为 指数代码 → 中文名 映射（复盘技术面覆盖的五标的）；
    仅有画线的标的进入输出，前置 [指数名] 头；全空时返回空提示。
    """
    repo = UserKlineDrawingRepository(session)
    parts: list[str] = []
    for code, label in codes.items():
        rows = await repo.list_by_target("index", code)
        if not rows:
            continue
        serialized = serialize_user_drawings_context(
            [_drawing_from_row(row) for row in rows]
        )
        parts.append(f"[{label}]\n{serialized}")
    return "\n\n".join(parts) if parts else "（五大标的暂无用户画线）"


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
        groups = await self.ai_repo.list_by_target(target_type, target_code)
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

    # ---------- AI 画线集（Agent 工具写路径，无用户归属） ----------

    async def upsert_ai_group(
        self,
        *,
        target_type: str,
        target_code: str,
        period: str,
        skill_id: str,
        trade_date: date | None,
        drawings: list[AiKlineDrawingItemSchema],
        mode: str = "replace",
        summary: str | None = None,
    ) -> AiKlineDrawingGroupResponse:
        """整组写入 AI 画线集：replace 全量重画 / append 保留并新增。

        append 时 label 撞名即原位替换（label 组内唯一由本方法维护）。
        """
        group = await self.ai_repo.get_group(target_type, target_code, period)
        new_items = [item.model_dump() for item in drawings]
        if group is None:
            group = AiKlineDrawing(
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

    async def clear_ai_group(self, target_type: str, target_code: str, period: str) -> None:
        """清空指定标的+周期的 AI 画线集（对话重新生成即可恢复）。"""
        group = await self.ai_repo.get_group(target_type, target_code, period)
        if group is not None:
            await self.ai_repo.delete(group)
            await self.session.commit()

    # ---------- AI 画线单条编辑（F-DRAW-08 人工原位编辑，全局共享工作区） ----------

    async def update_ai_item(
        self,
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
        group = await self._require_ai_group(target_type, target_code, period)
        items = [dict(item) for item in group.drawings or []]
        index = next((i for i, item in enumerate(items) if item.get("label") == label), None)
        if index is None:
            raise NotFoundError(f"AI 画线 {label} 不存在")
        drawing_type = items[index].get("drawing_type", "")
        if new_label:
            new_label = new_label.strip()
            if not new_label or len(new_label) > 100:
                raise BadRequestError("new_label 必须为 1-100 字符")
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
        self, target_type: str, target_code: str, period: str, label: str
    ) -> None:
        """按 label 删除单条 AI 画线（Delete 键）。"""
        group = await self._require_ai_group(target_type, target_code, period)
        items = [item for item in group.drawings or [] if item.get("label") != label]
        if len(items) == len(group.drawings or []):
            raise NotFoundError(f"AI 画线 {label} 不存在")
        group.drawings = items
        await self.session.commit()

    async def _require_ai_group(
        self, target_type: str, target_code: str, period: str
    ) -> AiKlineDrawing:
        group = await self.ai_repo.get_group(target_type, target_code, period)
        if group is None:
            raise NotFoundError("AI 画线组不存在")
        return group

    # ---------- 采纳 ----------

    async def adopt_ai_drawing(
        self, user_id: int, request: AiKlineDrawingAdoptRequest
    ) -> UserKlineDrawingResponse:
        """AI 画线单条采纳：按 label 定位，复制为用户画线（原 AI 画线保留）。"""
        group = await self.ai_repo.get_group(
            request.target_type, request.target_code, request.period
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
