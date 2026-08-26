"""助手数据工具：LangChain ``@tool`` 包装既有 service / db_tools。

只读查询工具统一做行数/天数上限裁剪，防止单次工具输出撑爆模型上下文。
产业链分析的持久化通过 ``persist_chain_analysis`` 显式写操作工具完成，便于
过程可观测与后续接入 HITL。
"""

from datetime import date
from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, InjectedToolArg, tool

from app.agent.tools import db_tools
from app.core.database import AsyncSessionLocal
from app.services import (
    auction_service,
    index_quotation_service,
    sector_fund_flow_service,
    stock_service,
)
from app.services import market_stats_service as market_stats_svc

INDUSTRY_COMPANIES_MAX_LIMIT = 200


def _normalize_industry(industry: str) -> str:
    """规范化行业名称，去除常见后缀，保证前后端一致匹配。"""
    name = industry.strip()
    for suffix in ("产业链", "行业", "板块"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


@tool
async def query_industry_companies(
    industry: str, limit: int = 150
) -> list[dict[str, Any]]:
    """按行业名称查询上市公司清单，返回股票代码、名称、二级/三级行业、经营范围。

    Args:
        industry: 行业名称，如 "半导体"。
        limit: 返回公司数上限，默认 150，最大 200。
    """
    limit = max(1, min(limit, INDUSTRY_COMPANIES_MAX_LIMIT))
    async with AsyncSessionLocal() as session:
        return await db_tools.query_industry_companies(session, industry, limit)


@tool
async def persist_chain_analysis(
    industry: str,
    result: dict[str, Any],
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> dict[str, Any]:
    """将产业链分析结果持久化到数据库，生成新版本并在产业链页面展示。

    Args:
        industry: 行业名称。
        result: 符合 ChainAnalysisResult schema 的结构化 JSON 对象。
        config: LangGraph 运行时配置，自动注入当前用户 ID。
    """
    from app.schemas.chain import ChainAnalysisResult
    from app.services import chain_service

    normalized = _normalize_industry(industry)
    user_id = int(config.get("configurable", {}).get("user_id", 0))
    async with AsyncSessionLocal() as session:
        parsed = ChainAnalysisResult.model_validate(result)
        response = await chain_service.persist_analysis_result(
            session, normalized, parsed, user_id=user_id
        )
        payload = {
            "industry": normalized,
            "version_id": response.version_id,
            "version_no": response.version_no,
            "status": response.status,
            "__event__": {
                "type": "industry_chain.analysis_complete",
                "industry": normalized,
                "version_id": response.version_id,
                "version_no": response.version_no,
            },
        }
        return payload


FINANCIAL_REPORT_MAX_LIMIT = 100


@tool
async def query_financial_reports(
    stock_code: str,
    report_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """查询系统中已存在的财报列表。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        report_type: 财报类型过滤，可选 annual / semi_annual / q1 / q3。
        start_date: 报告期起始，ISO 格式如 "2024-01-01"。
        end_date: 报告期截止，ISO 格式如 "2024-12-31"。
    """
    from app.services.financial_report_service import FinancialReportService

    try:
        resolved_start = date.fromisoformat(start_date) if start_date else None
        resolved_end = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        return {"error": "start_date / end_date 须为 YYYY-MM-DD 格式"}

    async with AsyncSessionLocal() as session:
        service = FinancialReportService(session)
        items, total = await service.list_reports(
            stock_code=stock_code,
            report_type=report_type,
            start_date=resolved_start,
            end_date=resolved_end,
            page_size=FINANCIAL_REPORT_MAX_LIMIT,
        )
        return {
            "total": total,
            "reports": [
                {
                    "id": item.id,
                    "stock_code": item.stock_code,
                    "report_type": item.report_type,
                    "report_date": item.report_date.isoformat() if item.report_date else None,
                    "original_name": item.original_name,
                    "has_pdf": bool(item.file_path),
                    "has_summary": bool(item.summary),
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in items
            ],
        }


@tool
async def download_financial_reports(
    stock_code: str,
    report_types: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """触发指定股票的财报采集任务（异步）。当系统中缺少所需财报时调用。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        report_types: 财报类型列表，可选 annual / semi_annual / q1 / q3；缺省则采集全部。
        start_date: 报告期起始，ISO 格式如 "2024-01-01"。
        end_date: 报告期截止，ISO 格式如 "2024-12-31"。
    """
    from app.services.financial_report_service import FinancialReportService

    try:
        resolved_start = date.fromisoformat(start_date) if start_date else None
        resolved_end = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        return {"error": "start_date / end_date 须为 YYYY-MM-DD 格式"}

    async with AsyncSessionLocal() as session:
        service = FinancialReportService(session)
        try:
            log = await service.trigger_collect(
                stock_code,
                report_types=report_types,
                start_date=resolved_start,
                end_date=resolved_end,
            )
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {"log_id": log.id, "status": log.status}


@tool
async def summarize_financial_report(report_id: int) -> dict[str, Any]:
    """获取单篇财报的 AI 摘要，用于从财报正文中提取业务亮点、风险与前景等定性信息。

    Args:
        report_id: 财报在系统中的 ID（由 query_financial_reports 返回的 id 字段）。
    """
    from app.services.financial_report_service import FinancialReportService

    async with AsyncSessionLocal() as session:
        service = FinancialReportService(session)
        try:
            return await service.summarize_report(report_id)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}


KLINE_MAX_DAYS = 120
FINANCIAL_MAX_CODES = 5
FINANCIAL_MAX_PERIODS = 4
NEWS_MAX_DAYS = 180
NEWS_MAX_ROWS = 30
KB_MAX_ROWS = 10
SECTOR_MAX_DAYS = 60
SECTOR_TOP_N = 10
AUCTION_MAX_DAYS = 30


@tool
async def get_stock_quote(stock_code: str) -> dict[str, Any] | None:
    """获取个股最新行情快照：现价、涨跌幅、成交量/额、总市值，Redis 实时缺失时回退最新日 K。

    Args:
        stock_code: 6 位股票代码，如 "000001"（平安银行）。
    """
    async with AsyncSessionLocal() as session:
        return await stock_service.get_stock_quote(session, stock_code)


@tool
async def get_stock_kline(stock_code: str, limit: int = 30) -> list[dict[str, Any]]:
    """查询个股近期日 K 线（日期、开高低收、成交量、涨跌幅），按交易日倒序。

    Args:
        stock_code: 6 位股票代码，如 "000001"。
        limit: 返回条数，1-120，默认 30。
    """
    limit = max(1, min(limit, KLINE_MAX_DAYS))
    async with AsyncSessionLocal() as session:
        return await db_tools.query_stock_kline(session, stock_code, limit)


@tool
async def query_financial_data(
    stock_codes: list[str], periods: int = 3
) -> list[dict[str, Any]]:
    """批量查询股票核心财务指标：最新报告期毛利率、营收同比、研发占比、应收账款周转。

    Args:
        stock_codes: 6 位股票代码列表，最多 5 只。
        periods: 参考期数，默认 3。
    """
    codes = stock_codes[:FINANCIAL_MAX_CODES]
    periods = max(1, min(periods, FINANCIAL_MAX_PERIODS))
    async with AsyncSessionLocal() as session:
        return await db_tools.query_financial_data(session, codes, periods)


@tool
async def search_news(
    keyword: str,
    days: int = 30,
    limit: int = 15,
    doc_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """按关键词检索近期新闻/公告/研报的标题与摘要。

    Args:
        keyword: 检索关键词，如 "半导体" 或股票名称。
        days: 回溯天数，1-180，默认 30。
        limit: 返回条数，1-30，默认 15。
        doc_types: 文档类型过滤，可选值 news / announcement / report。
    """
    days = max(1, min(days, NEWS_MAX_DAYS))
    limit = max(1, min(limit, NEWS_MAX_ROWS))
    async with AsyncSessionLocal() as session:
        return await db_tools.search_news(session, keyword, days, limit, doc_types)


@tool
async def search_vector_kb(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """检索研报知识库（全文检索），返回研报标题与内容片段；ES 不可用时自动回退研报标题检索。

    Args:
        query: 检索语句，如 "光模块 CPO 产能"。
        limit: 返回条数，1-10，默认 5。
    """
    limit = max(1, min(limit, KB_MAX_ROWS))
    async with AsyncSessionLocal() as session:
        return await db_tools.search_vector_kb(session, query, limit)


def _trim_sector_flow(response: Any, top_n: int) -> dict[str, Any]:
    """板块资金流响应裁剪：只保留净流入绝对值 Top N 板块的区间累计与最新值。"""
    dates = [d.isoformat() for d in response.dates]
    rows: list[dict[str, Any]] = []
    for sector in response.sectors:
        values = [v for v in sector.values if v is not None]
        period_net = round(sum(sector.values[i] or 0.0 for i in range(len(dates))), 2)
        rows.append(
            {
                "code": sector.code,
                "name": sector.name,
                "period_net_inflow_yi": period_net,
                "latest_yi": values[-1] if values else None,
            }
        )
    rows.sort(key=lambda r: abs(r["period_net_inflow_yi"]), reverse=True)
    return {
        "dates": [dates[0], dates[-1]] if dates else [],
        "unit": "亿元（主力净流入）",
        "sectors": rows[:top_n],
    }


@tool
async def get_sector_fund_flow(
    sector_type: str = "industry", days: int = 20, top: int = 10
) -> dict[str, Any]:
    """查询板块主力资金净流入排行（区间累计与最新一日，单位亿元）。当前仅支持行业板块。

    Args:
        sector_type: 板块类型，当前仅 "industry"。
        days: 统计区间交易日数，1-60，默认 20。
        top: 返回板块数，默认 10。
    """
    days = max(1, min(days, SECTOR_MAX_DAYS))
    async with AsyncSessionLocal() as session:
        response = await sector_fund_flow_service.get_sector_flow_trend(
            session, sector_type, days
        )
    return _trim_sector_flow(response, top)


@tool
async def get_market_overview(trade_date: str | None = None) -> dict[str, Any]:
    """获取大盘概览：四大指数行情 + 全市场涨跌家数、成交额（含环比）、涨停/跌停家数与情绪温度。

    Args:
        trade_date: 可选历史交易日，ISO 格式如 "2026-08-21"；缺省为最新交易日。
    """
    resolved: date | None = None
    if trade_date:
        try:
            resolved = date.fromisoformat(trade_date)
        except ValueError:
            return {"error": "trade_date 须为 YYYY-MM-DD 格式"}

    async with AsyncSessionLocal() as session:
        stats = await market_stats_svc.get_market_stats(session, resolved)
        quotes = await index_quotation_service.get_index_quotes(session, resolved)

    return {
        "market_stats": stats.model_dump(mode="json"),
        "index_quotes": [
            q.model_dump(mode="json", exclude={"trend"}) for q in quotes
        ],
    }


@tool
async def get_auction_summary(days: int = 5) -> dict[str, Any]:
    """查询指数集合竞价成交额趋势（单位亿元），反映开盘前资金活跃度。

    Args:
        days: 最近交易日数，1-30，默认 5。
    """
    days = max(1, min(days, AUCTION_MAX_DAYS))
    async with AsyncSessionLocal() as session:
        response = await auction_service.get_index_auction_trend(session, days=days)

    dates = [d.isoformat() for d in response.dates]
    series = [
        {
            "code": s.code,
            "name": s.name,
            "values_yi": s.values,
            "latest_yi": next((v for v in reversed(s.values) if v is not None), None),
        }
        for s in response.series
    ]
    return {"dates": dates, "series": series}


def build_assistant_tools() -> list[BaseTool]:
    """助手工具清单：只读查询工具 + 产业链分析持久化工具 + 财报工具。"""
    return [
        get_stock_quote,
        get_stock_kline,
        query_financial_data,
        search_news,
        search_vector_kb,
        get_sector_fund_flow,
        get_market_overview,
        get_auction_summary,
        query_industry_companies,
        persist_chain_analysis,
        query_financial_reports,
        download_financial_reports,
        summarize_financial_report,
    ]
