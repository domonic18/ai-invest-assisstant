"""日 K 采集宇宙：用户自选 ∪ 交易 Agent 生效标的。

交易 Agent 选出的标的落在 ``agent_stock_selection`` / ``agent_trade_plan``，
不进用户自选表（Agent 的「自选」是逻辑视图，成员由选股表派生）。这些标的
的日 K 过去只剩计划生成时锚点兜底落库的末几根，日常采集与新鲜度自愈都
覆盖不到——个股页历史 K 线近乎空白。宇宙在此统一并集，日 K 采集器缺省
符号集与新鲜度自愈巡检集共用同一真相源。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.agent_trading import AgentStockSelection, AgentTradePlan
from app.models.watchlist import UserWatchlist
from collector.core.base import get_engine

#: 计划状态纳入采集宇宙的取值：生效中 / 已触发 / 已成交（持仓与在途计划）。
#: expired（当日未触发）/ cancelled（人工取消）/ failed（委托未成交）/
#: invalid（死单体检失效）不再需要日 K。
_PLAN_UNIVERSE_STATUSES = ("active", "triggered", "executed")


async def fetch_kline_universe_codes() -> list[str]:
    """日 K 采集宇宙代码（去重升序）。

    三来源并集：用户自选股 ∪ Agent 生效选股（status='active'）∪ Agent
    生效/已成交计划标的。
    """
    session_maker = async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        watchlist = await session.execute(
            select(UserWatchlist.stock_code).distinct()
        )
        selections = await session.execute(
            select(AgentStockSelection.stock_code)
            .where(AgentStockSelection.status == "active")
            .distinct()
        )
        plans = await session.execute(
            select(AgentTradePlan.stock_code)
            .where(AgentTradePlan.status.in_(_PLAN_UNIVERSE_STATUSES))
            .distinct()
        )

    codes = {row[0] for row in watchlist.all()}
    codes.update(row[0] for row in selections.all())
    codes.update(row[0] for row in plans.all())
    return sorted(codes)
