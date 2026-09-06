"""财务三表（资产负债/利润/现金流）查询仓储。"""

from datetime import date
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_balance_sheet import BalanceSheet
from app.models.financial_cash_flow_statement import CashFlowStatement
from app.models.financial_income_statement import IncomeStatement

_StatementT = TypeVar(
    "_StatementT", BalanceSheet, IncomeStatement, CashFlowStatement
)


async def get_statement(
    session: AsyncSession,
    model: type[_StatementT],
    stock_code: str,
    report_date: date | None = None,
) -> _StatementT | None:
    """取单张报表：指定报告期取该期行，否则取最新一期。"""
    stmt = select(model).where(model.stock_code == stock_code)
    if report_date:
        stmt = stmt.where(model.report_date == report_date)
    else:
        stmt = stmt.order_by(model.report_date.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_statements(
    session: AsyncSession,
    model: type[_StatementT],
    stock_code: str,
    limit: int = 8,
) -> list[_StatementT]:
    """取单张报表最近 limit 个报告期（报告期倒序）。"""
    stmt = (
        select(model)
        .where(model.stock_code == stock_code)
        .order_by(model.report_date.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
