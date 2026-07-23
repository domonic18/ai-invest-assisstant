"""Industry chain analysis API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.chain import (
    ChainAnalysisRequest,
    ChainAnalyzeResponse,
    ChainCompareResult,
    ChainVersionDetail,
    ChainVersionSummary,
)
from app.services import chain_service
from app.services.chain_service import ChainAnalysisFailedError
from app.services.llm_config_service import LLMConfigNotConfiguredError

router = APIRouter()


@router.post("/analyze", response_model=ChainAnalyzeResponse)
async def analyze_chain(
    request: ChainAnalysisRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChainAnalyzeResponse:
    """产业链分析：调用 AI Agent 生成图谱并持久化为新版本。"""
    try:
        return await chain_service.analyze_and_persist(
            session, request.industry, request.focus
        )
    except LLMConfigNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ChainAnalysisFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI analysis failed: {exc}",
        ) from exc


@router.get("/versions/compare", response_model=ChainCompareResult)
async def compare_versions(
    session: Annotated[AsyncSession, Depends(get_db)],
    base_id: Annotated[int, Query(gt=0)],
    target_id: Annotated[int, Query(gt=0)],
) -> ChainCompareResult:
    """对比两个分析版本的差异。"""
    result = await chain_service.compare_versions(session, base_id, target_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在或不是成功版本",
        )
    return result


@router.get("/versions/{version_id}", response_model=ChainVersionDetail)
async def get_version(
    version_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChainVersionDetail:
    """查询指定版本详情（含完整快照）。"""
    detail = await chain_service.get_version_detail(session, version_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在",
        )
    return detail


@router.get("/{industry}/latest", response_model=ChainVersionDetail)
async def get_latest(
    industry: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChainVersionDetail:
    """查询指定行业最新成功版本。"""
    detail = await chain_service.get_latest_detail(session, industry)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该行业暂无分析版本",
        )
    return detail


@router.get("/{industry}/versions", response_model=list[ChainVersionSummary])
async def list_versions(
    industry: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChainVersionSummary]:
    """列出指定行业的全部版本（版本号降序）。"""
    return await chain_service.list_versions(session, industry)
