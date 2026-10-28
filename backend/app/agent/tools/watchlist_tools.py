"""用户自选股分组读写助手工具（user_id 经 configurable 注入，多租户安全）。"""

from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool

from app.core.database import AsyncSessionLocal


def _current_user_id(config: RunnableConfig) -> int:
    """从运行时 configurable 提取当前用户 ID（assistant/runs 统一注入）。"""
    return int(config.get("configurable", {}).get("user_id", 0))


@tool
async def get_user_watchlist(
    config: Annotated[RunnableConfig, InjectedToolArg],
    group_name: str | None = None,
) -> dict[str, Any]:
    """读取当前用户的自选股分组与股票列表（名称+代码+市场+加入日期）。

    Args:
        group_name: 可选分组名精确过滤（如「日周60」）；缺省返回全部分组。
        config: LangGraph 运行时配置，自动注入当前用户 ID。
    """
    from app.repositories.market.stock_repository import StockRepository
    from app.services.user.watchlist_service import WatchlistService

    user_id = _current_user_id(config)
    async with AsyncSessionLocal() as session:
        groups = await WatchlistService(session).list_groups_with_items(user_id)
        names = await StockRepository(session).get_names_by_codes(
            [item.stock_code for group in groups for item in group.items]
        )
        payload = [
            {
                "name": group.name,
                "is_default": group.is_default,
                "ai_review_enabled": group.ai_review_enabled,
                "stocks": [
                    {
                        "stock_code": item.stock_code,
                        "stock_name": names.get(item.stock_code),
                        "market": item.market,
                        "added_at": item.created_at.date().isoformat(),
                    }
                    for item in group.items
                ],
            }
            for group in groups
        ]

    if group_name is not None:
        matched = [g for g in payload if g["name"] == group_name]
        if not matched:
            return {
                "groups": [],
                "hint": f"未找到分组「{group_name}」，可用分组：{[g['name'] for g in payload]}",
            }
        return {"groups": matched}
    return {"groups": payload}


@tool
async def remove_watchlist_stocks(
    config: Annotated[RunnableConfig, InjectedToolArg],
    stock_codes: list[str],
    group_name: str | None = None,
) -> dict[str, Any]:
    """从当前用户自选中删除股票（写操作，不可恢复）。

    分析类任务执行删除前，必须先经 ask_user 向用户展示拟删清单并确认；
    仅当用户明确要求删除时才可直接调用。

    Args:
        stock_codes: 6 位股票代码列表，如 ["000001", "600519"]。
        group_name: 可选分组名校验（如「日周60」）；给定时不属于该分组的
            代码不会被删除，而列入 mismatch 并附实际所在分组。
        config: LangGraph 运行时配置，自动注入当前用户 ID。
    """
    from app.core.exceptions import NotFoundError
    from app.services.user.watchlist_service import WatchlistService

    user_id = _current_user_id(config)
    try:
        async with AsyncSessionLocal() as session:
            result = await WatchlistService(session).remove_watchlist_stocks(
                user_id, stock_codes, group_name
            )
    except NotFoundError:
        return {"error": f"分组「{group_name}」不存在，请先用 get_user_watchlist 确认分组名"}
    return result
