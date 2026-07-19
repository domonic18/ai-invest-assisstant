"""Market overview (每日复盘) API endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.market import (
    IndexIntradayResponse,
    IndexKlineResponse,
    IndexQuoteResponse,
    LimitUpResponse,
    MarketReviewResponse,
    MarketStatsResponse,
    SectorOverviewResponse,
)
from app.services import market_review_service, market_service
from app.services.llm_config_service import LLMConfigNotConfiguredError

router = APIRouter()


@router.get("/indices", response_model=list[IndexQuoteResponse])
async def get_indices(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> list[IndexQuoteResponse]:
    """四大指数行情（上证/深成/创业板/科创50，含近 30 日趋势）。

    默认取实时快照；指定历史交易日时返回当日收盘行情（非交易日返回空）。
    """
    try:
        return await market_service.get_index_quotes(session, trade_date)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch index quotes: {exc}",
        ) from exc


@router.get("/indices/kline", response_model=IndexKlineResponse)
async def get_index_kline(
    session: Annotated[AsyncSession, Depends(get_db)],
    code: str = "sh000001",
    period: str = "daily",
    limit: Annotated[int, Query(ge=1, le=2000)] = 250,
) -> IndexKlineResponse:
    """指数多周期 K 线（daily/weekly/monthly/quarterly/yearly，由本地 kline_daily 聚合）。"""
    try:
        return await market_service.get_index_kline(session, code, period, limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/indices/intraday", response_model=IndexIntradayResponse)
async def get_index_intraday(
    code: str = "sh000001", trade_date: date | None = None
) -> IndexIntradayResponse:
    """指数分时图数据（指定交易日的分钟级价格与量能，仅覆盖最近约 8 个交易日）。"""
    try:
        return await market_service.get_index_intraday(code, trade_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch index intraday: {exc}",
        ) from exc


@router.get("/stats", response_model=MarketStatsResponse)
async def get_stats(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> MarketStatsResponse:
    """涨跌家数、成交额与情绪温度；指定历史交易日时涨跌停取历史池。"""
    try:
        return await market_service.get_market_stats(session, trade_date)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch market stats: {exc}",
        ) from exc


@router.get("/limit-up", response_model=LimitUpResponse)
async def get_limit_up(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> LimitUpResponse:
    """涨停板与连板天梯，默认取最近有数据的交易日。"""
    return await market_service.get_limit_up(session, trade_date)


@router.get("/sectors", response_model=SectorOverviewResponse)
async def get_sector_overview(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
    sector_type: str = "industry",
) -> SectorOverviewResponse:
    """板块热力图、资金净流入/流出 TOP5 与领涨板块。"""
    return await market_service.get_sector_overview(session, trade_date, sector_type)


@router.get("/ai-review", response_model=MarketReviewResponse)
async def get_ai_review(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
    regenerate: bool = False,
) -> MarketReviewResponse:
    """AI 大盘综述（LLM 生成，按交易日缓存）。"""
    try:
        return await market_review_service.generate_market_review(
            session, trade_date, regenerate
        )
    except LLMConfigNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI review generation failed: {exc}",
        ) from exc
