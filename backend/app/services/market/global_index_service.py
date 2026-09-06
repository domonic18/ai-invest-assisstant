"""全球指标最新快照读取服务。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market import global_index_repository
from app.schemas.market import GlobalIndexQuoteResponse


async def get_global_index_quotes(session: AsyncSession) -> list[GlobalIndexQuoteResponse]:
    """启用中的全球指标最新收盘快照（按 sort_order 排序，无数据的代码字段留空）。"""
    configs = await global_index_repository.list_enabled_global_configs(session)
    if not configs:
        return []

    codes = [cfg.index_code for cfg in configs]
    latest = await global_index_repository.map_latest_closes(session, codes)

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
