"""全球指标最新快照读取服务。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quote_global_index import GlobalIndexDaily
from app.models.tracked_index import TrackedIndexConfig
from app.schemas.market import GlobalIndexQuoteResponse


async def get_global_index_quotes(session: AsyncSession) -> list[GlobalIndexQuoteResponse]:
    """启用中的全球指标最新收盘快照（按 sort_order 排序，无数据的代码字段留空）。"""
    cfg_stmt = (
        select(TrackedIndexConfig)
        .where(
            TrackedIndexConfig.market_category == "全球",
            TrackedIndexConfig.is_enabled.is_(True),
        )
        .order_by(TrackedIndexConfig.sort_order, TrackedIndexConfig.id)
    )
    configs = list((await session.execute(cfg_stmt)).scalars().all())
    if not configs:
        return []

    codes = [cfg.index_code for cfg in configs]
    bar_stmt = (
        select(
            GlobalIndexDaily.index_code,
            GlobalIndexDaily.close,
            GlobalIndexDaily.change_pct,
            GlobalIndexDaily.trade_date,
        )
        .where(GlobalIndexDaily.index_code.in_(codes))
        .distinct(GlobalIndexDaily.index_code)
        .order_by(GlobalIndexDaily.index_code, GlobalIndexDaily.trade_date.desc())
    )
    latest = {
        row[0]: (row[1], row[2], row[3])
        for row in (await session.execute(bar_stmt)).all()
    }

    results: list[GlobalIndexQuoteResponse] = []
    for cfg in configs:
        close, change_pct, trade_date = latest.get(cfg.index_code, (None, None, None))
        results.append(
            GlobalIndexQuoteResponse(
                index_code=cfg.index_code,
                index_name=cfg.index_name,
                close=float(close) if close is not None else None,
                change_pct=float(change_pct) if change_pct is not None else None,
                trade_date=trade_date,
            )
        )
    return results
