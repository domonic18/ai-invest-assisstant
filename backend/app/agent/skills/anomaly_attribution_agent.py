"""异动 AI 归因 deepagents skill 执行器（板块 / 个股双域）。

分析流程与证据工具编排由 ``skills/anomaly-attribution/SKILL.md`` 声明；
输出契约（category + summary 批量清单）以
``anomaly_attribution_service`` 的内容模型为真源。共享执行骨架见
``app.agent.skills.skill_runtime``。
"""

import json
import time
from datetime import date
from typing import Any

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig
from app.agent.runtime.model_factory import build_langchain_model
from app.agent.skills.skill_runtime import invoke_structured, load_skill_instructions
from app.services.admin.llm_config_service import resolve_default_llm
from app.services.market.anomaly_attribution_service import (
    SECTOR_CATEGORIES,
    SKILL_ID,
    STOCK_CATEGORIES,
    SectorAnomalyAttributionContent,
    StockAnomalyAttributionContent,
)

# 域 → 证据工具与取数提示（写进 user prompt 的取数建议段）
_EVIDENCE_TOOLS: dict[str, tuple[str, ...]] = {
    "sector": ("get_sector_fund_flow", "search_news_by_date", "search_news"),
    "stock": (
        "get_dragon_tiger",
        "get_stock_fund_flow",
        "search_news_by_date",
        "search_news",
    ),
}
_EVIDENCE_HINTS: dict[str, str] = {
    "sector": (
        '先调 get_sector_fund_flow(sector_type="industry", days=5, top=10) '
        "核实主力资金流向，再调 search_news_by_date 取近两日新闻"
    ),
    "stock": (
        "对上榜/高换手个股调 get_dragon_tiger(stock_code=...) 与 "
        "get_stock_fund_flow(stock_code=..., days=5) 核实龙虎榜与主力资金，"
        "再调 search_news_by_date 取近两日新闻"
    ),
}


async def run_skill(
    session: AsyncSession,
    *,
    domain: str,
    trade_date: date,
    targets: list[dict[str, Any]],
    prompt_config: PromptConfig,
) -> tuple[Any, str, int]:
    """执行异动归因 skill（单次调用覆盖全部输入标的）。

    Args:
        session: 数据库会话（用于解析默认 LLM 配置）。
        domain: 归因域，"sector" 或 "stock"。
        trade_date: 交易日。
        targets: 规则事实清单（服务层投影，含 rule_category）。
        prompt_config: YAML 契约（system_prompt/任务模板）。

    Returns:
        (归因内容, model 标识, 耗时毫秒)。

    Raises:
        SkillOutputError: 重试一次后输出仍无法解析或不符合 schema。
    """
    cfg = await resolve_default_llm(session)
    result_type = (
        SectorAnomalyAttributionContent
        if domain == "sector"
        else StockAnomalyAttributionContent
    )

    from deepagents import create_deep_agent

    from app.agent.tools import (
        get_dragon_tiger,
        get_sector_fund_flow,
        get_stock_fund_flow,
        search_news,
        search_news_by_date,
    )

    tool_map: dict[str, BaseTool] = {
        "get_dragon_tiger": get_dragon_tiger,
        "get_sector_fund_flow": get_sector_fund_flow,
        "get_stock_fund_flow": get_stock_fund_flow,
        "search_news": search_news,
        "search_news_by_date": search_news_by_date,
    }
    allowed = (
        ",".join(sorted(SECTOR_CATEGORIES))
        if domain == "sector"
        else ",".join(sorted(STOCK_CATEGORIES))
    )

    agent = create_deep_agent(
        model=build_langchain_model(cfg),
        tools=[tool_map[name] for name in _EVIDENCE_TOOLS[domain]],
        system_prompt=(
            f"{prompt_config.system_prompt.strip()}\n\n{load_skill_instructions(SKILL_ID)}"
        ),
        name=SKILL_ID,
    )

    user_prompt = prompt_config.user_prompt_template.format(
        trade_date=trade_date.isoformat(),
        domain_label="板块" if domain == "sector" else "个股",
        target_count=len(targets),
        targets_json=json.dumps(targets, ensure_ascii=False),
        evidence_hint=_EVIDENCE_HINTS[domain],
        categories=allowed,
    )

    started = time.perf_counter()
    content = await invoke_structured(
        agent,
        user_prompt,
        result_type,
        skill_id=SKILL_ID,
        domain=domain,
        trade_date=trade_date.isoformat(),
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    model_name = f"{cfg.provider}/{cfg.model_name}"
    return content, model_name, latency_ms
