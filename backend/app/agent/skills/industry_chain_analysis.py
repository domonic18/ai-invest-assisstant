"""产业链分析 deepagents skill 执行器。

定时刷新（chain-refresh 任务）与 ``POST /chain/analyze`` 兼容入口共用本模块；
交互式产业链分析走 Skill 驱动的 Assistant Agent 工作流
（``skills/industry-chain-analysis/SKILL.md``），两者共享同一份 skill yaml。
独立执行器注入精简取数工具（公司清单/财务指标/新闻/研报摘录），agent 循环
取数后输出符合 ``ChainAnalysisResult`` 的 JSON，后置校验剔除幻觉代码与超限规模。
"""

from typing import Any

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.agent.runtime.model_factory import build_langchain_model
from app.agent.skills.skill_runtime import invoke_structured, load_skill_instructions
from app.agent.tools import db_tools, search_news, search_vector_kb
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.stock import StockBasic
from app.schemas.chain import ChainAnalysisResult
from app.services.admin.llm_config_service import resolve_default_llm

SKILL_ID = "industry-chain-analysis"

_MAX_NODES = 40
_MAX_COMPANIES_PER_NODE = 5
_MAX_ALERTS = 10
_COMPANY_SCOPE_MAX_CHARS = 120
_FINANCIAL_COMPANY_LIMIT = 40


@tool
async def get_industry_companies(
    industry: str, limit: int = 150
) -> list[dict[str, Any]]:
    """按行业名称查询上市公司清单，返回股票代码、名称、二级/三级行业、经营范围（已截断）。

    Args:
        industry: 行业名称，如 "半导体"。
        limit: 返回公司数上限，默认 150，最大 200。
    """
    limit = max(1, min(limit, 200))
    async with AsyncSessionLocal() as session:
        companies = await db_tools.query_industry_companies(session, industry, limit)
    for company in companies:
        scope = (company.get("business_scope") or "").replace("\n", " ").strip()
        if len(scope) > _COMPANY_SCOPE_MAX_CHARS:
            scope = scope[:_COMPANY_SCOPE_MAX_CHARS] + "…"
        company["business_scope"] = scope
    return companies


@tool
async def get_financial_metrics(stock_codes: list[str]) -> list[dict[str, Any]]:
    """批量查询公司核心财务指标：最新报告期毛利率、营收同比、研发占比、应收账款周转。

    Args:
        stock_codes: 6 位股票代码列表，单次最多 40 只（超出部分忽略）。
    """
    codes = stock_codes[:_FINANCIAL_COMPANY_LIMIT]
    async with AsyncSessionLocal() as session:
        return await db_tools.query_financial_data(session, codes)


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

    for node in result.nodes[:_MAX_NODES]:
        node.companies = [
            company
            for company in node.companies[:_MAX_COMPANIES_PER_NODE]
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

    cleaned_alerts = [alert for alert in result.alerts[:_MAX_ALERTS] if alert.title]
    for alert in cleaned_alerts:
        alert.severity = max(1, min(3, alert.severity))
        alert.affected_segments = [
            segment for segment in alert.affected_segments if segment in node_names
        ]
        alert.related_stock_codes = [
            code for code in alert.related_stock_codes if code in valid_codes
        ]
    result.alerts = cleaned_alerts
    return result


async def analyze_industry_chain(
    session: AsyncSession,
    industry: str,
    focus: str | None = None,
) -> ChainAnalysisResult:
    """执行产业链分析 Skill（deepagents agent 循环）。"""
    prompt_loader = PromptLoader(get_settings().prompts_dir)
    prompt_config = prompt_loader.load("skills", SKILL_ID)
    cfg = await resolve_default_llm(session)

    from deepagents import create_deep_agent

    agent = create_deep_agent(
        model=build_langchain_model(cfg),
        tools=[
            get_industry_companies,
            get_financial_metrics,
            search_news,
            search_vector_kb,
        ],
        system_prompt=(
            f"{prompt_config.system_prompt.strip()}\n\n{load_skill_instructions(SKILL_ID)}"
        ),
        name=SKILL_ID,
    )

    user_prompt = PromptRenderer.render(
        prompt_config.user_prompt_template,
        industry=industry,
        focus=focus or "产业链上下游结构与投资价值",
    )

    output = await invoke_structured(
        agent, user_prompt, ChainAnalysisResult, skill_id=SKILL_ID, industry=industry
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
