"""新股发行信息的 Pydantic schemas。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IPOInfoBase(BaseModel):
    """新股发行信息的基础字段。"""

    stock_code: str = Field(..., max_length=10)
    stock_name: str | None = Field(None, max_length=100)
    listing_date: date | None = None
    subscription_date: date | None = None
    issue_price: Decimal | None = None
    total_issue_quantity: Decimal | None = None
    issue_pe_ratio: Decimal | None = None
    online_winning_rate: Decimal | None = None
    lottery_result_date: date | None = None
    winning_announcement_date: date | None = None
    payment_date: date | None = None
    online_subscription_limit: Decimal | None = None
    online_issue_quantity: Decimal | None = None
    source: str | None = Field(None, max_length=50)


class IPOInfoCreate(IPOInfoBase):
    """创建新股发行记录的请求 schema。"""


class IPOInfoUpdate(BaseModel):
    """更新新股发行记录的请求 schema。"""

    stock_name: str | None = Field(None, max_length=100)
    listing_date: date | None = None
    subscription_date: date | None = None
    issue_price: Decimal | None = None
    total_issue_quantity: Decimal | None = None
    issue_pe_ratio: Decimal | None = None
    online_winning_rate: Decimal | None = None
    lottery_result_date: date | None = None
    winning_announcement_date: date | None = None
    payment_date: date | None = None
    online_subscription_limit: Decimal | None = None
    online_issue_quantity: Decimal | None = None
    source: str | None = Field(None, max_length=50)


class IPOInfoResponse(IPOInfoBase):
    """新股发行记录的响应 schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
