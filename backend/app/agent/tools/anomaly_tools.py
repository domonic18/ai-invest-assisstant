"""异动查询与归因持久化助手工具（归因持久化仅助手对话路径注入）。"""

from datetime import date
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel

from app.agent.tools.page_event import page_event
from app.core.database import AsyncSessionLocal
from app.services.market import anomaly_attribution_service
from app.services.market.anomaly_common import AnomalyInputNotReadyError


def _parse_trade_date(value: str | None) -> tuple[date | None, str | None]:
    """解析可选 ISO 日期参数；返回 (日期, None) 或 (None, 错误提示)。"""
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "trade_date 须为 YYYY-MM-DD 格式"


class SectorAttributionArgs(BaseModel):
    """persist_sector_anomaly_attribution 的单条归因参数。"""

    sector_type: str
    sector_code: str
    category: str
    summary: str


class StockAttributionArgs(BaseModel):
    """persist_stock_anomaly_attribution 的单条归因参数。"""

    stock_code: str
    category: str
    summary: str


@tool
async def get_sector_anomaly(trade_date: str) -> dict[str, Any]:
    """获取当日板块异动信号（行业+概念合并，按异动强度降序 TOP10），供资金面与板块异动对照分析。

    Args:
        trade_date: 交易日期，ISO 格式如 "2026-09-17"。
    """
    from app.services.market import sector_anomaly_service

    resolved, error = _parse_trade_date(trade_date)
    if error or resolved is None:
        return {"error": "trade_date 须为 YYYY-MM-DD 格式"}
    async with AsyncSessionLocal() as session:
        response = await sector_anomaly_service.get_sector_anomaly_board(
            session, resolved, None
        )

    if response is None or not response.items:
        return {
            "trade_date": resolved.isoformat(),
            "items": [],
            "note": "当日无板块异动检测数据，资金面分区应如实说明，不得臆测异动方向。",
        }
    items = [
        {
            "sector_name": item.sector_name,
            "sector_type": item.sector_type,
            "change_pct": item.change_pct,
            "amount_ratio": item.amount_ratio,
            "anomaly_types": item.anomaly_types,
            "strength": item.strength,
            "attribution_summary": item.attribution_summary,
        }
        for item in response.items[:10]
    ]
    return {
        "trade_date": response.trade_date.isoformat(),
        "total": response.total,
        "items": items,
        "note": (
            f"共 {response.total} 个板块当日触发异动，已按异动强度降序返回前 {len(items)} 个；"
            "请与主力资金流向对照：净流入∧异动=主线确认，异动∧净流出=冲高回落/诱多风险。"
        ),
    }


@tool
async def persist_sector_anomaly_attribution(
    trade_date: str, items: list[SectorAttributionArgs]
) -> dict[str, Any]:
    """持久化板块异动 AI 归因结果到数据库，异动页归因摘要会自动刷新。

    Args:
        trade_date: 交易日（YYYY-MM-DD）。
        items: 归因条目列表。sector_type 为 "industry" 或 "concept"，sector_code
            为板块代码，category 取 resonance（趋势共振）或 rotation（轮动补涨），
            必须来自当日板块异动检测清单；summary 为 1-2 句简体中文归因摘要。
    """
    from app.services.admin.llm_config_service import resolve_default_llm

    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}
    assert resolved is not None

    async with AsyncSessionLocal() as session:
        cfg = await resolve_default_llm(session)
        try:
            result = await anomaly_attribution_service.persist_manual_attribution(
                session,
                "sector",
                resolved,
                [item.model_dump() for item in items],
                model=f"{cfg.provider}/{cfg.model_name}",
            )
        except (AnomalyInputNotReadyError, ValueError) as exc:
            return {"error": str(exc)}

    return {
        **result,
        "trade_date": resolved.isoformat(),
        "__event__": page_event(
            "sector_anomaly.complete",
            trade_date=resolved.isoformat(),
        ),
    }


@tool
async def persist_stock_anomaly_attribution(
    trade_date: str, items: list[StockAttributionArgs]
) -> dict[str, Any]:
    """持久化个股异动 AI 归因结果到数据库，异动页归因摘要会自动刷新。

    Args:
        trade_date: 交易日（YYYY-MM-DD）。
        items: 归因条目列表。stock_code 为 6 位代码，category 取 breakout
            （趋势突破启动）、acceleration（趋势内加速）或 pullback（下跌反抽），
            必须来自当日个股异动检测清单；summary 为 1-2 句简体中文归因摘要。
    """
    from app.services.admin.llm_config_service import resolve_default_llm

    resolved, error = _parse_trade_date(trade_date)
    if error:
        return {"error": error}
    assert resolved is not None

    async with AsyncSessionLocal() as session:
        cfg = await resolve_default_llm(session)
        try:
            result = await anomaly_attribution_service.persist_manual_attribution(
                session,
                "stock",
                resolved,
                [item.model_dump() for item in items],
                model=f"{cfg.provider}/{cfg.model_name}",
            )
        except (AnomalyInputNotReadyError, ValueError) as exc:
            return {"error": str(exc)}

    return {
        **result,
        "trade_date": resolved.isoformat(),
        "__event__": page_event(
            "stock_anomaly.complete",
            trade_date=resolved.isoformat(),
        ),
    }
