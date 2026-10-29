"""MCP 只读工具集（docs/requirement/10 §5）。

工具层只做三件事：Scope 校验、参数解析、复用服务层取数后裁剪输出。
写操作与 LLM 生成入口不在此开放；业务失败返回 ``{"error": ...}``，
鉴权/越权以 ``ToolError`` 返回（客户端可区分协议错误与业务空态）。
"""

from datetime import date
from typing import Any, cast

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.core.config import get_settings
from app.core.constants import (
    API_KEY_SCOPE_KB_READ,
    API_KEY_SCOPE_MARKET_READ,
    API_KEY_SCOPE_TRADING_READ,
)
from app.core.database import AsyncSessionLocal

_MAX_ANOMALY_LIMIT = 50


def _require_scope(scope: str) -> int:
    """取当前请求的用户身份并校验 Scope，返回 user_id。"""
    token = get_access_token()
    claims = token.claims if token is not None else None
    user_id = (claims or {}).get("user_id")
    if token is None or user_id is None:
        raise ToolError("MCP 调用缺少有效身份，请检查 Authorization: Bearer <API Key>")
    if scope not in (token.scopes or []):
        raise ToolError(f"当前 API Key 缺少权限范围 {scope}")
    return int(user_id)


def _parse_date(value: str | None, name: str = "trade_date") -> tuple[date | None, str | None]:
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, f"无效的 {name}：{value}（应为 YYYY-MM-DD）"


def _agent_key(value: str | None) -> str:
    return value or get_settings().mcp_default_agent_key


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_ANOMALY_LIMIT))


async def get_market_daily_review(
    trade_date: str | None = None,
) -> dict[str, Any]:
    """读取 AI 大盘每日复盘（只读，不触发生成）。

    Args:
        trade_date: 交易日 YYYY-MM-DD，缺省取最新交易日。
    """
    user_id = _require_scope(API_KEY_SCOPE_MARKET_READ)
    day, error = _parse_date(trade_date)
    if error:
        return {"error": error}

    from app.core.exceptions import AppError
    from app.services.review import market_review_service

    try:
        async with AsyncSessionLocal() as session:
            review = await market_review_service.get_market_review(session, user_id, day)
    except AppError as exc:
        return {"error": str(exc)}
    if review is None:
        return {
            "trade_date": day.isoformat() if day else None,
            "not_ready": True,
            "note": "该交易日大盘复盘尚未生成（盘后定时任务生成，或等待数据就绪）。",
        }
    return review.model_dump(mode="json")


async def get_sector_anomaly(
    trade_date: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """获取板块异动榜（行业+概念，按异动强度降序）。

    Args:
        trade_date: 交易日 YYYY-MM-DD，缺省取最新检测日。
        limit: 返回条数上限（1-50，默认 20）。
    """
    _require_scope(API_KEY_SCOPE_MARKET_READ)
    day, error = _parse_date(trade_date)
    if error:
        return {"error": error}

    from app.services.market import sector_anomaly_service

    async with AsyncSessionLocal() as session:
        response = await sector_anomaly_service.get_sector_anomaly_board(session, day)
    if response is None or not response.items:
        return {
            "trade_date": day.isoformat() if day else None,
            "items": [],
            "note": "当日无板块异动检测数据。",
        }
    payload = response.model_dump(mode="json")
    payload["items"] = payload["items"][:_clamp_limit(limit)]
    payload["returned"] = len(payload["items"])
    return payload


async def get_stock_anomaly(
    trade_date: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """获取个股异动榜（按异动强度降序，命中当前用户自选股的条目标注 is_watchlist）。

    Args:
        trade_date: 交易日 YYYY-MM-DD，缺省取最新检测日。
        limit: 返回条数上限（1-50，默认 20）。
    """
    user_id = _require_scope(API_KEY_SCOPE_MARKET_READ)
    day, error = _parse_date(trade_date)
    if error:
        return {"error": error}

    from app.services.market import stock_anomaly_service

    async with AsyncSessionLocal() as session:
        response = await stock_anomaly_service.get_stock_anomaly_board(
            session, day, user_id
        )
    if response is None or not response.items:
        return {
            "trade_date": day.isoformat() if day else None,
            "items": [],
            "note": "当日无个股异动检测数据。",
        }
    payload = response.model_dump(mode="json")
    payload["items"] = payload["items"][:_clamp_limit(limit)]
    payload["returned"] = len(payload["items"])
    return payload


async def get_social_sentiment(
    trade_date: str | None = None,
) -> dict[str, Any]:
    """获取抖音大V散户情绪聚合（多空中性分布、近 7 日净多空、代表观点）。

    散户情绪是反向指标：显著净看多且升温=情绪亢奋；净看空/冰点=情绪低位。
    ``sample_insufficient`` 为真时结论不足为凭。

    Args:
        trade_date: 交易日 YYYY-MM-DD，缺省取最新交易日。
    """
    _require_scope(API_KEY_SCOPE_MARKET_READ)
    day, error = _parse_date(trade_date)
    if error:
        return {"error": error}

    from app.services.market import trade_calendar_service
    from app.services.social import feed_service

    async with AsyncSessionLocal() as session:
        resolved = day or await trade_calendar_service.resolve_latest_trade_date(session)
        return await feed_service.get_review_sentiment(session, resolved)


async def get_trading_account(
    agent_key: str | None = None,
) -> dict[str, Any]:
    """查询交易 Agent 专属模拟盘账户：资金概况、当前持仓、未结委托。

    Args:
        agent_key: 交易 Agent key，缺省取平台默认 Agent（short-line）。
    """
    _require_scope(API_KEY_SCOPE_TRADING_READ)

    from app.core.exceptions import AppError
    from app.services.trading.account_service import resolve_agent_account
    from app.services.trading.paper_trade_service import get_overview

    async with AsyncSessionLocal() as session:
        try:
            account = await resolve_agent_account(session, _agent_key(agent_key))
            return await get_overview(session, account)
        except AppError as exc:
            return {"error": str(exc)}


async def list_trading_plans(
    agent_key: str | None = None,
) -> dict[str, Any]:
    """查询交易 Agent 当日（最近计划日）全部交易计划及状态。

    Args:
        agent_key: 交易 Agent key，缺省取平台默认 Agent（short-line）。
    """
    _require_scope(API_KEY_SCOPE_TRADING_READ)

    from app.core.exceptions import AppError
    from app.services.trading import agent_plan_ops, agent_registry

    key = _agent_key(agent_key)
    async with AsyncSessionLocal() as session:
        try:
            await agent_registry.get_agent(session, key)
            plan_date = await agent_plan_ops.resolve_default_plan_date(session, key)
            rows = await agent_plan_ops.list_plans(session, key, plan_date=plan_date)
        except AppError as exc:
            return {"error": str(exc)}

    return {
        "agent_key": key,
        "trade_date": plan_date.isoformat(),
        "items": [
            {
                "id": row.id,
                "stock_code": row.stock_code,
                "plan_type": row.plan_type,
                "strategy": row.strategy,
                "buy_zone_low": float(row.buy_zone_low)
                if row.buy_zone_low is not None
                else None,
                "buy_zone_high": float(row.buy_zone_high)
                if row.buy_zone_high is not None
                else None,
                "target_price": float(row.target_price)
                if row.target_price is not None
                else None,
                "stop_loss": float(row.stop_loss),
                "position_pct": float(row.position_pct),
                "status": row.status,
                "triggered_cl_ord_id": row.triggered_cl_ord_id,
            }
            for row in rows
        ],
    }


async def get_trading_review(
    agent_key: str | None = None,
    period: str | None = None,
    trade_date: str | None = None,
    scope: str = "current",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """读取交易 Agent 已生成的分层复盘（只读，不触发生成）。

    Args:
        agent_key: 交易 Agent key，缺省取平台默认 Agent（short-line）。
        period: day / week / month / quarter / half_year / year；仅给区间时可省略。
        trade_date: 基准交易日 YYYY-MM-DD，缺省取最新交易日。
        scope: current 本期 / previous 上一完整周期。
        start_date/end_date: 自定义区间 YYYY-MM-DD（须成对）。
    """
    _require_scope(API_KEY_SCOPE_TRADING_READ)

    if scope not in ("current", "previous"):
        return {"error": f"无效的 scope：{scope}（应为 current 或 previous）"}
    if period is not None and period not in (
        "day",
        "week",
        "month",
        "quarter",
        "half_year",
        "year",
    ):
        return {"error": f"无效的 period：{period}"}

    parsed_date, date_error = _parse_date(trade_date)
    if date_error:
        return {"error": date_error}
    parsed_start, start_error = _parse_date(start_date, "start_date")
    if start_error:
        return {"error": start_error}
    parsed_end, end_error = _parse_date(end_date, "end_date")
    if end_error:
        return {"error": end_error}
    if (parsed_start is None) != (parsed_end is None):
        return {"error": "自定义区间须同时提供 start_date 与 end_date"}

    from app.core.exceptions import AppError
    from app.services.trading import agent_review_service
    from app.services.trading.agent_review_periods import ReviewPeriod
    from app.services.trading.agent_review_service import ReviewWindowScope

    key = _agent_key(agent_key)
    resolved_period = period or (None if parsed_start is not None else "day")
    try:
        async with AsyncSessionLocal() as session:
            content = await agent_review_service.get_review(
                session,
                key,
                period=cast(ReviewPeriod | None, resolved_period),
                trade_date=parsed_date,
                scope=cast(ReviewWindowScope, scope),
                start_date=parsed_start,
                end_date=parsed_end,
            )
    except AppError as exc:
        return {"error": str(exc)}
    if content is None:
        return {
            "agent_key": key,
            "not_ready": True,
            "note": "该窗口复盘尚未生成（日/周/月有盘后定时生成，其余需站内按需生成）。",
        }
    return content.model_dump(mode="json")


async def get_trading_selections(
    agent_key: str | None = None,
) -> dict[str, Any]:
    """查询交易 Agent 当前选股清单（含选入依据与置信度）。

    Args:
        agent_key: 交易 Agent key，缺省取平台默认 Agent（short-line）。
    """
    _require_scope(API_KEY_SCOPE_TRADING_READ)

    from app.core.exceptions import AppError
    from app.services.trading import agent_plan_ops, agent_registry

    key = _agent_key(agent_key)
    async with AsyncSessionLocal() as session:
        try:
            await agent_registry.get_agent(session, key)
            rows = await agent_plan_ops.list_active_selections(session, key)
        except AppError as exc:
            return {"error": str(exc)}

    return {
        "agent_key": key,
        "items": [
            {
                "id": row.id,
                "stock_code": row.stock_code,
                "reason": row.reason,
                "confidence": float(row.confidence)
                if row.confidence is not None
                else None,
                "trade_date": row.trade_date.isoformat(),
            }
            for row in rows
        ],
    }


async def search_knowledge_base(
    query: str,
    source: str | None = None,
    chapter: str | None = None,
    point_type: str | None = None,
    include_media: bool = False,
) -> dict[str, Any]:
    """检索投资课程知识库（形态/量价/趋势纪律等方法论卡片与原文片段）。

    Args:
        query: 检索语句，如 "均线金叉的买入纪律"。
        source: 知识库名称过滤；不传搜全部。
        chapter: 章节路径过滤，层级用 / 连接，如 "第二讲/均线系统"。
        point_type: concept / theorem / method / discipline / case。
        include_media: 是否附带视频起播点/书籍页码定位。
    """
    _require_scope(API_KEY_SCOPE_KB_READ)

    from app.agent.tools.kb_tools import search_knowledge_base_data

    return await search_knowledge_base_data(
        query, source, chapter, point_type, include_media
    )


def register_tools(mcp: FastMCP) -> None:
    """把只读工具注册到 FastMCP 实例（工具描述取函数 docstring）。"""
    for fn in (
        get_market_daily_review,
        get_sector_anomaly,
        get_stock_anomaly,
        get_social_sentiment,
        get_trading_account,
        list_trading_plans,
        get_trading_review,
        get_trading_selections,
        search_knowledge_base,
    ):
        mcp.add_tool(fn)
