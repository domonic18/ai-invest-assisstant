"""每日计划 LLM 输入组装（批次 7 §10.2 输入清单的唯一组装点）。

输入 = 当日复盘解读（18:35 后就绪——缺失即 ``ReviewInputDataNotReadyError``
退避重试）+ 涨停归因 + 异动归因 + agent 账户本地持仓 + 人工移出清单 +
方法论基座（温程《趋势理论》KB 直读双层注入，见 ``agent_methodology``）+
agent 经验记忆（``agent_memory`` active 条目）。仅取数，不做 LLM 调用与落库；
各采集函数可独立 mock 测试。
"""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trading import AgentStockSelection
from app.models.market_anomaly import StockAnomaly
from app.models.paper_trade import PaperTradeExecution
from app.repositories.review import ai_analysis_repository
from app.services.review.market_review_generator import (
    SKILL_ID as MARKET_REVIEW_SKILL_ID,
)
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_methodology

#: 异动归因注入 prompt 的条数上限（按 strength 降序）
_ANOMALY_TOP_N = 10
#: 人工移出清单回看窗口（天）——超过后允许重新候选
_MANUAL_REMOVED_WINDOW_DAYS = 14
#: agent 经验记忆注入条数上限
_MEMORY_TOP_N = 20


async def _market_review_sections(
    session: AsyncSession, trade_date: date
) -> dict[str, Any]:
    """当日复盘解读全文（就绪预检：缺失即输入未就绪，18:35 任务生成）。"""
    row = await ai_analysis_repository.load_latest_success(
        session, skill_id=MARKET_REVIEW_SKILL_ID, trade_date=trade_date
    )
    if row is None or not row.structured_output:
        raise ReviewInputDataNotReadyError(
            f"{trade_date.isoformat()} 当日复盘解读尚未生成，每日计划输入未就绪"
        )
    return row.structured_output


async def _limit_up_attribution(
    session: AsyncSession, trade_date: date
) -> dict[str, Any] | None:
    from app.services.review import limit_up_ai_service

    content = await limit_up_ai_service.get_cached_attribution(session, trade_date)
    return None if content is None else content.model_dump()


async def _stock_anomalies(
    session: AsyncSession, trade_date: date
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(StockAnomaly)
                .where(StockAnomaly.trade_date == trade_date)
                .order_by(StockAnomaly.strength.desc())
                .limit(_ANOMALY_TOP_N)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "stock_code": r.stock_code,
            "stock_name": r.stock_name,
            "change_pct": float(r.change_pct) if r.change_pct is not None else None,
            "anomaly_types": r.anomaly_types,
            "attribution_category": r.attribution_category,
            "attribution_summary": r.attribution_summary,
        }
        for r in rows
    ]


async def _manual_removed_codes(session: AsyncSession, trade_date: date) -> list[str]:
    """近期人工移出清单（全局生效：prompt 声明禁止选入 + 服务层兜底过滤）。"""
    since = trade_date.toordinal() - _MANUAL_REMOVED_WINDOW_DAYS
    rows = await session.execute(
        select(AgentStockSelection.stock_code)
        .where(
            AgentStockSelection.removed_reason == "manual",
            AgentStockSelection.trade_date >= date.fromordinal(since),
        )
        .distinct()
    )
    return [code for code in rows.scalars().all()]


async def _local_positions(session: AsyncSession, account_id: int) -> list[dict[str, Any]]:
    """agent 账户当前持仓（本地成交聚合，不依赖柜台）：净持有 > 0 的标的。"""
    rows = (
        (
            await session.execute(
                select(PaperTradeExecution)
                .where(PaperTradeExecution.paper_trade_account_id == account_id)
                .order_by(PaperTradeExecution.trade_date.asc())
            )
        )
        .scalars()
        .all()
    )
    agg: dict[str, dict[str, float]] = {}
    for row in rows:
        code = row.symbol.split(".")[-1]
        volume = float(row.volume or 0)
        price = float(row.price or 0)
        entry = agg.setdefault(code, {"volume": 0.0, "cost": 0.0})
        if row.side == 1:
            entry["volume"] += volume
            entry["cost"] += volume * price
        elif row.side == 2:
            entry["volume"] -= volume
    return [
        {
            "stock_code": code,
            "volume": int(item["volume"]),
            "avg_cost": round(item["cost"] / item["volume"], 4)
            if item["volume"] > 0
            else None,
        }
        for code, item in sorted(agg.items())
        if item["volume"] > 0
    ]


async def _active_memories(session: AsyncSession) -> list[dict[str, Any]]:
    """agent 经验记忆 active 条目（复盘沉淀 + 手动沉淀，停用条目不注入）。"""
    from sqlalchemy import text

    # SAVEPOINT 隔离：表缺失等失败只回滚到保存点，避免外层事务进入 aborted 态
    try:
        async with session.begin_nested():
            rows = await session.execute(
                text(
                    "SELECT title, body, mem_type FROM agent_memory "
                    "WHERE status = 'active' ORDER BY updated_at DESC LIMIT :n"
                ),
                {"n": _MEMORY_TOP_N},
            )
            items = [
                {"title": r.title, "body": r.body, "mem_type": r.mem_type}
                for r in rows.mappings().all()
            ]
    except (OperationalError, ProgrammingError):
        # 批次 9 建 agent_memory 前表不存在（asyncpg UndefinedTable → ProgrammingError）；
        # 记忆注入是可选增强，任何取数失败都降级为空集，不阻塞每日计划。
        return []
    return items


async def collect_plan_input(
    session: AsyncSession, account_id: int, trade_date: date
) -> tuple[dict[str, Any], list[str]]:
    """组装 LLM 输入，返回 (输入 dict, 人工移出代码清单)。"""
    review = await _market_review_sections(session, trade_date)
    attribution = await _limit_up_attribution(session, trade_date)
    anomalies = await _stock_anomalies(session, trade_date)
    manual_removed = await _manual_removed_codes(session, trade_date)
    methodology = await agent_methodology.build_methodology_input(
        session,
        query_text=agent_methodology.build_retrieval_query(
            review.get("sections") or review, attribution, anomalies
        ),
    )
    return (
        {
            "trade_date": trade_date.isoformat(),
            "market_review": review.get("sections") or review,
            "limit_up_attribution": attribution,
            "stock_anomalies": anomalies,
            "positions": await _local_positions(session, account_id),
            "manual_removed_codes": manual_removed,
            "methodology": methodology,
            "memories": await _active_memories(session),
        },
        manual_removed,
    )
