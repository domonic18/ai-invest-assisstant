"""Industry chain analysis API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills.industry_chain_analysis import run_skill
from app.dependencies import get_db
from app.schemas.chain import ChainAnalysisRequest, ChainAnalysisResult

router = APIRouter()


@router.post("/analyze", response_model=ChainAnalysisResult)
async def analyze_chain(
    request: ChainAnalysisRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChainAnalysisResult:
    """产业链分析：调用 AI Agent 生成产业链图谱与报告。"""
    try:
        result = await run_skill(
            session,
            {"industry": request.industry, "focus": request.focus},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI analysis failed: {exc}",
        ) from exc
    return result
