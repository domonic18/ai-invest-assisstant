"""K 线 AI 画线写入工具（kline-smart-drawing skill 专用，F-DRAW-07）。

写路径人工优先：写前必须已经 ``get_kline_drawings`` 检查并（必要时）
``ask_user`` 确认处理策略；锚点 date 必须真实存在于该标的的交易日序列
（防 LLM 幻觉日期），校验失败以错误反馈供模型自纠。
"""

import math
from datetime import date
from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from sqlalchemy import select

from app.agent.tools.page_event import page_event
from app.constants.drawing import (
    AI_DRAWING_MAX_ITEMS,
    DRAWING_DIRECTIONS,
    DRAWING_LABEL_MAX,
    DRAWING_TARGET_TYPES,
    DRAWING_TYPES,
    KLINE_DRAWING_PERIODS,
    REQUIRED_ANCHORS,
)
from app.core.database import AsyncSessionLocal

_SKILL_ID = "kline-smart-drawing"


async def _target_trade_dates(
    target_type: str, target_code: str, limit: int = 800
) -> set[str]:
    """标的近端交易日集合（ISO 字符串）；空集合表示标的无 K 线数据。"""
    from app.models.kline import KlineDaily, SectorKlineDaily

    async with AsyncSessionLocal() as session:
        if target_type == "sector":
            rows = await session.execute(
                select(SectorKlineDaily.trade_date)
                .where(SectorKlineDaily.sector_code == target_code)
                .order_by(SectorKlineDaily.trade_date.desc())
                .limit(limit)
            )
        else:
            rows = await session.execute(
                select(KlineDaily.trade_date)
                .where(KlineDaily.stock_code == target_code)
                .order_by(KlineDaily.trade_date.desc())
                .limit(limit)
            )
        return {row[0].isoformat() for row in rows.all()}


def _validate_items(drawings: list[dict[str, Any]], trade_dates: set[str]) -> str | None:
    """逐项校验画线（类型/锚点数/锚点取值/label/reason）；返回错误文本或 None。"""
    if not trade_dates:
        return "该标的无 K 线数据，无法画线；请先确认标的代码是否正确"
    labels: set[str] = set()
    for i, item in enumerate(drawings, start=1):
        dtype = item.get("drawing_type")
        if dtype not in DRAWING_TYPES:
            return f"第 {i} 条 drawing_type 非法：{dtype}（须为 {sorted(DRAWING_TYPES)}）"
        anchors = item.get("anchors")
        if not isinstance(anchors, list) or len(anchors) != REQUIRED_ANCHORS[dtype]:
            return f"第 {i} 条（{dtype}）需要 {REQUIRED_ANCHORS[dtype]} 个锚点"
        for j, anchor in enumerate(anchors, start=1):
            price = anchor.get("price")
            if not isinstance(price, (int, float)) or not math.isfinite(price):
                return f"第 {i} 条锚点 {j} 的 price 必须是有限数值"
            anchor_date = anchor.get("date") or ""
            if dtype == "hline":
                if anchor_date:
                    return "水平线锚点不需要 date（price only）"
                continue
            if anchor_date not in trade_dates:
                return (
                    f"第 {i} 条锚点 {j} 的 date（{anchor_date}）不是该标的真实交易日；"
                    "请改用工具取数返回中的真实 K 线日期"
                )
        direction = item.get("direction")
        if direction is not None and direction not in DRAWING_DIRECTIONS:
            return f"第 {i} 条 direction 非法：{direction}"
        label = str(item.get("label", "")).strip()
        if not label or len(label) > DRAWING_LABEL_MAX:
            return f"第 {i} 条 label 必须为 1-{DRAWING_LABEL_MAX} 字符（组内唯一，作为锚点语义标识）"
        if label in labels:
            return f"label「{label}」在组内重复（append 模式按 label 原位替换，须唯一）"
        labels.add(label)
        reason = str(item.get("reason", "")).strip()
        if not reason or len(reason) > 200:
            return f"第 {i} 条 reason 必须为 1-200 字符（一句话依据）"
    return None


@tool
async def persist_ai_kline_drawings(
    config: Annotated[RunnableConfig, InjectedToolArg],
    target_type: str,
    target_code: str,
    period: str,
    drawings: list[dict[str, Any]],
    mode: str = "replace",
    summary: str | None = None,
    sector_type: str | None = None,
) -> dict[str, Any]:
    """写入 AI K 线画线集，图表 AI 图层自动刷新展示（kline-smart-drawing 专用）。

    调用前置（必须已满足）：先 ``get_kline_drawings`` 检查已有画线；发现已有
    **用户画线**时必须先 ``ask_user`` 让用户确认处理策略，未确认不得调用本工具；
    删除用户画线类操作只能提示用户手动处理，本工具不触碰用户画线。

    Args:
        target_type: "stock"（个股）/ "index"（指数）/ "sector"（板块）。
        target_code: 股票 6 位代码（"600519"）/ 指数代码（"sh000001"）/ THS 板块代码（"881125"）。
        period: "daily" / "weekly" / "monthly"。
        drawings: 画线数组（1-20 条），每项：
            {"drawing_type": "trendline|ray|hline|box|text",
             "anchors": [{"date": "YYYY-MM-DD", "price": 数值}]（hline 仅 price，date 留空串），
             "direction": "left|right|both"（仅 ray 可选，默认 right），
             "label": "简短唯一标识，如 近半年压力位",
             "reason": "一句话依据，如 两测 21.4 放量回落"}。
            date 必须是该标的真实交易日（以工具取数返回的 K 线日期为准）。
        mode: "replace" 整组重画 / "append" 保留已有 AI 画线并新增（label 撞名原位替换）。
        summary: 可选整组摘要（一句话，说明本组画线的分析口径）。
        sector_type: 板块类型 "industry" / "concept"（仅 target_type=sector 时用于前端导航）。
    """
    from app.schemas.drawing import AiKlineDrawingItemSchema
    from app.services.market.kline_drawing_service import KlineDrawingService

    user_id = int(config.get("configurable", {}).get("user_id", 0))
    if not user_id:
        return {"error": "无法识别当前用户（缺少会话属主），拒绝写入画线"}

    if target_type not in DRAWING_TARGET_TYPES:
        return {"error": f"target_type 须为 {sorted(DRAWING_TARGET_TYPES)} 之一"}
    if period not in KLINE_DRAWING_PERIODS:
        return {"error": f"period 须为 {sorted(KLINE_DRAWING_PERIODS)} 之一"}
    if mode not in ("replace", "append"):
        return {"error": 'mode 须为 "replace" 或 "append"'}
    if not drawings:
        return {"error": "drawings 不能为空（不画线时无需调用本工具）"}
    if len(drawings) > AI_DRAWING_MAX_ITEMS:
        return {"error": f"drawings 最多 {AI_DRAWING_MAX_ITEMS} 条"}
    code = target_code.strip()
    if not code:
        return {"error": "target_code 不能为空"}

    trade_dates = await _target_trade_dates(target_type, code)
    if (error := _validate_items(drawings, trade_dates)) is not None:
        return {"error": error}

    items = [
        AiKlineDrawingItemSchema.model_validate(
            {
                "drawing_type": item["drawing_type"],
                "anchors": item["anchors"],
                "direction": item.get("direction"),
                "label": str(item["label"]).strip(),
                "reason": str(item["reason"]).strip(),
            }
        )
        for item in drawings
    ]
    async with AsyncSessionLocal() as session:
        service = KlineDrawingService(session)
        group = await service.upsert_ai_group(
            user_id=user_id,
            target_type=target_type,
            target_code=code,
            period=period,
            skill_id=_SKILL_ID,
            trade_date=date.fromisoformat(max(trade_dates)),
            drawings=items,
            mode=mode,
            summary=summary,
        )
    return {
        "target_type": target_type,
        "target_code": code,
        "period": period,
        "mode": mode,
        "count": len(group.drawings),
        "__event__": page_event(
            "kline_drawing.complete",
            target_type=target_type,
            target_code=code,
            period=period,
            count=len(group.drawings),
            sector_type=sector_type,
        ),
    }
