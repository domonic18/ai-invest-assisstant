"""管理后台知识库用量端点（批次 G1，arch/09 §10.2）。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.kb import KbUsageResponse
from app.services.kb import usage_service

router = APIRouter(prefix="/kb", dependencies=[Depends(get_current_admin_user)])


@router.get("/usage", response_model=KbUsageResponse)
async def get_usage(
    session: Annotated[AsyncSession, Depends(get_db)],
    source_id: int | None = Query(
        default=None, description="按知识库过滤（台账按 detail.sourceId 归集）"
    ),
    date_from: date | None = Query(default=None, description="起始日（北京日历日，含）"),
    date_to: date | None = Query(default=None, description="截止日（北京日历日，含）"),
) -> KbUsageResponse:
    """建库用量聚合：kb_* token 分项 + ASR 时长 × 单价（预估 vs 实际对照）。"""
    return await usage_service.get_usage(
        session, source_id=source_id, date_from=date_from, date_to=date_to
    )
