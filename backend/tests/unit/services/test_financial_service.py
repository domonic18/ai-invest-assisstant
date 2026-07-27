"""Unit tests for financial health service."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.financial_balance_sheet import BalanceSheet
from app.models.financial_cash_flow_statement import CashFlowStatement
from app.models.financial_income_statement import IncomeStatement
from app.services import financial_service


@pytest.mark.unit
class TestFinancialService:
    @pytest.mark.asyncio
    async def test_get_health_calculates_metrics(self) -> None:
        session = AsyncMock()
        balance = BalanceSheet(
            stock_code="000001",
            report_date=date(2024, 3, 31),
            report_type="年报",
            total_assets=Decimal("1000"),
            total_liabilities=Decimal("500"),
            current_assets=Decimal("300"),
            current_liabilities=Decimal("150"),
            total_equity=Decimal("500"),
            created_at=datetime(2024, 3, 31, 0, 0, 0),
        )
        income = IncomeStatement(
            stock_code="000001",
            report_date=date(2024, 3, 31),
            report_type="年报",
            total_revenue=Decimal("800"),
            operating_cost=Decimal("600"),
            net_profit=Decimal("100"),
            created_at=datetime(2024, 3, 31, 0, 0, 0),
        )
        cash = CashFlowStatement(
            stock_code="000001",
            report_date=date(2024, 3, 31),
            report_type="年报",
            cash_flow_from_operations=Decimal("120"),
            created_at=datetime(2024, 3, 31, 0, 0, 0),
        )

        session.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: balance),
            MagicMock(scalar_one_or_none=lambda: income),
            MagicMock(scalar_one_or_none=lambda: cash),
        ]

        result = await financial_service.get_health(session, "000001")

        assert result.stock_code == "000001"
        assert result.report_date == date(2024, 3, 31)
        assert result.metrics["debt_ratio"] == pytest.approx(0.5)
        assert result.metrics["current_ratio"] == pytest.approx(2.0)
        assert result.metrics["gross_margin"] == pytest.approx(0.25)
        assert result.metrics["net_margin"] == pytest.approx(0.125)
        assert result.metrics["roe"] == pytest.approx(0.2)
        assert result.metrics["operating_cf_ratio"] == pytest.approx(0.15)

    @pytest.mark.asyncio
    async def test_get_health_no_data(self) -> None:
        session = AsyncMock()
        session.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)

        result = await financial_service.get_health(session, "000001")

        assert result.stock_code == "000001"
        assert result.report_date is None
        assert result.metrics == {}

    @pytest.mark.asyncio
    async def test_get_health_with_report_date(self) -> None:
        session = AsyncMock()
        target = date(2023, 12, 31)
        balance = BalanceSheet(
            stock_code="000001",
            report_date=target,
            report_type="年报",
            created_at=datetime(2023, 12, 31, 0, 0, 0),
        )
        income = IncomeStatement(
            stock_code="000001",
            report_date=target,
            report_type="年报",
            created_at=datetime(2023, 12, 31, 0, 0, 0),
        )
        cash = CashFlowStatement(
            stock_code="000001",
            report_date=target,
            report_type="年报",
            created_at=datetime(2023, 12, 31, 0, 0, 0),
        )

        session.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: balance),
            MagicMock(scalar_one_or_none=lambda: income),
            MagicMock(scalar_one_or_none=lambda: cash),
        ]

        result = await financial_service.get_health(
            session, "000001", report_date=target
        )

        assert result.report_date == target

    @pytest.mark.asyncio
    async def test_get_health_history_returns_sorted_periods(self) -> None:
        session = AsyncMock()
        balance_q1 = BalanceSheet(
            stock_code="000001",
            report_date=date(2024, 3, 31),
            report_type="q1",
            total_assets=Decimal("1000"),
            total_liabilities=Decimal("500"),
            current_assets=Decimal("300"),
            current_liabilities=Decimal("150"),
            total_equity=Decimal("500"),
            created_at=datetime(2024, 3, 31, 0, 0, 0),
        )
        balance_annual = BalanceSheet(
            stock_code="000001",
            report_date=date(2023, 12, 31),
            report_type="annual",
            total_assets=Decimal("1000"),
            total_liabilities=Decimal("400"),
            current_assets=Decimal("300"),
            current_liabilities=Decimal("150"),
            total_equity=Decimal("600"),
            created_at=datetime(2023, 12, 31, 0, 0, 0),
        )
        income_annual = IncomeStatement(
            stock_code="000001",
            report_date=date(2023, 12, 31),
            report_type="annual",
            total_revenue=Decimal("800"),
            operating_cost=Decimal("600"),
            net_profit=Decimal("100"),
            created_at=datetime(2023, 12, 31, 0, 0, 0),
        )

        session.execute.side_effect = [
            MagicMock(scalars=lambda: MagicMock(all=lambda: [balance_q1, balance_annual])),
            MagicMock(scalars=lambda: MagicMock(all=lambda: [income_annual])),
            MagicMock(scalars=lambda: MagicMock(all=lambda: [])),
        ]

        result = await financial_service.get_health_history(session, "000001", limit=8)

        assert len(result) == 2
        assert result[0].report_date == date(2023, 12, 31)
        assert result[1].report_date == date(2024, 3, 31)
        assert result[0].metrics["debt_ratio"] == pytest.approx(0.4)
        assert result[1].metrics["debt_ratio"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_get_health_history_no_data(self) -> None:
        session = AsyncMock()
        empty_result = MagicMock(scalars=lambda: MagicMock(all=lambda: []))
        session.execute.return_value = empty_result

        result = await financial_service.get_health_history(session, "000001")

        assert result == []
