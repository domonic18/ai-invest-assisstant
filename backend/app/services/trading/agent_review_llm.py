"""复盘 LLM 调用面：per-agent 契约装载、人设段渲染、结构化生成与后置校验。

与生成编排解耦：``generate`` 只关心步骤顺序与落库，提示词装配与幻觉
剔除集中在本模块，便于单测直接验证 prompt 契约。
"""

import json
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper_trade import TradingAgent
from app.services.trading.agent_review_content import (
    PaperTradeReviewContent,
    PaperTradeReviewDraft,
)
from app.services.trading.agent_review_periods import ReviewPeriod
from app.services.trading.agent_review_sections import (
    contract_text,
    render_section_instructions,
)

#: per-agent 技能包复盘契约文件名（D34 skill 化）
_REVIEW_PROMPT_FILE = "review_prompt.yaml"


def review_prompt_skill_id(agent_key: str) -> str:
    """Agent 复盘契约技能包：``skills/trading-<agent_key>/review_prompt.yaml``
    专属作业程序，未建目录时回退共享 ``trading-default``（镜像 plan_skill_id）。"""
    from app.skills import get_skill

    specific = f"trading-{agent_key}"
    return specific if get_skill(specific) is not None else "trading-default"


async def run_review_llm(
    session: AsyncSession,
    agent: TradingAgent,
    period: ReviewPeriod,
    trade_date: date,
    window_input: dict[str, Any],
    *,
    meta_out: dict[str, Any] | None = None,
    prompt_out: dict[str, str] | None = None,
) -> PaperTradeReviewContent:
    """渲染复盘 prompt 并执行结构化生成。"""
    from app.skills import load_named_skill_prompt

    config = load_named_skill_prompt(
        review_prompt_skill_id(agent.agent_key), _REVIEW_PROMPT_FILE
    )
    # 人设段空值行跳过（D30：新建 Agent 仅填名称即可）
    identity = f"- 你是{agent.name}" + (f"（{agent.tagline}）" if agent.tagline else "")
    persona_lines = [identity, "- 以该人设的视角与风格生成分层复盘结论"]
    user_prompt = (
        f"{config.system_prompt}\n\n"
        f"## 复盘人设（注册表行，D27/D34）\n"
        + "\n".join(persona_lines)
        + "\n\n"
        f"## 复盘任务\n"
        f"- 周期 period：{period}\n"
        f"- 基准交易日 trade_date：{trade_date.isoformat()}（输出字段须原样带回）\n\n"
        f"{contract_text()}\n\n"
        f"{render_section_instructions(period)}\n\n"
        f"## 复盘输入数据（JSON：agent 账户本地委托/成交/资金快照 + metrics "
        f"系统指标 + market_review 盘面语境 + methodology 方法论基座）\n"
        f"{json.dumps(window_input, ensure_ascii=False, default=str)}"
    )
    if prompt_out is not None:
        prompt_out["prompt"] = user_prompt
    from app.agent.runtime.structured import run_structured

    return await run_structured(
        session,
        result_type=PaperTradeReviewDraft,
        user_prompt=user_prompt,
        config_id=agent.llm_config_id,
        meta_out=meta_out,
    )


def validate_review_trades(
    content: PaperTradeReviewContent, valid_cl_ord_ids: set[str]
) -> PaperTradeReviewContent:
    """后置校验：trades.cl_ord_id 必须来自窗口内真实委托（剔除幻觉行）。"""
    trades = [t for t in content.trades if t.cl_ord_id in valid_cl_ord_ids]
    return content.model_copy(update={"trades": trades})
