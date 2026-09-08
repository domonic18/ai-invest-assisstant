"""全球指标最新快照与历史走势读取服务。"""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.constants import GLOBAL_INDEX_CODES
from app.core.exceptions import BadRequestError
from app.repositories.market import global_index_repository
from app.schemas.market import GlobalIndexHistoryPoint, GlobalIndexQuoteResponse

# 2s10s 利差为衍生指标：US10Y − US2Y 按 trade_date 对齐求差
_SPREAD_CODE = "US2Y10S"
_SPREAD_LEG_CODES = ("US2Y", "US10Y")


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


async def get_index_history(
    session: AsyncSession, index_code: str, months: int = 12
) -> list[GlobalIndexHistoryPoint]:
    """全球指标近 N 月收盘走势（升序）。

    ``US2Y10S`` 特例：美债 10Y − 2Y 利差，两腿按 trade_date 对齐求差。
    """
    if index_code == _SPREAD_CODE:
        return await _get_spread_history(session, months)
    if index_code not in GLOBAL_INDEX_CODES:
        raise BadRequestError(f"未知全球指标代码: {index_code}")
    since = today_cn() - timedelta(days=months * 31)
    rows = await global_index_repository.list_closes(session, index_code, since)
    return [
        GlobalIndexHistoryPoint(trade_date=d, close=float(c)) for d, c in rows
    ]


async def _get_spread_history(
    session: AsyncSession, months: int
) -> list[GlobalIndexHistoryPoint]:
    since = today_cn() - timedelta(days=months * 31)
    closes = {
        code: dict(await global_index_repository.list_closes(session, code, since))
        for code in _SPREAD_LEG_CODES
    }
    two_year, ten_year = closes[_SPREAD_LEG_CODES[0]], closes[_SPREAD_LEG_CODES[1]]
    return [
        GlobalIndexHistoryPoint(trade_date=d, close=float(ten_year[d] - two_year[d]))
        for d in sorted(set(two_year) & set(ten_year))
    ]
