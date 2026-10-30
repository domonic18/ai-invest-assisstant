"""MCP 工具集（docs/requirement/10 §5）。

工具层只做三件事：Scope 校验、参数解析、复用服务层取数后裁剪输出。
开放范围：9 个只读工具（P0）+ 6 个自选股工具（P1，读写 scope 分离）；
交易写操作（下单/计划）与 LLM 生成入口不在此开放。业务失败返回
``{"error": ...}``，鉴权/越权以 ``ToolError`` 返回（客户端可区分协议错误与业务空态）。
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
    API_KEY_SCOPE_WATCHLIST_READ,
    API_KEY_SCOPE_WATCHLIST_WRITE,
)
from app.core.database import AsyncSessionLocal

_MAX_ANOMALY_LIMIT = 50
_MAX_WATCHLIST_BATCH = 50


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


def _group_payload(group: Any) -> dict[str, Any]:
    return {
        "id": group.id,
        "name": group.name,
        "is_default": group.is_default,
        "ai_review_enabled": group.ai_review_enabled,
        "stock_count": len(group.items),
    }


async def list_watchlist_groups() -> dict[str, Any]:
    """列出自选股分组（名称、是否默认、AI 复盘开关、股票数量）。"""
    user_id = _require_scope(API_KEY_SCOPE_WATCHLIST_READ)

    from app.services.user.watchlist_service import WatchlistService

    async with AsyncSessionLocal() as session:
        groups = await WatchlistService(session).list_groups_with_items(user_id)
    return {"groups": [_group_payload(group) for group in groups]}


async def get_watchlist(group_name: str | None = None) -> dict[str, Any]:
    """读取当前用户自选股（名称+代码+市场+加入日期），可按分组名精确过滤。

    Args:
        group_name: 分组名，如「日周60」；缺省返回全部分组。
    """
    user_id = _require_scope(API_KEY_SCOPE_WATCHLIST_READ)

    from app.repositories.market.stock_repository import StockRepository
    from app.services.user.watchlist_service import WatchlistService

    async with AsyncSessionLocal() as session:
        groups = await WatchlistService(session).list_groups_with_items(user_id)
        names = await StockRepository(session).get_names_by_codes(
            [item.stock_code for group in groups for item in group.items]
        )
    payload = [
        {
            **_group_payload(group),
            "stocks": [
                {
                    "stock_code": item.stock_code,
                    "stock_name": names.get(item.stock_code),
                    "market": item.market,
                    "group_id": item.group_id,
                    "added_at": item.created_at.date().isoformat(),
                }
                for item in group.items
            ],
        }
        for group in groups
    ]

    if group_name is not None:
        matched = [group for group in payload if group["name"] == group_name]
        if not matched:
            return {
                "groups": [],
                "hint": (
                    f"未找到分组「{group_name}」，可用分组："
                    f"{[group['name'] for group in payload]}"
                ),
            }
        return {"groups": matched}
    return {"groups": payload}


async def add_watchlist_stocks(
    stock_codes: list[str],
    group_name: str | None = None,
    new_group_name: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """向自选股添加股票（写操作）。

    可指定已有分组（group_name）、新建分组（new_group_name）或落默认分组（都不传），
    两个分组参数互斥。重复股票不重复添加（归入 duplicated），代码不在主数据的
    归入 invalid。单次最多 50 只。

    Args:
        stock_codes: 股票代码列表，如 ["000001", "600519", "00700"]（港股 5 位）。
        group_name: 目标已有分组名。
        new_group_name: 新建分组名。
        tags: 附加标签列表。
    """
    user_id = _require_scope(API_KEY_SCOPE_WATCHLIST_WRITE)

    codes = list(
        dict.fromkeys(code.strip() for code in stock_codes if code and code.strip())
    )
    if not codes:
        return {"error": "stock_codes 不能为空"}
    if len(codes) > _MAX_WATCHLIST_BATCH:
        return {"error": f"单次最多添加 {_MAX_WATCHLIST_BATCH} 只股票"}
    if group_name and new_group_name:
        return {"error": "group_name 与 new_group_name 只能二选一"}

    from app.core.exceptions import AppError
    from app.models.user import User
    from app.schemas.user import WatchlistBatchCreate, WatchlistBatchItemCreate
    from app.services.user.watchlist_service import WatchlistService

    async with AsyncSessionLocal() as session:
        service = WatchlistService(session)
        group_id: int | None = None
        if group_name:
            group = await service.get_group_by_name(user_id, group_name)
            if group is None:
                groups = await service.list_groups_with_items(user_id)
                return {
                    "error": f"未找到分组「{group_name}」",
                    "available_groups": [item.name for item in groups],
                }
            group_id = group.id
        user = await session.get(User, user_id)
        if user is None:
            return {"error": "账号不存在或已删除"}
        try:
            result = await service.batch_add_items(
                user,
                WatchlistBatchCreate(
                    items=[
                        WatchlistBatchItemCreate(stock_code=code, tags=tags)
                        for code in codes
                    ],
                    group_id=group_id,
                    new_group_name=new_group_name,
                ),
            )
        except AppError as exc:
            return {"error": str(exc)}
    return result.model_dump(mode="json")


async def remove_watchlist_stocks(
    stock_codes: list[str],
    group_name: str | None = None,
) -> dict[str, Any]:
    """从自选股删除股票（写操作，不可恢复）。

    返回 removed / not_found / mismatch 三类结果；给定 group_name 时不属于
    该分组的代码不会删除，而列入 mismatch 并附实际所在分组。

    Args:
        stock_codes: 股票代码列表。
        group_name: 可选分组名校验。
    """
    user_id = _require_scope(API_KEY_SCOPE_WATCHLIST_WRITE)

    codes = list(
        dict.fromkeys(code.strip() for code in stock_codes if code and code.strip())
    )
    if not codes:
        return {"error": "stock_codes 不能为空"}

    from app.core.exceptions import AppError
    from app.services.user.watchlist_service import WatchlistService

    async with AsyncSessionLocal() as session:
        try:
            return await WatchlistService(session).remove_watchlist_stocks(
                user_id, codes, group_name
            )
        except AppError as exc:
            return {"error": str(exc)}


async def move_watchlist_stock(
    stock_code: str,
    target_group_name: str,
) -> dict[str, Any]:
    """把一只自选股移动到目标分组（写操作）。

    Args:
        stock_code: 股票代码（须已在自选股中）。
        target_group_name: 目标分组名。
    """
    user_id = _require_scope(API_KEY_SCOPE_WATCHLIST_WRITE)
    code = stock_code.strip()
    if not code:
        return {"error": "stock_code 不能为空"}

    from app.core.exceptions import AppError
    from app.services.user.watchlist_service import WatchlistService

    async with AsyncSessionLocal() as session:
        service = WatchlistService(session)
        target = await service.get_group_by_name(user_id, target_group_name)
        if target is None:
            groups = await service.list_groups_with_items(user_id)
            return {
                "error": f"未找到分组「{target_group_name}」",
                "available_groups": [item.name for item in groups],
            }
        item = await service.get_item_by_stock_code(user_id, code)
        if item is None:
            return {"error": f"自选股中不存在 {code}，请先用 add_watchlist_stocks 添加"}
        previous_group_id = item.group_id
        try:
            moved = await service.move_watchlist_item(user_id, item.id, target.id)
        except AppError as exc:
            return {"error": str(exc)}
    return {
        "stock_code": moved.stock_code,
        "group_id": moved.group_id,
        "group_name": target.name,
        "previous_group_id": previous_group_id,
    }


async def manage_watchlist_group(
    action: str,
    name: str,
    new_name: str | None = None,
    delete_items: bool = False,
) -> dict[str, Any]:
    """管理自选股分组（写操作）：create 新建 / rename 改名 / delete 删除。

    默认分组不可改名或删除；删除非空分组时 delete_items=False 会把组内
    股票移入默认分组，True 则连同股票一起删除。

    Args:
        action: create / rename / delete。
        name: 目标分组名（rename/delete 为现有名称）。
        new_name: rename 时的新名称。
        delete_items: delete 时是否连同组内股票一起删除。
    """
    user_id = _require_scope(API_KEY_SCOPE_WATCHLIST_WRITE)
    if action not in ("create", "rename", "delete"):
        return {"error": f"无效的 action：{action}（应为 create / rename / delete）"}
    if action == "rename" and not new_name:
        return {"error": "rename 需要提供 new_name"}
    if not name.strip():
        return {"error": "name 不能为空"}

    from app.core.exceptions import AppError
    from app.schemas.user import WatchlistGroupCreate, WatchlistGroupUpdate
    from app.services.user.watchlist_service import WatchlistService

    async with AsyncSessionLocal() as session:
        service = WatchlistService(session)
        try:
            if action == "create":
                group = await service.create_group(
                    user_id, WatchlistGroupCreate(name=name.strip())
                )
                return {"action": action, "group": _group_payload(group)}
            existing = await service.get_group_by_name(user_id, name.strip())
            if existing is None:
                groups = await service.list_groups_with_items(user_id)
                return {
                    "error": f"未找到分组「{name}」",
                    "available_groups": [item.name for item in groups],
                }
            if action == "rename":
                updated = await service.update_group(
                    user_id,
                    existing.id,
                    WatchlistGroupUpdate(name=new_name),
                )
                return {"action": action, "group": _group_payload(updated)}
            await service.delete_group(
                user_id, existing.id, delete_items=delete_items
            )
        except AppError as exc:
            return {"error": str(exc)}
    return {
        "action": action,
        "deleted": True,
        "group_name": name.strip(),
        "delete_items": delete_items,
    }


def register_tools(mcp: FastMCP) -> None:
    """把工具注册到 FastMCP 实例（工具描述取函数 docstring）。"""
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
        list_watchlist_groups,
        get_watchlist,
        add_watchlist_stocks,
        remove_watchlist_stocks,
        move_watchlist_stock,
        manage_watchlist_group,
    ):
        mcp.add_tool(fn)
