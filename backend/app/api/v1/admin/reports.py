"""Admin report (file metadata) management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.models.file_metadata import FileMetadata
from app.schemas.file_metadata import (
    FileMetadataCreate,
    FileMetadataResponse,
    FileMetadataUpdate,
)
from app.schemas.stock import PaginatedResponse
from app.services.admin_report_service import AdminReportService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/", response_model=PaginatedResponse)
async def list_reports(
    session: Annotated[AsyncSession, Depends(get_db)],
    stock_code: str | None = None,
    file_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """查询研报文件列表。"""
    items, total = await AdminReportService(session).list_reports(
        stock_code, file_type, page, page_size
    )
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[FileMetadataResponse.model_validate(item) for item in items],
    )


@router.post(
    "/",
    response_model=FileMetadataResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    data: FileMetadataCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FileMetadataResponse:
    """创建研报文件元数据。"""
    report = await AdminReportService(session).create_report(data)
    return FileMetadataResponse.model_validate(report)


@router.get("/{report_id}", response_model=FileMetadataResponse)
async def get_report(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FileMetadataResponse:
    """获取单条研报文件元数据。"""
    report = await session.get(FileMetadata, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return FileMetadataResponse.model_validate(report)


@router.put("/{report_id}", response_model=FileMetadataResponse)
async def update_report(
    report_id: int,
    data: FileMetadataUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FileMetadataResponse:
    """更新研报文件元数据。"""
    report = await AdminReportService(session).update_report(report_id, data)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return FileMetadataResponse.model_validate(report)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除研报文件元数据。"""
    try:
        await AdminReportService(session).delete_report(report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
