"""Industry chain analysis skill execution."""

from typing import Any, cast

from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.llm_router import build_agent
from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.agent.tools import db_tools
from app.core.config import get_settings
from app.schemas.chain import ChainAnalysisResult
from app.services.llm_config_service import resolve_default_llm


async def analyze_industry_chain(
    session: AsyncSession,
    industry: str,
    focus: str | None = None,
) -> ChainAnalysisResult:
    """执行产业链分析 Skill。"""
    prompt_loader = PromptLoader(get_settings().prompts_dir)
    prompt_config = prompt_loader.load("skills", "industry-chain-analysis")

    companies = await db_tools.query_industry_companies(session, industry, limit=20)
    context_lines = [f"行业：{industry}，共找到 {len(companies)} 家上市公司"]
    for company in companies[:10]:
        context_lines.append(
            f"- {company['stock_code']} {company['stock_name']} "
            f"({company['market']}) {company['industry_l2']} / {company['industry_l3']}"
        )

    kline_context = []
    for company in companies[:5]:
        kline = await db_tools.query_stock_kline(session, company["stock_code"], limit=5)
        if kline:
            latest = kline[0]
            kline_context.append(
                f"{company['stock_code']} {company['stock_name']}: "
                f"最新收盘价 {latest['close']}, 涨跌幅 {latest['pct_change']}%"
            )

    context = "\n".join(context_lines + [""] + kline_context)
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
    return cast(ChainAnalysisResult, result.output)


async def run_skill(
    session: AsyncSession,
    params: dict[str, Any],
) -> ChainAnalysisResult:
    """Skill 统一入口。"""
    industry = params.get("industry", "")
    focus = params.get("focus")
    return await analyze_industry_chain(session, industry, focus)
