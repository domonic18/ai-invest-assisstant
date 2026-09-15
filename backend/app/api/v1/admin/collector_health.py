"""管理后台采集健康监测 API（只读快照 + 手动检测/清空）。"""

from datetime import date as date_type
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.core.exceptions import UnprocessableEntityError
from app.dependencies import get_current_admin_user, get_db
from app.schemas.collector_health import (
    ChannelHealthItem,
    ClearSnapshotsResponse,
    HealthOverviewResponse,
    HealthTaskItem,
    RunHealthCheckResponse,
    ScheduleCheckResponse,
)
from app.services.collector.health import health_service

router = APIRouter(
    prefix="/collector/health",
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/overview", response_model=HealthOverviewResponse)
async def get_health_overview(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HealthOverviewResponse:
    """总览：健康分、状态计数、24h 成功率、分域概览与检测时间。"""
    data = await health_service.get_overview(session)
    return HealthOverviewResponse.model_validate(data)


@router.get("/tasks", response_model=list[HealthTaskItem])
async def list_health_tasks(
    session: Annotated[AsyncSession, Depends(get_db)],
    domain: str | None = None,
    status: str | None = None,
) -> list[HealthTaskItem]:
    """实例明细（快照行 + cron/启用状态），支持域与状态过滤。"""
    rows = await health_service.get_tasks(session, domain=domain, status=status)
    return [HealthTaskItem.model_validate(row) for row in rows]


@router.get("/channels", response_model=list[ChannelHealthItem])
async def list_health_channels(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChannelHealthItem]:
    """渠道视图：按 source 聚合实例数/成功率/故障数/归因分布。"""
    rows = await health_service.get_channels(session)
    return [ChannelHealthItem.model_validate(row) for row in rows]


@router.get("/schedule-check", response_model=ScheduleCheckResponse)
async def get_schedule_check(
    session: Annotated[AsyncSession, Depends(get_db)],
    date: date_type = Query(description="核对日期（CN 日历日）"),
) -> ScheduleCheckResponse:
    """按任意历史日期核对「应跑 vs 实跑」（按运行日志现算）。"""
    today = today_cn()
    if date > today or date < today - timedelta(days=365):
        raise UnprocessableEntityError("date 须为最近一年内、不晚于今日的 CN 日历日")
    data = await health_service.get_schedule_check(session, date)
    return ScheduleCheckResponse.model_validate(data)


@router.post("/run", response_model=RunHealthCheckResponse)
async def run_health_check(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunHealthCheckResponse:
    """立即执行一次健康检测并返回新快照摘要（免等下个 cron 点）。"""
    summary = await health_service.run_check(session)
    return RunHealthCheckResponse.model_validate(summary)


@router.delete("/snapshots", response_model=ClearSnapshotsResponse)
async def clear_health_snapshots(
    session: Annotated[AsyncSession, Depends(get_db)],
    task_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> ClearSnapshotsResponse:
    """清空健康快照（可选过滤）；下个检测点或「立即检测」会重建。"""
    deleted = await health_service.clear_snapshots(
        session, task_type=task_type, source=source
    )
    return ClearSnapshotsResponse(deleted=deleted)
