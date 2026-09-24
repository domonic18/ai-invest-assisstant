"""板块详情 API 路由（真实指数 K 线 + 资金流 + 异动日标注）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.sector_detail import SectorDetailResponse
from app.services.market import sector_detail_service

router = APIRouter()


@router.get("/{sector_type}/{sector_code}", response_model=SectorDetailResponse | None)
async def get_sector_detail(
    session: Annotated[AsyncSession, Depends(get_db)],
    sector_type: Annotated[str, Path(pattern="^(industry|concept)$")],
    sector_code: str,
) -> SectorDetailResponse | None:
    """板块详情：K 线走势 + 主力资金 + 异动日（板块不存在返回 null）。"""
    return await sector_detail_service.get_sector_detail(session, sector_type, sector_code)
