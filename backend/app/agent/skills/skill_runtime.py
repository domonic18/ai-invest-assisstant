"""deepagents 工具循环型 skill 的共享运行时。

个股每日分析与大盘每日复盘等 skill 的公共骨架：SKILL.md 指引加载、分区任务
指令渲染、agent 调用与最终 sections JSON 解析（失败自动重试一次）。输出契约
（分区 key）仍以各 skill 的 ``prompts/skills/<skill_id>.yaml`` 为真源。
"""

import json
import re
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from app.agent.core.prompt_loader import PromptSection
from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class SkillOutputError(ValueError):
    """skill 最终输出不是合法的 sections JSON（重试后仍失败）。"""


def load_skill_instructions(skill_id: str) -> str:
    """读取 SKILL.md 正文（剥离 YAML frontmatter）作为分析流程指引。"""
    path = get_settings().skills_dir / skill_id / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].strip()
    return text.strip()


def render_section_instructions(sections: list[PromptSection]) -> str:
    """把 YAML sections 声明渲染为带序号的分区撰写指令。"""
    lines = ["请输出以下分区（以分区 key 为字段名）："]
    for index, section in enumerate(sections, start=1):
        requirements = section.requirements.strip()
        lines.append(f"{index}. {section.key}（{section.title}）：{requirements}")
    return "\n".join(lines)


def message_text(content: Any) -> str:
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


def parse_sections(text: str, sections: list[PromptSection]) -> dict[str, str]:
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


async def invoke(agent: Any, prompt: str) -> str:
    """单次调用 deepagents agent 并提取最终回复文本。"""
    result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        raise SkillOutputError("agent 未返回任何消息")
    return message_text(messages[-1].content)


async def invoke_sections(
    agent: Any,
    prompt: str,
    sections: list[PromptSection],
    *,
    skill_id: str,
    **log_fields: Any,
) -> dict[str, str]:
    """调用 agent 并解析 sections JSON；解析/校验失败自动重试一次。"""
    text = await invoke(agent, prompt)
    try:
        return parse_sections(text, sections)
    except SkillOutputError as first_err:
        logger.warning(
            f"{skill_id.replace('-', '_')}_output_retry",
            skill_id=skill_id,
            error=str(first_err),
            **log_fields,
        )
        retry_prompt = (
            f"{prompt}\n\n【重试】上一次最终回复无法解析（{first_err}）。"
            "请直接输出最终 JSON 对象：仅含 sections 字段，键为声明的分区 key，"
            "值为 Markdown 字符串，不要任何其他文字。"
        )
        text = await invoke(agent, retry_prompt)
        return parse_sections(text, sections)
