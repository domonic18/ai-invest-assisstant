"""大盘每日复盘 deepagents skill 执行器。

分析流程与工具编排由 ``skills/market-daily-review/SKILL.md`` 声明（可直接
改该文件升级分析逻辑）；输出契约（分区 key）以
``prompts/skills/market-daily-review.yaml`` 为真源。共享执行骨架见
``app.agent.skills.skill_runtime``。
"""

import time
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig
from app.agent.runtime.model_factory import build_langchain_model
from app.agent.skills.skill_runtime import (
    invoke_sections,
    load_skill_instructions,
    render_section_instructions,
)
from app.services.admin.llm_config_service import resolve_default_llm

SKILL_ID = "market-daily-review"


async def run_skill(
    session: AsyncSession,
    *,
    trade_date: date,
    prompt_config: PromptConfig,
) -> tuple[dict[str, str], str, int]:
    """执行 deepagents 大盘复盘 skill。

    Args:
        session: 数据库会话（用于解析默认 LLM 配置）。
        trade_date: 交易日。
        prompt_config: YAML 输出契约（system_prompt/sections/任务模板）。

    Returns:
        (分区内容, model 标识, 耗时毫秒)。

    Raises:
        SkillOutputError: 重试一次后输出仍无法解析或分区缺失。
    """
    cfg = await resolve_default_llm(session)

    from deepagents import create_deep_agent

    from app.agent.tools import (
        get_index_technical,
        get_limit_up_ladder,
        get_market_overview,
        get_sector_overview,
    )

    agent = create_deep_agent(
        model=build_langchain_model(cfg),
        tools=[
            get_market_overview,
            get_limit_up_ladder,
            get_index_technical,
            get_sector_overview,
        ],
        system_prompt=(
            f"{prompt_config.system_prompt.strip()}\n\n{load_skill_instructions(SKILL_ID)}"
        ),
        name=SKILL_ID,
    )

    user_prompt = prompt_config.user_prompt_template.format(
        trade_date=trade_date.isoformat(),
        section_instructions=render_section_instructions(prompt_config.sections),
    )

    started = time.perf_counter()
    contents = await invoke_sections(
        agent, user_prompt, prompt_config.sections, skill_id=SKILL_ID
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    model_name = f"{cfg.provider}/{cfg.model_name}"
    return contents, model_name, latency_ms
