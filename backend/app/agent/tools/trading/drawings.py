"""交易 Agent 画线渲染工具（数据能力补齐批次 2：看图解读 + 写后自检）。

渲染该标的「用户 + AI 双图层」画线为 K 线截图（服务端 pillow 自绘），上传
MinIO 返回预签名 URL。图像消费双路径（D-V3）：

- 绑定模型出口具备视觉能力（管理后台 ``extra.capabilities.vision``）时，
  经 ToolMessage content blocks 直进会话上下文——模型亲眼看图；
- 否则降级 ``run_structured(vision=True)`` 系统视觉槽位独立看图，返回结构化
  文本结论（KB 截图识别同款机制）。

前端聊天图片渲染独立后置（D-V4），URL 文本兜底供用户点开核对。
"""

import base64
import json
import time
from typing import Annotated, Any

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, InjectedToolArg, tool
from pydantic import BaseModel

from app.constants.drawing import KLINE_DRAWING_PERIODS
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError
from app.services.common.minio_service import get_minio_service
from app.services.market.kline_drawing_render import (
    AI_PALETTE,
    PERIOD_LABELS,
    RenderableDrawing,
    render_kline_png,
)
from app.services.market.kline_drawing_service import KlineDrawingService
from app.services.market.kline_service import get_stock_kline

logger = structlog.get_logger(__name__)

_KLINE_MIN_BARS = 30
_KLINE_MAX_BARS = 250

_VISUAL_PROMPT = """你是 K 线画线视觉审查员。下图是个股 K 线蜡烛图与「用户/AI 画线」叠加的截图，画线清单（图层/类型/标签/锚点）如下 JSON。

请逐条读图：每条线的标签、类型、锚点日期与价格，线是否触及 K 线高点/低点、是否穿越箱体或压在关键位上；并指出画歪、锚点漂移、标签与实际线条不符等问题。只依据图中可见内容判断，禁止编造图中不存在的线或价位。

画线清单：
{drawings_json}"""


class DrawingVisualRead(BaseModel):
    """单条画线的视觉读图结论。"""

    label: str
    kind: str
    reading: str


class KlineDrawingVisualCheck(BaseModel):
    """视觉槽位看图结论（降级路径的结构化契约）。"""

    summary: str
    readings: list[DrawingVisualRead]
    anomalies: list[str]


async def _bound_model_supports_vision(agent_key: str) -> bool:
    """绑定模型出口是否标记视觉能力（判定失败一律降级走视觉槽位）。"""
    from app.agent.runtime.trading_agent import resolve_trading_llm
    from app.services.trading.agent_registry import get_agent

    try:
        async with AsyncSessionLocal() as session:
            row = await get_agent(session, agent_key)
            cfg = await resolve_trading_llm(row.llm_config_id)
    except Exception:  # noqa: BLE001
        logger.warning("trading_agent_vision_probe_failed", agent_key=agent_key)
        return False
    return bool((cfg.extra or {}).get("capabilities", {}).get("vision"))


def make_render_kline_drawings_tool(agent_key: str) -> BaseTool:
    """按 agent_key 闭包绑定（双路径消费需判定「该 Agent 绑定模型」的视觉能力）。"""

    @tool(response_format="content_and_artifact")
    async def render_kline_drawings(
        config: Annotated[RunnableConfig, InjectedToolArg],
        target_type: str,
        target_code: str,
        period: str = "daily",
        limit: int = 120,
    ) -> tuple[list[dict[str, Any]], None]:
        """渲染 K 线画线截图并看图（解读用户画线 / AI 画线写后自检必调）。

        将该标的当前「用户 + AI 双图层」画线渲染为一张 K 线截图，返回图片与
        画线清单（含预签名 URL）。两类用途：
        1. 写后自检：``persist_ai_kline_drawings`` 之后必须调用本工具亲眼确认
           每条线落位（类型/锚点日期与价格/是否触及 K 线高低点），发现画歪或
           锚点漂移立即修正重画；
        2. 解读用户画线：以截图视觉为准读出每条线的类型与关键价位，结合 K 线
           结构给出压力/支撑是否成立的判断；结构化 JSON 可用
           ``get_kline_drawings`` 互证。

        Args:
            target_type: 仅支持 "stock"（个股）。
            target_code: 6 位股票代码，如 "600519"。
            period: "daily" / "weekly" / "monthly"，默认 "daily"。
            limit: K 线根数 30-250，默认 120。
        """
        meta: dict[str, Any] = {"target_type": target_type, "target_code": target_code}
        user_id = int(config.get("configurable", {}).get("user_id", 0))
        if not user_id:
            meta["error"] = "无法识别当前用户（缺少会话属主），拒绝渲染"
            return ([{"type": "text", "text": json.dumps(meta, ensure_ascii=False)}], None)
        if target_type != "stock":
            meta["error"] = "画线渲染当前仅支持个股（target_type=stock）"
            return ([{"type": "text", "text": json.dumps(meta, ensure_ascii=False)}], None)
        if period not in KLINE_DRAWING_PERIODS:
            meta["error"] = f"period 须为 {sorted(KLINE_DRAWING_PERIODS)} 之一"
            return ([{"type": "text", "text": json.dumps(meta, ensure_ascii=False)}], None)
        limit = max(_KLINE_MIN_BARS, min(int(limit), _KLINE_MAX_BARS))
        code = target_code.strip()
        meta["target_code"] = code

        try:
            async with AsyncSessionLocal() as session:
                kline = await get_stock_kline(session, code, period=period, limit=limit)
                resp = await KlineDrawingService(session).list_drawings(user_id, "stock", code)
        except BadRequestError as exc:
            meta["error"] = str(exc)
            return ([{"type": "text", "text": json.dumps(meta, ensure_ascii=False)}], None)
        bars = kline["bars"]
        if len(bars) < 2:
            meta["error"] = "该标的暂无 K 线数据，无法渲染"
            return ([{"type": "text", "text": json.dumps(meta, ensure_ascii=False)}], None)

        renderables: list[RenderableDrawing] = []
        for row in resp.user:
            if row.period != period:
                continue
            renderables.append(
                RenderableDrawing(
                    layer="user",
                    drawing_type=row.drawing_type,
                    anchors=tuple((a.date, a.price) for a in row.anchors),
                    direction=row.direction or "right",
                    label=row.text or "",
                    color=row.style.color,
                    line_style=row.style.line_style,
                    width=int(row.style.width),
                    text=row.text or "",
                )
            )
        palette_i = 0
        for group in resp.ai:
            if group.period != period:
                continue
            for item in group.drawings:
                renderables.append(
                    RenderableDrawing(
                        layer="ai",
                        drawing_type=item.drawing_type,
                        anchors=tuple((a.date, a.price) for a in item.anchors),
                        direction=item.direction or "right",
                        label=item.label,
                        color=AI_PALETTE[palette_i % len(AI_PALETTE)],
                        line_style="solid",
                        width=2,
                    )
                )
                palette_i += 1

        png = render_kline_png(
            bars,
            renderables,
            title_name=str(kline.get("name") or ""),
            title_code=code,
            period_label=PERIOD_LABELS[period],
        )
        object_name = f"kline-drawings/u{user_id}/{code}-{period}-{int(time.time())}.png"
        minio = get_minio_service()
        await minio.upload_file(object_name, png, content_type="image/png")
        meta.update(
            {
                "image_url": await minio.get_presigned_url(object_name),
                "period": period,
                "bar_count": len(bars),
                "drawing_count": len(renderables),
                "drawings": [
                    {
                        "layer": d.layer,
                        "label": d.label or d.drawing_type,
                        "drawing_type": d.drawing_type,
                        "direction": d.direction,
                        "anchors": [{"date": adate, "price": price} for adate, price in d.anchors],
                    }
                    for d in renderables
                ],
            }
        )

        if await _bound_model_supports_vision(agent_key):
            text_block = {"type": "text", "text": json.dumps(meta, ensure_ascii=False)}
            encoded = base64.b64encode(png).decode()
            image_block = {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            }
            return ([text_block, image_block], None)

        from app.agent.runtime.structured import run_structured
        from app.services.admin.llm_config_service import LLMConfigNotConfiguredError

        try:
            async with AsyncSessionLocal() as session:
                check = await run_structured(
                    session,
                    result_type=KlineDrawingVisualCheck,
                    user_prompt=_VISUAL_PROMPT.format(
                        drawings_json=json.dumps(meta["drawings"], ensure_ascii=False)
                    ),
                    images=[(png, "image/png")],
                    user_id=user_id,
                    vision=True,
                )
            meta["visual_check"] = {
                "summary": check.summary,
                "readings": [r.model_dump() for r in check.readings],
                "anomalies": list(check.anomalies),
            }
            meta["consumption"] = "vision_slot"
        except LLMConfigNotConfiguredError:
            meta["visual_check"] = None
            meta["consumption"] = "none"
            meta["note"] = "未配置视觉模型，仅返回截图链接与画线清单"
        return ([{"type": "text", "text": json.dumps(meta, ensure_ascii=False)}], None)

    return render_kline_drawings
