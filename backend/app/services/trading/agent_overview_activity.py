"""Agent 总览/能力视图的活动流与计数采集（确定性查询）。

近期计划/复盘活动条目组装（股票名批量回填，D30）、今日产出判定（复盘
done 集合 / 计划创建，D32）、当日订单数、活跃记忆计数。视图组装见
``agent_overview_service``。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trading import AgentMemory, AgentTradePlan
from app.models.ai_analysis_result import AiAnalysisResult
from app.models.paper_trade import PaperTradeOrder
from app.repositories.market.stock_repository import StockRepository
from app.schemas.paper_trade import AgentActivityItem, AgentMemoryCounts
from app.services.trading.account_service import resolve_agent_account
from app.services.trading.agent_review_service import REVIEW_SKILL_ID
from app.services.trading.errors import AgentAccountNotDesignatedError

_PLAN_STATUS_TITLE = {
    "active": "待触发",
    "triggered": "已触发下单",
    "cancelled": "已人工取消",
    "expired": "已过期",
}

_PLAN_TYPE_TITLE = {
    "buy": "买入计划",
    "sell": "卖出计划",
}


async def _review_done_keys(session: AsyncSession, day_start_cn: datetime) -> set[str]:
    """今日（北京墙钟）已生成分层复盘的 agent_key 集合。"""
    rows = (
        await session.scalars(
            select(AiAnalysisResult.structured_output["agent_key"].astext)
            .where(
                AiAnalysisResult.skill_id == REVIEW_SKILL_ID,
                AiAnalysisResult.status == "success",
                AiAnalysisResult.created_at >= day_start_cn,
                AiAnalysisResult.structured_output["agent_key"].astext.isnot(None),
            )
            .distinct()
        )
    ).all()
    return {str(r) for r in rows}


async def _plans_created_today(
    session: AsyncSession, agent_key: str, day_start_cn: datetime
) -> bool:
    """今日（北京墙钟）生成过交易计划（按计划行创建时刻计）。"""
    return bool(
        await session.scalar(
            select(func.count())
            .select_from(AgentTradePlan)
            .where(
                AgentTradePlan.agent_key == agent_key,
                AgentTradePlan.created_at >= day_start_cn,
            )
        )
    )


async def _plan_activity(
    session: AsyncSession, agent_key: str
) -> list[AgentActivityItem]:
    """近期计划活动（生成 + 触发/取消，created_at 倒序取 5；条目结构化
    携带 stock_code，股票名称由 ``_fill_stock_names`` 批量回填，D30）。"""
    rows = (
        await session.scalars(
            select(AgentTradePlan)
            .where(AgentTradePlan.agent_key == agent_key)
            .order_by(AgentTradePlan.created_at.desc())
            .limit(5)
        )
    ).all()
    return [
        AgentActivityItem(
            kind="plan",
            title=_PLAN_TYPE_TITLE.get(row.plan_type, f"{row.plan_type} 计划"),
            detail=_PLAN_STATUS_TITLE.get(row.status, row.status),
            stock_code=row.stock_code,
            occurred_at=row.triggered_at or row.created_at,
        )
        for row in rows
    ]


async def _fill_stock_names(
    session: AsyncSession, items: list[AgentActivityItem]
) -> list[AgentActivityItem]:
    """活动条目按 stock_code 批量回填股票名称（主数据缺失保持 None）。"""
    codes = sorted({item.stock_code for item in items if item.stock_code})
    if not codes:
        return items
    names = await StockRepository(session).get_names_by_codes(codes)
    for item in items:
        if item.stock_code:
            item.stock_name = names.get(item.stock_code)
    return items


async def _review_activity(
    session: AsyncSession, agent_key: str
) -> list[AgentActivityItem]:
    """近期复盘活动（ai_analysis_result 按 agent_key 结构化过滤取 3）。"""
    rows = (
        await session.scalars(
            select(AiAnalysisResult)
            .where(
                AiAnalysisResult.skill_id == REVIEW_SKILL_ID,
                AiAnalysisResult.status == "success",
                AiAnalysisResult.structured_output["agent_key"].astext == agent_key,
            )
            .order_by(AiAnalysisResult.created_at.desc())
            .limit(3)
        )
    ).all()
    items: list[AgentActivityItem] = []
    for row in rows:
        period = (row.structured_output or {}).get("period", "day")
        items.append(
            AgentActivityItem(
                kind="review",
                title=f"{period} 复盘已生成",
                detail=row.model,
                occurred_at=row.created_at,
            )
        )
    return items


async def _order_count_today(
    session: AsyncSession, agent_key: str, day_start_cn: datetime
) -> int:
    """Agent 账户当日订单数（未绑定账户记 0）。"""
    try:
        account = await resolve_agent_account(session, agent_key)
    except AgentAccountNotDesignatedError:
        return 0
    return int(
        await session.scalar(
            select(func.count())
            .select_from(PaperTradeOrder)
            .where(
                PaperTradeOrder.paper_trade_account_id == account.id,
                PaperTradeOrder.created_at >= day_start_cn,
            )
        )
    )


async def _memory_counts(session: AsyncSession, agent_key: str) -> AgentMemoryCounts:
    """活跃记忆按类型计数（status='active'）。"""
    counts = AgentMemoryCounts()
    rows = (
        await session.execute(
            select(AgentMemory.mem_type, func.count())
            .where(AgentMemory.agent_key == agent_key, AgentMemory.status == "active")
            .group_by(AgentMemory.mem_type)
        )
    ).all()
    for mem_type, cnt in rows:
        counts.active_total += int(cnt)
        if mem_type == "discipline":
            counts.discipline = int(cnt)
        elif mem_type == "method":
            counts.method = int(cnt)
        elif mem_type == "lesson":
            counts.lesson = int(cnt)
    return counts
