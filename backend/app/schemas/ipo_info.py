"""Pydantic schemas for IPO information."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IpoInfoBase(BaseModel):
    """Base fields for IPO information."""

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


class IpoInfoCreate(IpoInfoBase):
    """Request schema for creating an IPO record."""


class IpoInfoUpdate(BaseModel):
    """Request schema for updating an IPO record."""

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


class IpoInfoResponse(IpoInfoBase):
    """Response schema for an IPO record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
