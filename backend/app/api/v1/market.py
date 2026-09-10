"""市场总览（每日复盘）API 路由。

业务异常（NonTradingDayError/ReviewNotFoundError/LLMConfigNotConfiguredError 等）
均由 ``app.main.app_error_handler`` 统一转换为 JSONResponse ``{detail: message}``，
路由层不再做 try/except 转换。
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import KLINE_PERIODS
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.market import (
    CollectTaskResult,
    FedWatchResponse,
    GlobalIndexHistoryPoint,
    GlobalIndexQuoteResponse,
    IndexIntradayResponse,
    IndexKlineResponse,
    IndexQuoteResponse,
    LimitUpIntradayResponse,
    LimitUpResponse,
    MarketCollectRequest,
    MarketReviewResponse,
    MarketReviewUpdateRequest,
    MarketStatsResponse,
    SectorOverviewResponse,
    SectorQuoteResponse,
)
from app.schemas.tracked_index import TrackedIndexOption
from app.services import review as market_review_service
from app.services.market import (
    fed_watch_service,
    global_index_service,
    market_service,
    sector_quote_service,
)
from app.services.user import UserService

router = APIRouter()

_KLINE_PERIOD_PATTERN = "^(" + "|".join(KLINE_PERIODS) + ")$"


@router.get("/indices", response_model=list[IndexQuoteResponse])
async def get_indices(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> list[IndexQuoteResponse]:
    """四大指数行情（上证/深成/创业板/科创50，含近 30 日趋势）。

    默认取实时快照；指定历史交易日时返回当日收盘行情（非交易日返回空）。
    """
    return await market_service.get_index_quotes(session, trade_date)


@router.get("/global-indices", response_model=list[GlobalIndexQuoteResponse])
async def get_global_indices(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[GlobalIndexQuoteResponse]:
    """启用中的全球指标最新快照（黄金/美元指数/美债收益率等），按用户个人配置过滤。"""
    settings = await UserService(session).get_settings(current_user)
    return await global_index_service.get_global_index_quotes(
        session, settings.tracked_index_codes
    )


@router.get("/tracked-indexes", response_model=list[TrackedIndexOption])
async def list_tracked_index_options(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[TrackedIndexOption]:
    """个人设置可勾选的跟踪指数清单（启用中的全球指标）。"""
    return await global_index_service.list_tracked_index_options(session)


@router.get("/global-index-history", response_model=list[GlobalIndexHistoryPoint])
async def get_global_index_history(
    session: Annotated[AsyncSession, Depends(get_db)],
    index_code: str = Query(..., description="全球指标代码，US2Y10S 为 10Y-2Y 利差"),
    months: Annotated[int, Query(ge=1, le=24)] = 12,
) -> list[GlobalIndexHistoryPoint]:
    """全球指标近 N 月收盘走势（trade_date 升序）。"""
    return await global_index_service.get_index_history(session, index_code, months)


@router.get("/global-indices/kline", response_model=IndexKlineResponse)
async def get_global_index_kline(
    session: Annotated[AsyncSession, Depends(get_db)],
    index_code: str = Query(..., description="全球指标代码，US2Y10S 为 10Y-2Y 利差"),
    period: str = Query("daily", pattern=_KLINE_PERIOD_PATTERN),
    limit: Annotated[int, Query(ge=1, le=1000)] = 250,
) -> IndexKlineResponse:
    """全球指标多周期 K 线（股指/商品/汇率含 OHLC；债券收益率与利差为收盘线）。"""
    return await global_index_service.get_global_index_kline(
        session, index_code, period, limit
    )


@router.get("/fed-watch", response_model=FedWatchResponse | None)
async def get_fed_watch(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FedWatchResponse | None:
    """CME FedWatch 官方加息概率快照（未采集时返回 null）。"""
    return await fed_watch_service.get_fed_watch(session)


@router.get("/sector-quotes", response_model=SectorQuoteResponse | None)
async def get_sector_quotes(
    session: Annotated[AsyncSession, Depends(get_db)],
    sector_type: Annotated[str, Query(pattern="^(industry|concept)$")] = "industry",
    trade_date: date | None = None,
) -> SectorQuoteResponse | None:
    """单日板块行情快照（涨跌幅降序）；未指定日期取最新快照日。"""
    return await sector_quote_service.get_sector_quotes(
        session, sector_type, trade_date
    )


@router.get("/indices/kline", response_model=IndexKlineResponse)
async def get_index_kline(
    session: Annotated[AsyncSession, Depends(get_db)],
    code: str = "sh000001",
    period: str = "daily",
    limit: Annotated[int, Query(ge=1, le=2000)] = 250,
) -> IndexKlineResponse:
    """指数多周期 K 线（daily/weekly/monthly/quarterly/yearly，由本地 quote_kline_stock_daily 聚合）。"""
    return await market_service.get_index_kline(session, code, period, limit)


@router.get("/indices/intraday", response_model=IndexIntradayResponse)
async def get_index_intraday(
    session: Annotated[AsyncSession, Depends(get_db)],
    code: str = "sh000001",
    trade_date: date | None = None,
) -> IndexIntradayResponse:
    """指数分时图数据（指定交易日的分钟级价格与量能，读本地 quote_kline_stock_minute）。"""
    return await market_service.get_index_intraday(session, code, trade_date)


@router.get("/stats", response_model=MarketStatsResponse)
async def get_stats(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> MarketStatsResponse:
    """涨跌家数、成交额与情绪温度；指定历史交易日时涨跌停取历史池。"""
    return await market_service.get_market_stats(session, trade_date)


@router.get("/limit-up", response_model=LimitUpResponse)
async def get_limit_up(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> LimitUpResponse:
    """涨停板与连板天梯，默认取最近有数据的交易日。"""
    return await market_service.get_limit_up(session, trade_date)


@router.get("/limit-up/intraday", response_model=LimitUpIntradayResponse)
async def get_limit_up_intraday(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> LimitUpIntradayResponse:
    """涨停个股全天分时缩略图（每股 ≤60 个收盘价采样点）。"""
    return await market_service.get_limit_up_intraday(session, trade_date)


@router.get("/sectors", response_model=SectorOverviewResponse)
async def get_sector_overview(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
    sector_type: str = "industry",
) -> SectorOverviewResponse:
    """板块热力图、资金净流入/流出 TOP5 与领涨板块。"""
    return await market_service.get_sector_overview(session, trade_date, sector_type)


@router.get(
    "/ai-review",
    response_model=MarketReviewResponse,
    responses={204: {"description": "该交易日尚未生成 AI 复盘"}},
)
async def get_ai_review(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    trade_date: date | None = None,
) -> MarketReviewResponse | Response:
    """读取当前用户的 AI 大盘综述（优先用户编辑版，否则回退共享 base）。"""
    review = await market_review_service.get_market_review(
        session, current_user.id, trade_date
    )
    if review is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return review


@router.put("/ai-review", response_model=MarketReviewResponse)
async def update_ai_review(
    data: MarketReviewUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MarketReviewResponse:
    """按分区保存当前用户编辑后的复盘内容（不影响其他用户/共享 base）。"""
    return await market_review_service.update_market_review(
        session,
        current_user.id,
        data.trade_date,
        data.section_key,
        data.content,
    )


@router.post("/collect", response_model=list[CollectTaskResult])
async def collect_trade_date(
    data: MarketCollectRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CollectTaskResult]:
    """补采指定交易日的行情数据（涨停池/炸板池/跌停池/成交额/板块资金流）。

    任务经采集队列异步执行：涨停/成交额约 1 分钟入库，板块资金流
    受数据源限流约束约需 10 分钟。涨跌家数为盘中快照，无法补采。
    """
    return await market_service.backfill_trade_date(session, data.trade_date)
