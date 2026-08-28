"""Unit tests for AI agent database tools."""

import inspect
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools import db_tools
from app.models.financial_balance_sheet import BalanceSheet
from app.models.financial_income_statement import IncomeStatement
from app.models.stock import StockBasic


@pytest.mark.unit
class TestQueryIndustryCompanies:
    @pytest.mark.asyncio
    async def test_returns_business_scope_and_industry_tags(self) -> None:
        items = [
            StockBasic(
                stock_code="600703",
                stock_name="三安光电",
                market="SH",
                industry_level_1="半导体",
                industry_level_2="半导体材料",
                industry_level_3="化合物半导体",
                business_scope="化合物半导体材料研发、生产与销售",
            )
        ]
        result = MagicMock()
        result.scalars.return_value.all.return_value = items
        session = AsyncMock()
        session.execute.return_value = result

        rows = await db_tools.query_industry_companies(session, "半导体")

        assert rows == [
            {
                "stock_code": "600703",
                "stock_name": "三安光电",
                "market": "SH",
                "industry_level_2": "半导体材料",
                "industry_level_3": "化合物半导体",
                "business_scope": "化合物半导体材料研发、生产与销售",
            }
        ]

    def test_default_limit_is_150(self) -> None:
        signature = inspect.signature(db_tools.query_industry_companies)
        assert signature.parameters["limit"].default == 150

    @pytest.mark.asyncio
    async def test_matches_all_industry_levels(self) -> None:
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session = AsyncMock()
        session.execute.return_value = result

        await db_tools.query_industry_companies(session, "半导体")

        stmt = str(session.execute.await_args.args[0])
        for column in ("industry_level_1", "industry_level_2", "industry_level_3"):
            assert column in stmt


@pytest.mark.unit
class TestRatioHelpers:
    def test_safe_divide(self) -> None:
        assert db_tools.safe_divide(Decimal("1"), Decimal("4")) == 0.25
        assert db_tools.safe_divide(None, Decimal("4")) is None
        assert db_tools.safe_divide(Decimal("1"), Decimal("0")) is None

    def test_calculate_growth(self) -> None:
        assert db_tools.calculate_growth(Decimal("120"), Decimal("100")) == 20.0
        assert db_tools.calculate_growth(Decimal("80"), Decimal("-100")) == 180.0
        assert db_tools.calculate_growth(Decimal("120"), None) is None
        assert db_tools.calculate_growth(Decimal("120"), Decimal("0")) is None


@pytest.mark.unit
class TestQueryFinancialData:
    @pytest.mark.asyncio
    async def test_computes_metrics_with_year_ago(self) -> None:
        incomes = [
            IncomeStatement(
                stock_code="600703",
                report_date=date(2026, 3, 31),
                report_type="一季报",
                total_revenue=Decimal("120"),
                operating_cost=Decimal("60"),
                research_development_expense=Decimal("12"),
            ),
            IncomeStatement(
                stock_code="600703",
                report_date=date(2025, 12, 31),
                report_type="年报",
                total_revenue=Decimal("400"),
            ),
            IncomeStatement(
                stock_code="600703",
                report_date=date(2025, 3, 31),
                report_type="一季报",
                total_revenue=Decimal("100"),
            ),
        ]
        balance = BalanceSheet(
            stock_code="600703",
            report_date=date(2026, 3, 31),
            report_type="一季报",
            accounts_receivable=Decimal("30"),
        )

        income_result = MagicMock()
        income_result.scalars.return_value.all.return_value = incomes
        balance_result = MagicMock()
        balance_result.scalar_one_or_none.return_value = balance
        session = AsyncMock()
        session.execute.side_effect = [income_result, balance_result]

        rows = await db_tools.query_financial_data(session, ["600703"])

        assert len(rows) == 1
        row = rows[0]
        assert row["has_data"] is True
        assert row["gross_margin_pct"] == 50.0
        # 2026-03-31 对比 2025-03-31（间隔 365 天，命中同比窗口）
        assert row["revenue_yoy_pct"] == 20.0
        assert row["rd_ratio_pct"] == 10.0
        assert row["receivables_turnover"] == 4.0

    @pytest.mark.asyncio
    async def test_no_income_data(self) -> None:
        income_result = MagicMock()
        income_result.scalars.return_value.all.return_value = []
        session = AsyncMock()
        session.execute.return_value = income_result

        rows = await db_tools.query_financial_data(session, ["999999"])

        assert rows == [{"stock_code": "999999", "has_data": False}]


@pytest.mark.unit
class TestSearchVectorKb:
    @pytest.mark.asyncio
    async def test_falls_back_to_research_news_when_es_unavailable(self) -> None:
        publish = datetime(2026, 7, 20, tzinfo=timezone.utc)
        news_result = MagicMock()
        news_result.all.return_value = [
            ("research", "半导体行业深度", "国产替代加速", publish)
        ]
        session = AsyncMock()
        session.execute.return_value = news_result

        with patch(
            "app.services.common.knowledge_base_service.get_knowledge_base_service",
            side_effect=Exception("es down"),
        ):
            rows = await db_tools.search_vector_kb(session, "半导体 产业链")

        assert rows == [
            {
                "title": "半导体行业深度",
                "content": "国产替代加速",
                "publish_date": publish.isoformat(),
            }
        ]
