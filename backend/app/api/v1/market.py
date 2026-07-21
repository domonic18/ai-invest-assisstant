"""Market overview (每日复盘) API endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.market import (
    CollectTaskResult,
    IndexIntradayResponse,
    IndexKlineResponse,
    IndexQuoteResponse,
    LimitUpIntradayResponse,
    LimitUpResponse,
    MarketCollectRequest,
    MarketReviewGenerateRequest,
    MarketReviewResponse,
    MarketReviewUpdateRequest,
    MarketStatsResponse,
    SectorOverviewResponse,
)
from app.services import limit_up_ai_service, market_review_service, market_service
from app.services.llm_config_service import LLMConfigNotConfiguredError
from app.services.market_review_service import NonTradingDayError, ReviewNotFoundError

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
    session: Annotated[AsyncSession, Depends(get_db)],
    code: str = "sh000001",
    trade_date: date | None = None,
) -> IndexIntradayResponse:
    """指数分时图数据（指定交易日的分钟级价格与量能，读本地 kline_minute）。"""
    try:
        return await market_service.get_index_intraday(session, code, trade_date)
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


@router.get("/limit-up/intraday", response_model=LimitUpIntradayResponse)
async def get_limit_up_intraday(
    session: Annotated[AsyncSession, Depends(get_db)],
    trade_date: date | None = None,
) -> LimitUpIntradayResponse:
    """涨停个股全天分时缩略图（每股 ≤60 个收盘价采样点）。"""
    return await market_service.get_limit_up_intraday(session, trade_date)


@router.post("/limit-up/ai-review", response_model=LimitUpResponse)
async def generate_limit_up_ai_review(
    data: MarketReviewGenerateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LimitUpResponse:
    """触发 LLM 生成 AI 涨停归因（regenerate=true 强制重新生成）。

    生成成功后返回带题材分组与原因的完整涨停数据；无缓存时 GET /limit-up
    回退为行业分组。
    """
    try:
        await limit_up_ai_service.generate_attribution(
            session, data.trade_date, data.regenerate
        )
        return await market_service.get_limit_up(session, data.trade_date)
    except NonTradingDayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LLMConfigNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Limit-up AI review generation failed: {exc}",
        ) from exc


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
) -> MarketReviewResponse:
    """读取已生成的 AI 大盘综述（只读，不存在时 404，绝不触发生成）。"""
    try:
        review = await market_review_service.get_cached_review(session, trade_date)
    except NonTradingDayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该交易日尚未生成 AI 复盘",
        )
    return review


@router.post("/ai-review", response_model=MarketReviewResponse)
async def generate_ai_review(
    data: MarketReviewGenerateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MarketReviewResponse:
    """触发 LLM 生成 AI 大盘综述（regenerate=true 强制重新生成）。"""
    try:
        return await market_review_service.generate_market_review(
            session, data.trade_date, data.regenerate
        )
    except NonTradingDayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
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


@router.put("/ai-review", response_model=MarketReviewResponse)
async def update_ai_review(
    data: MarketReviewUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MarketReviewResponse:
    """保存人工编辑后的复盘内容。"""
    try:
        return await market_review_service.update_market_review(
            session,
            data.trade_date,
            market_review_service.MarketReviewContent(
                overview=data.overview,
                emotion_analysis=data.emotion_analysis,
                capital_analysis=data.capital_analysis,
                risk_advice=data.risk_advice,
            ),
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NonTradingDayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


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
    try:
        return await market_service.backfill_trade_date(session, data.trade_date)
    except market_service.NonTradingDayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Market data collection failed: {exc}",
        ) from exc
