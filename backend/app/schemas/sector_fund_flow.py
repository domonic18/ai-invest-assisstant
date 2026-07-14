"""Pydantic schemas for sector fund flow (hotspot)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SectorFundFlowResponse(BaseModel):
    """板块资金流向响应。"""

    model_config = ConfigDict(from_attributes=True)

    sector_code: str
    sector_name: str
    sector_type: str
    trade_date: date
    main_net_inflow: Decimal | None = None
    super_large_net: Decimal | None = None
    large_net: Decimal | None = None
    medium_net: Decimal | None = None
    small_net: Decimal | None = None
    top_stock_code: str | None = None
    top_stock_name: str | None = None
    created_at: datetime


class HotspotListRequest(BaseModel):
    """热点列表请求。"""

    sector_type: str | None = Field(None, max_length=20)
    trade_date: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
