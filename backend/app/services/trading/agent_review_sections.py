"""多周期复盘报告专属板块契约（§4.2 统一框架 + 周期专属章节）。

板块清单的唯一真相源是 ``skills/trading-default/review_sections.yaml``：
``periods`` 声明各周期专属板块（key/title/撰写要求），``contract`` 是注入
user_prompt 的通用契约文本（指标口径/关键交易/经验沉淀）。所有 Agent 共用
（板块是报告契约，不是人设），per-agent 的 review_prompt.yaml 只管人设与
分层归因方法。

LLM 输出 ``sections`` 的 key 集合由 ``canonicalize_sections`` 确定性校验：
缺键/多键/重复键抛 ValueError（触发结构化输出重试）；标题由注册表覆盖，
防止各周期板块漂移。旧缓存行缺 ``sections`` 由 content 校验器补空值兼容。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.agent.core.prompt_loader import PromptSection
from app.core.config import get_settings
from app.services.trading.agent_review_periods import REVIEW_PERIODS, ReviewPeriod

#: 板块契约资产位置：始终取共享 trading-default（不随 per-agent 技能包分叉）
REVIEW_SECTIONS_SKILL_ID = "trading-default"
REVIEW_SECTIONS_FILE = "review_sections.yaml"


class ReviewSection(BaseModel):
    """报告专属板块（LLM 输出 + 持久化读模型共用）。"""

    key: str
    title: str
    body: str


class ReviewSectionsConfig(BaseModel):
    """板块契约 YAML 的装载形状。"""

    contract: str
    periods: dict[str, list[PromptSection]] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def load_review_sections() -> ReviewSectionsConfig:
    """装载板块契约（模块级缓存；测试可用 ``cache_clear()`` 重置）。"""
    path = (
        get_settings().skills_dir
        / REVIEW_SECTIONS_SKILL_ID
        / REVIEW_SECTIONS_FILE
    )
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = ReviewSectionsConfig(**data)
    missing = [period for period in REVIEW_PERIODS if not config.periods.get(period)]
    if missing:
        raise ValueError(f"复盘板块契约缺少周期定义：{'、'.join(missing)}")
    return config


def section_specs(period: ReviewPeriod) -> tuple[PromptSection, ...]:
    """指定周期的专属板块声明（按注册表顺序）。"""
    return tuple(load_review_sections().periods.get(period, ()))


def contract_text() -> str:
    """注入 user_prompt 的通用报告契约文本。"""
    return load_review_sections().contract.strip()


def render_section_instructions(period: ReviewPeriod) -> str:
    """把该周期的专属板块渲染为带序号的撰写指令。"""
    lines = ["本周期专属板块（sections 只能包含以下 key，按此顺序输出）："]
    for index, spec in enumerate(section_specs(period), start=1):
        lines.append(
            f"{index}. {spec.key}（{spec.title}）：{spec.requirements.strip()}"
        )
    return "\n".join(lines)


def canonicalize_sections(
    period: ReviewPeriod, sections: list[ReviewSection]
) -> list[ReviewSection]:
    """校验板块 key 集合并按注册表规范化标题与顺序。

    Raises:
        ValueError: 缺键、多键或重复键（结构化输出重试）。
    """
    specs = section_specs(period)
    expected = [spec.key for spec in specs]
    actual = [section.key for section in sections]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError(
            f"{period} 周期专属板块不符：期望 {expected}，实际 {actual}"
        )
    bodies = {section.key: section.body for section in sections}
    return [
        ReviewSection(key=spec.key, title=spec.title, body=bodies[spec.key])
        for spec in specs
    ]
