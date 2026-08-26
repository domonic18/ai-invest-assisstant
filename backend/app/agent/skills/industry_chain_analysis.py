"""Industry chain analysis skill execution.

.. deprecated::
    该 PydanticAI 单轮执行器已被 Skill 驱动的 Assistant Agent 工作流替代。
    产业链分析逻辑现在由 ``skills/industry-chain-analysis/SKILL.md`` 描述，
    Agent 通过读取 SKILL.md 并调用平台工具完成分析。
    保留本模块仅作兼容，新实现请勿依赖。
"""

import warnings
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.agent.runtime import run_structured_agent
from app.agent.tools import db_tools
from app.core.config import get_settings
from app.models.stock import StockBasic
from app.schemas.chain import ChainAnalysisResult

warnings.warn(
    "industry_chain_analysis.run_skill is deprecated; "
    "use the Skill-driven Assistant Agent workflow instead.",
    DeprecationWarning,
    stacklevel=2,
)

_MAX_NODES = 40
_MAX_COMPANIES_PER_NODE = 5
_COMPANY_PREFETCH_LIMIT = 150
_FINANCIAL_PREFETCH_COUNT = 40
_BUSINESS_SCOPE_MAX_CHARS = 120


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

    companies = await db_tools.query_industry_companies(
        session, industry, limit=_COMPANY_PREFETCH_LIMIT
    )
    if not companies:
        raise ValueError(f"行业 {industry} 未匹配到上市公司，无法进行产业链分析")
    context_lines = [f"行业：{industry}，共找到 {len(companies)} 家上市公司"]
    for company in companies:
        scope = (company.get("business_scope") or "").replace("\n", " ").strip()
        if len(scope) > _BUSINESS_SCOPE_MAX_CHARS:
            scope = scope[:_BUSINESS_SCOPE_MAX_CHARS] + "…"
        context_lines.append(
            f"- {company['stock_code']} | {company['stock_name']} | "
            f"{company['industry_level_2'] or ''}/{company['industry_level_3'] or ''} | "
            f"{scope}"
        )

    financials = await db_tools.query_financial_data(
        session,
        [company["stock_code"] for company in companies[:_FINANCIAL_PREFETCH_COUNT]],
    )
    financial_lines = _format_financial_context(financials)

    news = await db_tools.search_news(session, industry, days=30, limit=10)
    news_lines = [
        f"- [{item['doc_type']}] {item['title']}" for item in news
    ]

    kb_docs = await db_tools.search_vector_kb(
        session, f"{industry} 主营业务 经营范围 产业链"
    )
    kb_lines = [
        f"- {item['title']}: {item['content'][:300]}" for item in kb_docs if item.get("title")
    ]

    sections = [
        "\n".join(context_lines),
        "财务指标（近一期）：\n" + "\n".join(financial_lines) if financial_lines else "",
        "近期行业动态：\n" + "\n".join(news_lines) if news_lines else "",
        "年报/研报摘录：\n" + "\n".join(kb_lines) if kb_lines else "",
    ]
    context = "\n\n".join(section for section in sections if section)

    user_prompt = PromptRenderer.render(
        prompt_config.user_prompt_template,
        industry=industry,
        focus=focus or "产业链上下游结构与投资价值",
        context=context,
    )

    output = await run_structured_agent(
        session,
        prompt_config=prompt_config,
        user_prompt=user_prompt,
        result_type=ChainAnalysisResult,
    )
    return await _validate(session, output)


async def run_skill(
    session: AsyncSession,
    params: dict[str, Any],
) -> ChainAnalysisResult:
    """Skill 统一入口。"""
    industry = params.get("industry", "")
    focus = params.get("focus")
    return await analyze_industry_chain(session, industry, focus)
