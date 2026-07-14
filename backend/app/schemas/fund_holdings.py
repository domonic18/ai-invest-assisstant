"""Pydantic schemas for fund holdings."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FundHoldingsBase(BaseModel):
    """Base fields for fund holdings."""

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


class FundHoldingsCreate(FundHoldingsBase):
    """Request schema for creating a fund holding record."""


class FundHoldingsUpdate(BaseModel):
    """Request schema for updating a fund holding record."""

    stock_name: str | None = Field(None, max_length=100)
    report_date: date | None = None
    holding_fund_count: int | None = None
    total_holding_quantity: int | None = None
    holding_market_value: Decimal | None = None
    holding_change: str | None = Field(None, max_length=20)
    holding_change_quantity: int | None = None
    holding_change_ratio: Decimal | None = None
    source: str | None = Field(None, max_length=50)


class FundHoldingsResponse(FundHoldingsBase):
    """Response schema for a fund holding record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
