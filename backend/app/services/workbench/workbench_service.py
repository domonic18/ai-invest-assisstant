"""工作台聚合服务：一次请求拼装多模块数据，单模块降级不拖垮整体。"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.calendar import CalendarEventResponse
from app.schemas.telegraph import TelegraphResponse
from app.schemas.workbench import WorkbenchResponse
from app.services.market import (
    calendar_service,
    global_index_service,
    index_quotation_service,
    market_stats_service,
    sector_fund_flow_service,
    telegraph_service,
)
from app.services.review import market_review_service
from app.services.user import watchlist_quote_service
from app.services.workbench import collector_status_service, review_status_service

logger = structlog.get_logger(__name__)

_CALENDAR_LIMIT = 8
_TELEGRAPH_PAGE_SIZE = 12


async def get_workbench(session: AsyncSession, user_id: int) -> WorkbenchResponse:
    """并发友好地顺序聚合日历/复盘/要闻/自选/市场快览（均为快读，无跨模块依赖）。

    单模块异常记录 warning 后返回空态，保证聚合端点整体恒 200。
    """
    data = WorkbenchResponse()

    try:
        events = await calendar_service.list_upcoming(session, _CALENDAR_LIMIT)
        data.calendar = [CalendarEventResponse.model_validate(e) for e in events]
    except Exception:
        logger.warning("workbench_calendar_degraded", exc_info=True)

    try:
        data.review = await market_review_service.get_market_review(
            session, user_id, None
        )
    except Exception:
        logger.warning("workbench_review_degraded", exc_info=True)

    try:
        items, _total = await telegraph_service.list_telegraph(
            session, page=1, page_size=_TELEGRAPH_PAGE_SIZE
        )
        data.telegraph = [TelegraphResponse.model_validate(t) for t in items]
    except Exception:
        logger.warning("workbench_telegraph_degraded", exc_info=True)

    try:
        data.watchlist_groups = await watchlist_quote_service.get_watchlist_groups(
            session, user_id
        )
    except Exception:
        logger.warning("workbench_watchlist_degraded", exc_info=True)

    try:
        data.indices = await index_quotation_service.get_index_quotes(session, None)
    except Exception:
        logger.warning("workbench_indices_degraded", exc_info=True)

    try:
        data.stats = await market_stats_service.get_market_stats(session, None)
    except Exception:
        logger.warning("workbench_stats_degraded", exc_info=True)

    try:
        data.global_indices = await global_index_service.get_global_index_quotes(session)
    except Exception:
        logger.warning("workbench_global_indices_degraded", exc_info=True)

    try:
        data.sector_flow = await sector_fund_flow_service.get_latest_sector_flow(session)
    except Exception:
        logger.warning("workbench_sector_flow_degraded", exc_info=True)

    try:
        data.review_status = await review_status_service.get_review_status(session)
    except Exception:
        logger.warning("workbench_review_status_degraded", exc_info=True)

    try:
        data.collector_status = await collector_status_service.get_collector_status(session)
    except Exception:
        logger.warning("workbench_collector_status_degraded", exc_info=True)

    return data
