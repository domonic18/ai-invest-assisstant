"""个股每日 AI 分析 deepagents skill 执行器。

分析流程与工具编排由 ``skills/stock-daily-analysis/SKILL.md`` 声明（可直接
改该文件升级分析逻辑）；输出契约（分区 key）以
``skills/stock-daily-analysis/prompt.yaml`` 为真源。共享执行骨架见
``app.agent.skills.skill_runtime``。
"""

import time
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig
from app.agent.runtime.model_factory import build_langchain_model
from app.agent.skills.kb_grounding import (
    SENTINEL_LINE,
    STOCK_REQUIRED,
    apply_sentinels,
    citation_gaps,
)
from app.agent.skills.skill_runtime import (
    invoke_sections,
    load_skill_instructions,
    load_skill_methodology,
    render_section_instructions,
)
from app.services.admin.llm_config_service import resolve_default_llm

logger = structlog.get_logger(__name__)

SKILL_ID = "stock-daily-analysis"


async def run_skill(
    session: AsyncSession,
    stock_code: str,
    *,
    trade_date: date,
    stock_name: str,
    prompt_config: PromptConfig,
) -> tuple[dict[str, str], str, int]:
    """执行 deepagents 个股分析 skill。

    Args:
        session: 数据库会话（用于解析默认 LLM 配置）。
        stock_code: 股票代码。
        trade_date: 交易日。
        stock_name: 股票名称（渲染任务指令）。
        prompt_config: YAML 输出契约（system_prompt/sections/任务模板）。

    Returns:
        (分区内容, model 标识, 耗时毫秒)。

    Raises:
        SkillOutputError: 重试一次后输出仍无法解析或分区缺失。
    """
    cfg = await resolve_default_llm(session)

    from deepagents import create_deep_agent

    from app.agent.tools import (
        get_stock_emotion_context,
        get_stock_kline,
        get_stock_quote,
        get_stock_technical,
        query_financial_data,
        search_knowledge_base,
        search_news,
    )

    agent = create_deep_agent(
        model=build_langchain_model(cfg),
        tools=[
            get_stock_quote,
            get_stock_kline,
            get_stock_technical,
            get_stock_emotion_context,
            query_financial_data,
            search_news,
            search_knowledge_base,
        ],
        system_prompt=(
            f"{prompt_config.system_prompt.strip()}\n\n{load_skill_instructions(SKILL_ID)}"
            f"\n\n{load_skill_methodology(SKILL_ID)}"
        ),
        name=SKILL_ID,
    )

    user_prompt = prompt_config.user_prompt_template.format(
        stock_name=stock_name,
        stock_code=stock_code,
        trade_date=trade_date.isoformat(),
        section_instructions=render_section_instructions(prompt_config.sections),
    )

    started = time.perf_counter()
    contents = await invoke_sections(
        agent,
        user_prompt,
        prompt_config.sections,
        skill_id=SKILL_ID,
        stock_code=stock_code,
    )

    # 引用契约：必需分区须含 citation 或弃权声明；缺则补提示重跑一次，
    # 仍缺则 fail-soft 落弃权声明（不阻塞个股分析主链路）
    declared = {section.key for section in prompt_config.sections}
    required = tuple(key for key in STOCK_REQUIRED if key in declared)
    gaps = citation_gaps(contents, required)
    if gaps:
        logger.warning(
            "stock_analysis_citation_retry", gaps=list(gaps), stock_code=stock_code
        )
        retry_prompt = (
            f"{user_prompt}\n\n【补充提示】以下分区未引用方法论资料且未声明"
            f"无适用方法论：{'、'.join(gaps)}。请修正这些分区：引用方法论"
            "（手册条目或知识库检索卡片）时原样保留《趋势理论》第N集 "
            f"MM:SS（章节）定位；确无适用方法论时在分区末尾另起一行输出："
            f"{SENTINEL_LINE}"
        )
        contents = await invoke_sections(
            agent,
            retry_prompt,
            prompt_config.sections,
            skill_id=SKILL_ID,
            stock_code=stock_code,
        )
        gaps = citation_gaps(contents, required)
        if gaps:
            contents = apply_sentinels(contents, gaps)
            logger.warning(
                "stock_analysis_citation_gap", gaps=list(gaps), stock_code=stock_code
            )

    latency_ms = int((time.perf_counter() - started) * 1000)
    model_name = f"{cfg.provider}/{cfg.model_name}"
    return contents, model_name, latency_ms
