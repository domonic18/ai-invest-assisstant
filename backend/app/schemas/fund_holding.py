"""个股基金持仓的 Pydantic schemas。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FundHoldingBase(BaseModel):
    """基金持仓的基础字段。"""

    stock_code: str = Field(..., max_length=10)
    stock_name: str | None = Field(None, max_length=100)
    report_date: date
    holding_fund_count: int | None = None
    total_holding_quantity: int | None = None
    holding_market_value: Decimal | None = None
    holding_change: str | None = Field(None, max_length=20)
    holding_change_quantity: int | None = None
    holding_change_ratio: Decimal | None = None
    source: str | None = Field(None, max_length=50)


class FundHoldingCreate(FundHoldingBase):
    """创建基金持仓记录的请求 schema。"""


class FundHoldingUpdate(BaseModel):
    """更新基金持仓记录的请求 schema。"""

    stock_name: str | None = Field(None, max_length=100)
    report_date: date | None = None
    holding_fund_count: int | None = None
    total_holding_quantity: int | None = None
    holding_market_value: Decimal | None = None
    holding_change: str | None = Field(None, max_length=20)
    holding_change_quantity: int | None = None
    holding_change_ratio: Decimal | None = None
    source: str | None = Field(None, max_length=50)


class FundHoldingResponse(FundHoldingBase):
    """基金持仓记录的响应 schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
