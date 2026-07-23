"""Industry chain analysis skill execution."""

from typing import Any, cast

from pydantic_ai import Agent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.llm_router import build_agent
from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.agent.tools import db_tools
from app.core.config import get_settings
from app.models.stock import StockBasic
from app.schemas.chain import ChainAnalysisResult
from app.services.llm_config_service import resolve_default_llm

_MAX_NODES = 25
_MAX_COMPANIES_PER_NODE = 5


def _format_financial_context(financials: list[dict[str, Any]]) -> list[str]:
    """格式化财务指标上下文行。"""
    lines = []
    for item in financials:
        if not item.get("has_data"):
            continue
        parts = [f"{item['stock_code']}"]
        if item.get("gross_margin_pct") is not None:
            parts.append(f"毛利率 {item['gross_margin_pct']}%")
        if item.get("revenue_yoy_pct") is not None:
            parts.append(f"营收同比 {item['revenue_yoy_pct']}%")
        if item.get("rd_ratio_pct") is not None:
            parts.append(f"研发占比 {item['rd_ratio_pct']}%")
        if item.get("receivables_turnover") is not None:
            parts.append(f"应收周转 {item['receivables_turnover']}")
        lines.append("- " + "，".join(parts))
    return lines


async def _validate(
    session: AsyncSession, result: ChainAnalysisResult
) -> ChainAnalysisResult:
    """后置校验：剔除幻觉股票代码、截断 strength、限制节点与公司规模。"""
    codes = {
        company.code
        for node in result.nodes
        for company in node.companies
    }
    codes |= {item.code for item in result.key_companies_summary}
    valid_codes: set[str] = set()
    if codes:
        stmt = select(StockBasic.stock_code).where(StockBasic.stock_code.in_(codes))
        valid_codes = set((await session.execute(stmt)).scalars().all())

    for node in result.nodes[: _MAX_NODES]:
        node.companies = [
            company
            for company in node.companies[: _MAX_COMPANIES_PER_NODE]
            if company.code in valid_codes
        ]
    result.nodes = result.nodes[:_MAX_NODES]

    node_names = {node.name for node in result.nodes}
    result.edges = [
        edge
        for edge in result.edges
        if edge.source in node_names and edge.target in node_names
    ]
    for edge in result.edges:
        edge.strength = max(0.0, min(100.0, edge.strength))

    result.key_companies_summary = [
        item for item in result.key_companies_summary if item.code in valid_codes
    ]
    return result


async def analyze_industry_chain(
    session: AsyncSession,
    industry: str,
    focus: str | None = None,
) -> ChainAnalysisResult:
    """执行产业链分析 Skill。"""
    prompt_loader = PromptLoader(get_settings().prompts_dir)
    prompt_config = prompt_loader.load("skills", "industry-chain-analysis")

    companies = await db_tools.query_industry_companies(session, industry, limit=30)
    context_lines = [f"行业：{industry}，共找到 {len(companies)} 家上市公司"]
    for company in companies:
        context_lines.append(
            f"- {company['stock_code']} {company['stock_name']} "
            f"({company['market']}) {company['industry_level_2']} / {company['industry_level_3']}"
        )

    financials = await db_tools.query_financial_data(
        session, [company["stock_code"] for company in companies[:15]]
    )
    financial_lines = _format_financial_context(financials)

    news = await db_tools.search_news(session, industry, days=30, limit=10)
    news_lines = [
        f"- [{item['doc_type']}] {item['title']}" for item in news
    ]

    kb_docs = await db_tools.search_vector_kb(session, f"{industry} 产业链 上下游")
    kb_lines = [
        f"- {item['title']}: {item['content'][:150]}" for item in kb_docs if item.get("title")
    ]

    sections = [
        "\n".join(context_lines),
        "财务指标（近一期）：\n" + "\n".join(financial_lines) if financial_lines else "",
        "近期行业动态：\n" + "\n".join(news_lines) if news_lines else "",
        "研报摘录：\n" + "\n".join(kb_lines) if kb_lines else "",
    ]
    context = "\n\n".join(section for section in sections if section)

    user_prompt = PromptRenderer.render(
        prompt_config.user_prompt_template,
        industry=industry,
        focus=focus or "产业链上下游结构与投资价值",
        context=context,
    )

    resolved = await resolve_default_llm(session)
    model_config = {
        "provider": resolved.provider,
        "model": resolved.model_name,
        "api_key": resolved.api_key,
        "base_url": resolved.base_url,
    }
    agent: Agent = build_agent(
        prompt_config=prompt_config,
        model_config=model_config,
        result_type=ChainAnalysisResult,
    )

    result = await agent.run(user_prompt)
    output = cast(ChainAnalysisResult, result.output)
    return await _validate(session, output)


async def run_skill(
    session: AsyncSession,
    params: dict[str, Any],
) -> ChainAnalysisResult:
    """Skill 统一入口。"""
    industry = params.get("industry", "")
    focus = params.get("focus")
    return await analyze_industry_chain(session, industry, focus)
