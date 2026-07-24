"""Internal database tools for AI Agent."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_balance_sheet import BalanceSheet
from app.models.financial_income_statement import IncomeStatement
from app.models.kline import KlineDaily
from app.models.news_announcement import NewsAnnouncement
from app.models.stock import StockBasic


async def query_industry_companies(
    session: AsyncSession, industry: str, limit: int = 150
) -> list[dict]:
    """查询指定行业的上市公司（含经营范围，供产业链环节推导）。

    行业名按一/二/三级行业标签匹配（如「半导体」为二级行业，归属一级「电子」）。
    """
    result = await session.execute(
        select(StockBasic)
        .where(
            or_(
                StockBasic.industry_level_1 == industry,
                StockBasic.industry_level_2 == industry,
                StockBasic.industry_level_3 == industry,
            )
        )
        .limit(limit)
    )
    return [
        {
            "stock_code": item.stock_code,
            "stock_name": item.stock_name,
            "market": item.market,
            "industry_level_2": item.industry_level_2,
            "industry_level_3": item.industry_level_3,
            "business_scope": item.business_scope,
        }
        for item in result.scalars().all()
    ]


async def query_stock_kline(
    session: AsyncSession,
    stock_code: str,
    limit: int = 30,
) -> list[dict]:
    """查询指定股票近期 K 线数据。"""
    result = await session.execute(
        select(KlineDaily)
        .where(KlineDaily.stock_code == stock_code)
        .order_by(KlineDaily.trade_date.desc())
        .limit(limit)
    )
    return [
        {
            "trade_date": item.trade_date.isoformat(),
            "open": float(item.open) if item.open is not None else None,
            "high": float(item.high) if item.high is not None else None,
            "low": float(item.low) if item.low is not None else None,
            "close": float(item.close) if item.close is not None else None,
            "volume": item.volume,
            "amount": float(item.amount) if item.amount is not None else None,
            "change_pct": float(item.change_pct) if item.change_pct is not None else None,
        }
        for item in result.scalars().all()
    ]


def safe_divide(
    numerator: Decimal | None, denominator: Decimal | None
) -> float | None:
    """安全除法，分母为空或为零时返回 None。"""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator / denominator)


def calculate_growth(
    latest: Decimal | None, base: Decimal | None
) -> float | None:
    """计算增长率（百分比），base 为零或缺失时返回 None。"""
    if latest is None or base is None or base == 0:
        return None
    return round(float((latest - base) / abs(base)) * 100, 2)


def _pct(value: float | None) -> float | None:
    """将比率转为百分比并保留两位小数。"""
    return round(value * 100, 2) if value is not None else None


async def _query_stock_financials(
    session: AsyncSession, stock_code: str, periods: int
) -> dict[str, Any]:
    """查询单只股票近 N 期财务指标（毛利率/营收同比/研发占比/应收周转）。"""
    income_stmt = (
        select(IncomeStatement)
        .where(IncomeStatement.stock_code == stock_code)
        .order_by(IncomeStatement.report_date.desc())
        .limit(periods + 4)
    )
    incomes = list((await session.execute(income_stmt)).scalars().all())
    if not incomes:
        return {"stock_code": stock_code, "has_data": False}

    balance_stmt = (
        select(BalanceSheet)
        .where(BalanceSheet.stock_code == stock_code)
        .order_by(BalanceSheet.report_date.desc())
        .limit(1)
    )
    balance = (await session.execute(balance_stmt)).scalar_one_or_none()

    latest = incomes[0]
    year_ago = next(
        (
            item
            for item in incomes[1:]
            if 300 <= (latest.report_date - item.report_date).days <= 400
        ),
        None,
    )

    receivables_turnover = (
        safe_divide(latest.total_revenue, balance.accounts_receivable)
        if balance
        else None
    )

    return {
        "stock_code": stock_code,
        "has_data": True,
        "report_date": latest.report_date.isoformat(),
        "gross_margin_pct": _pct(
            safe_divide(
                (latest.total_revenue or Decimal("0"))
                - (latest.operating_cost or Decimal("0")),
                latest.total_revenue,
            )
        ),
        "revenue_yoy_pct": calculate_growth(
            latest.total_revenue, year_ago.total_revenue if year_ago else None
        ),
        "rd_ratio_pct": _pct(
            safe_divide(latest.research_development_expense, latest.total_revenue)
        ),
        "receivables_turnover": (
            round(receivables_turnover, 2)
            if receivables_turnover is not None
            else None
        ),
    }


async def query_financial_data(
    session: AsyncSession, stock_codes: list[str], periods: int = 3
) -> list[dict[str, Any]]:
    """批量查询多只股票的财务指标，无数据的股票 has_data=False。"""
    return [
        await _query_stock_financials(session, code, periods) for code in stock_codes
    ]


async def search_news(
    session: AsyncSession,
    keyword: str,
    days: int = 30,
    limit: int = 15,
    doc_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """按关键词检索近期新闻/公告/研报标题与摘要。"""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    conditions = [
        NewsAnnouncement.publish_date >= since,
        or_(
            NewsAnnouncement.title.ilike(f"%{keyword}%"),
            NewsAnnouncement.industry_tags.contains([keyword]),
        ),
    ]
    if doc_types:
        conditions.append(NewsAnnouncement.doc_type.in_(doc_types))
    stmt = (
        select(
            NewsAnnouncement.doc_type,
            NewsAnnouncement.title,
            NewsAnnouncement.summary,
            NewsAnnouncement.publish_date,
        )
        .where(*conditions)
        .order_by(NewsAnnouncement.publish_date.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "doc_type": doc_type,
            "title": title,
            "summary": (summary or "")[:200],
            "publish_date": publish_date.isoformat() if publish_date else None,
        }
        for doc_type, title, summary, publish_date in rows
    ]


async def search_vector_kb(
    session: AsyncSession, query: str, limit: int = 5
) -> list[dict[str, Any]]:
    """检索知识库研报片段；ES 不可用时回退 news_announcement 研报记录。"""
    try:
        from app.services.knowledge_base_service import get_knowledge_base_service

        service = get_knowledge_base_service()
        client = await service._get_client()
        response = await client.search(
            index=service.index_name,
            query={"match": {"content": query}},
            size=limit,
            source={"includes": ["title", "content", "publish_date"]},
        )
        hits = response.get("hits", {}).get("hits", [])
        if hits:
            return [
                {
                    "title": hit["_source"].get("title"),
                    "content": (hit["_source"].get("content") or "")[:300],
                    "publish_date": hit["_source"].get("publish_date"),
                }
                for hit in hits
            ]
    except Exception:  # noqa: BLE001
        pass

    rows = await search_news(session, query, days=90, limit=limit, doc_types=["research"])
    return [
        {"title": row["title"], "content": row["summary"], "publish_date": row["publish_date"]}
        for row in rows
    ]
