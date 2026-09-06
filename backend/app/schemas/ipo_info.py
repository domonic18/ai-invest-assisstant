"""新股发行信息的 Pydantic schemas。"""

from datetime import date, datetime

from pydantic import Field

from app.schemas.base import CamelModel


class IPOInfoBase(CamelModel):
    """新股发行信息的基础字段。"""

    stock_code: str = Field(..., max_length=10)
    stock_name: str | None = Field(None, max_length=100)
    listing_date: date | None = None
    subscription_date: date | None = None
    issue_price: float | None = None
    total_issue_quantity: float | None = None
    issue_pe_ratio: float | None = None
    online_winning_rate: float | None = None
    lottery_result_date: date | None = None
    winning_announcement_date: date | None = None
    payment_date: date | None = None
    online_subscription_limit: float | None = None
    online_issue_quantity: float | None = None
    source: str | None = Field(None, max_length=50)


class IPOInfoCreate(IPOInfoBase):
    """创建新股发行记录的请求 schema。"""


class IPOInfoUpdate(CamelModel):
    """更新新股发行记录的请求 schema。"""

    stock_name: str | None = Field(None, max_length=100)
    listing_date: date | None = None
    subscription_date: date | None = None
    issue_price: float | None = None
    total_issue_quantity: float | None = None
    issue_pe_ratio: float | None = None
    online_winning_rate: float | None = None
    lottery_result_date: date | None = None
    winning_announcement_date: date | None = None
    payment_date: date | None = None
    online_subscription_limit: float | None = None
    online_issue_quantity: float | None = None
    source: str | None = Field(None, max_length=50)


class IPOInfoResponse(IPOInfoBase):
    """新股发行记录的响应 schema。"""

    id: int
    created_at: datetime
