"""个股基础信息 API 路由。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.stock import (
    StockAiAnalysisResponse,
    StockBasicResponse,
    StockIntradayResponse,
    StockKlineResponse,
    StockQuoteResponse,
    StockSearchRequest,
    StockSectorsResponse,
)
from app.services import market as stock_service
from app.services.market import trade_calendar_service
from app.services.review import stock_daily_analysis_service

router = APIRouter()


@router.get("/search", response_model=list[StockBasicResponse])
async def search_stocks(
    q: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
) -> list[StockBasicResponse]:
    """根据股票代码或名称搜索。"""
    request = StockSearchRequest(q=q, limit=limit)
    items = await stock_service.search_stocks(session, request.q, request.limit)
    return [StockBasicResponse.model_validate(item) for item in items]


@router.get("/{code}", response_model=StockBasicResponse)
async def get_stock(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    market: str | None = None,
) -> StockBasicResponse:
    """获取股票基础信息。"""
    item = await stock_service.get_stock_by_code(session, code, market)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock not found",
        )
    return StockBasicResponse.model_validate(item)


@router.get("/{code}/quote", response_model=StockQuoteResponse)
async def get_stock_quote(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StockQuoteResponse:
    """获取个股实时行情快照（Redis 优先，缺失时回退日 K）。"""
    data = await stock_service.get_stock_quote(session, code)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock quote not found",
        )
    return StockQuoteResponse.model_validate(data)


@router.get("/{code}/kline", response_model=StockKlineResponse)
async def get_stock_kline(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    limit: int = Query(default=250, ge=1, le=500),
) -> StockKlineResponse:
    """获取个股日/周/月 K 线。"""
    try:
        data = await stock_service.get_stock_kline(session, code, period, limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return StockKlineResponse.model_validate(data)


@router.get("/{code}/intraday", response_model=StockIntradayResponse)
async def get_stock_intraday(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> StockIntradayResponse:
    """获取个股分时数据。"""
    try:
        data = await stock_service.get_stock_intraday(session, code, trade_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return StockIntradayResponse.model_validate(data)


@router.get("/{code}/sectors", response_model=StockSectorsResponse)
async def get_stock_sectors(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StockSectorsResponse:
    """获取个股所属行业与概念。"""
    data = await stock_service.get_stock_sectors(session, code)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock not found",
        )
    return StockSectorsResponse.model_validate(data)


@router.get(
    "/{code}/ai-analysis",
    response_model=StockAiAnalysisResponse,
    responses={204: {"description": "该交易日尚未生成个股 AI 分析"}},
)
async def get_stock_ai_analysis(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    trade_date: date | None = None,
) -> StockAiAnalysisResponse | Response:
    """读取个股指定交易日的 AI 分析（trade_date 缺省取最近交易日）。"""
    resolved_date = trade_date or await trade_calendar_service.resolve_latest_trade_date(
        session
    )
    analysis = await stock_daily_analysis_service.get_stock_analysis(
        session, code, trade_date=resolved_date
    )
    if analysis is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return analysis
