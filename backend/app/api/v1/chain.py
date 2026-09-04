"""产业链分析 API 路由。

业务异常（ChainAnalysisFailedError / LLMConfigNotConfiguredError）由全局
AppError handler 统一转换为 JSONResponse ``{detail: message}``。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.chain import (
    ChainAlertResponse,
    ChainAnalysisRequest,
    ChainAnalyzeResponse,
    ChainCompareResult,
    ChainVersionDetail,
    ChainVersionSummary,
)
from app.services.chain import chain_service

router = APIRouter()


@router.get("/industries", response_model=list[str])
async def list_industries(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[str]:
    """列出当前用户已有成功分析版本的所有行业名称（最近更新在前）。"""
    return await chain_service.list_industries(session, user.id)


@router.get("/alerts", response_model=list[ChainAlertResponse])
async def list_alerts(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    industry: Annotated[str, Query(min_length=1, max_length=50)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[ChainAlertResponse]:
    """查询指定行业近 N 天的 AI 提醒（severity 降序）。"""
    return await chain_service.list_alerts(session, industry, days=days)


@router.post("/analyze", response_model=ChainAnalyzeResponse)
async def analyze_chain(
    request: ChainAnalysisRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ChainAnalyzeResponse:
    """产业链分析：调用 AI Agent 生成图谱并持久化为新版本。"""
    return await chain_service.analyze_and_persist(
        session, request.industry, request.focus, user_id=user.id
    )


@router.get("/versions/compare", response_model=ChainCompareResult)
async def compare_versions(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    base_id: Annotated[int, Query(gt=0)],
    target_id: Annotated[int, Query(gt=0)],
) -> ChainCompareResult:
    """对比两个分析版本的差异。"""
    result = await chain_service.compare_versions(
        session, base_id, target_id, user_id=user.id
    )
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
    user: Annotated[User, Depends(get_current_user)],
) -> ChainVersionDetail:
    """查询指定版本详情（含完整快照）。"""
    detail = await chain_service.get_version_detail(
        session, version_id, user_id=user.id
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在",
        )
    return detail


@router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_version(
    version_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """删除指定分析版本（节点/边/映射级联清理，AI 结果保留）。"""
    deleted = await chain_service.delete_version(session, version_id, user_id=user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在",
        )


@router.get("/{industry}/latest", response_model=ChainVersionDetail)
async def get_latest(
    industry: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ChainVersionDetail:
    """查询指定行业最新成功版本。"""
    detail = await chain_service.get_latest_detail(
        session, industry, user_id=user.id
    )
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
    user: Annotated[User, Depends(get_current_user)],
) -> list[ChainVersionSummary]:
    """列出指定行业的全部版本（版本号降序）。"""
    return await chain_service.list_versions(
        session, industry, user_id=user.id
    )
