"""个股每日 AI 分析 deepagents skill 执行器。

分析流程与工具编排由 ``skills/stock-daily-analysis/SKILL.md`` 声明（可直接
改该文件升级分析逻辑）；输出契约（分区 key）以
``prompts/skills/stock-daily-analysis.yaml`` 为真源。

deepagents 无原生结构化输出：system prompt 强制最终回复为 JSON，
解析/校验失败重试一次，仍失败抛 :class:`SkillOutputError`。
"""

import json
import re
import time
from datetime import date
from typing import Any

import structlog
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptConfig, PromptSection
from app.agent.runtime.model_factory import build_langchain_model
from app.core.config import get_settings
from app.services.admin.llm_config_service import resolve_default_llm

logger = structlog.get_logger(__name__)

SKILL_ID = "stock-daily-analysis"


class SkillOutputError(ValueError):
    """skill 最终输出不是合法的 sections JSON（重试后仍失败）。"""


def load_skill_instructions() -> str:
    """读取 SKILL.md 正文（剥离 YAML frontmatter）作为分析流程指引。"""
    path = get_settings().skills_dir / SKILL_ID / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].strip()
    return text.strip()


def render_section_instructions(sections: list[PromptSection]) -> str:
    lines = ["请输出以下分区（以分区 key 为字段名）："]
    for index, section in enumerate(sections, start=1):
        requirements = section.requirements.strip()
        lines.append(f"{index}. {section.key}（{section.title}）：{requirements}")
    return "\n".join(lines)


def _message_text(content: Any) -> str:
    """提取最终消息文本（兼容 str 与多块 content 结构）。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def _parse_sections(text: str, sections: list[PromptSection]) -> dict[str, str]:
    """从最终回复提取 sections JSON 并校验分区键齐整。"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise SkillOutputError("输出中未找到 JSON 对象")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise SkillOutputError(f"JSON 解析失败：{exc}") from exc
    raw = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        raise SkillOutputError("JSON 缺少 sections 对象")
    missing = [s.key for s in sections if not isinstance(raw.get(s.key), str)]
    if missing:
        raise SkillOutputError(f"缺少分区或分区非字符串：{', '.join(missing)}")
    return {s.key: raw[s.key] for s in sections}


async def _invoke(agent: Any, prompt: str) -> str:
    result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        raise SkillOutputError("agent 未返回任何消息")
    return _message_text(messages[-1].content)


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
        get_stock_kline,
        get_stock_quote,
        query_financial_data,
        search_news,
    )

    agent = create_deep_agent(
        model=build_langchain_model(cfg),
        tools=[get_stock_quote, get_stock_kline, query_financial_data, search_news],
        system_prompt=(
            f"{prompt_config.system_prompt.strip()}\n\n{load_skill_instructions()}"
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
    text = await _invoke(agent, user_prompt)
    try:
        contents = _parse_sections(text, prompt_config.sections)
    except SkillOutputError as first_err:
        logger.warning(
            "stock_daily_analysis_output_retry",
            stock_code=stock_code,
            error=str(first_err),
        )
        retry_prompt = (
            f"{user_prompt}\n\n【重试】上一次最终回复无法解析（{first_err}）。"
            "请直接输出最终 JSON 对象：仅含 sections 字段，键为声明的分区 key，"
            "值为 Markdown 字符串，不要任何其他文字。"
        )
        text = await _invoke(agent, retry_prompt)
        contents = _parse_sections(text, prompt_config.sections)

    latency_ms = int((time.perf_counter() - started) * 1000)
    model_name = f"{cfg.provider}/{cfg.model_name}"
    return contents, model_name, latency_ms
