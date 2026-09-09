"""涨停 AI 归因 deepagents skill 执行器。

分析流程与工具编排由 ``skills/limit-up-review/SKILL.md`` 声明（可直接改该文件
升级分析逻辑）；输出契约（groups/stock_themes）以 ``LimitUpAttributionContent``
模型为真源，SKILL.md 的「输出 Schema」与其保持一致。共享执行骨架见
``app.agent.skills.skill_runtime``。
"""

import time
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig
from app.agent.runtime.model_factory import build_langchain_model
from app.agent.skills.skill_runtime import invoke_structured, load_skill_instructions
from app.services.admin.llm_config_service import resolve_default_llm
from app.services.review.limit_up_ai_service import LimitUpAttributionContent

SKILL_ID = "limit-up-review"


async def run_skill(
    session: AsyncSession,
    *,
    trade_date: date,
    pool_count: int,
    prompt_config: PromptConfig,
) -> tuple[LimitUpAttributionContent, str, int]:
    """执行 deepagents 涨停归因 skill。

    Args:
        session: 数据库会话（用于解析默认 LLM 配置）。
        trade_date: 交易日。
        pool_count: 当日涨停家数（服务层已预取涨停池用于就绪预检与后置校验）。
        prompt_config: YAML 契约（system_prompt/任务模板）。

    Returns:
        (归因内容, model 标识, 耗时毫秒)。

    Raises:
        SkillOutputError: 重试一次后输出仍无法解析或不符合 schema。
    """
    cfg = await resolve_default_llm(session)

    from deepagents import create_deep_agent

    from app.agent.tools import (
        get_limit_up_pool,
        get_sector_overview,
        search_news_by_date,
    )

    agent = create_deep_agent(
        model=build_langchain_model(cfg),
        tools=[get_limit_up_pool, get_sector_overview, search_news_by_date],
        system_prompt=(
            f"{prompt_config.system_prompt.strip()}\n\n{load_skill_instructions(SKILL_ID)}"
        ),
        name=SKILL_ID,
    )

    user_prompt = prompt_config.user_prompt_template.format(
        trade_date=trade_date.isoformat(),
        pool_count=pool_count,
    )

    started = time.perf_counter()
    content = await invoke_structured(
        agent,
        user_prompt,
        LimitUpAttributionContent,
        skill_id=SKILL_ID,
        trade_date=trade_date.isoformat(),
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    model_name = f"{cfg.provider}/{cfg.model_name}"
    return content, model_name, latency_ms
