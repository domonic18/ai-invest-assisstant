"""管理后台 AI 分析结果通用管理 API 端点。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.ai_result import AdminAiResultDetail, AdminAiSkillInfo
from app.schemas.stock import PaginatedResponse
from app.services.admin.ai_results import AdminAiResultService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/skills", response_model=list[AdminAiSkillInfo])
async def list_ai_skills() -> list[AdminAiSkillInfo]:
    """已纳管 AI skill 清单（管理页 Tab 与完成事件订阅的数据源）。

    声明在 ``GET /{row_id}`` 之前，避免路径被参数路由吞掉。
    """
    return AdminAiResultService.list_skills()


@router.get("/", response_model=PaginatedResponse)
async def list_ai_results(
    session: Annotated[AsyncSession, Depends(get_db)],
    skill_id: str = Query(),
    status_filter: str | None = Query(default=None, alias="status"),
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    """分页返回每个业务键最新一条生成记录的元信息。"""
    items, total = await AdminAiResultService(session).list_results(
        skill_id,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/{row_id}", response_model=AdminAiResultDetail)
async def get_ai_result(
    row_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminAiResultDetail:
    """读取单条生成记录的详情（含结构化输出全文）。"""
    return await AdminAiResultService(session).get_detail(row_id)


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_result(
    row_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除该业务键的全部生成记录（用户编辑副本与关联版本内容不受影响）。"""
    await AdminAiResultService(session).delete(row_id)
