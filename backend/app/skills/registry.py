"""builtin skill 注册表：skill 资产的唯一登记入口。

每个 builtin skill 是 ``skills/<skill_id>/`` 下的自包含目录（SKILL.md 方法论
文档 + prompt.yaml 提示词契约，二者按 skill_id 同名对齐）；本注册表声明各
skill 的能力与运行时绑定，收敛「目录名即 id」的隐式约定。

- ``executor`` 为执行器模块的字符串引用（服务层/采集层各自延迟导入，此处
  不导入 agent 代码，保证 services 与 agent 层均可顶层导入本包）
- ``task_spec_names`` 记录 collector ``TASK_SPECS`` 任务名映射（历史原因部分
  任务名与 skill_id 不同名，映射在此显式声明而非改名；一个 skill 可对应
  多个检测任务，如异动归因挂板块/个股两个检测任务）
- custom skill（用户创建）不走本表，见 DB ``skill`` 表（``is_builtin=False``）
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

SkillKind = Literal["executable", "prompt_only", "doc_only"]

# 业务场景分类（技能广场 Tab 的唯一真相源）；custom skill 固定为 'custom'
SkillScenario = Literal["market", "stock", "chain", "report", "news"]

SCENARIO_LABELS: dict[str, str] = {
    "market": "大盘与情绪",
    "stock": "个股分析",
    "chain": "产业链",
    "report": "财报与研报",
    "news": "资讯处理",
    "custom": "自定义",
}


@dataclass(frozen=True)
class SkillDescriptor:
    """builtin skill 描述符。"""

    skill_id: str
    label: str
    kind: SkillKind
    skill_md: bool
    scenario: SkillScenario
    executor: str | None = None
    task_spec_names: tuple[str, ...] = ()


BUILTIN_SKILLS: tuple[SkillDescriptor, ...] = (
    SkillDescriptor(
        skill_id="market-daily-review",
        label="大盘每日复盘",
        kind="executable",
        skill_md=True,
        scenario="market",
        executor="app.agent.skills.market_review_agent",
        task_spec_names=("market-daily-review",),
    ),
    SkillDescriptor(
        skill_id="limit-up-review",
        label="涨停归因",
        kind="executable",
        skill_md=True,
        scenario="market",
        executor="app.agent.skills.limit_up_review_agent",
        task_spec_names=("limit-up-ai-review",),
    ),
    SkillDescriptor(
        skill_id="anomaly-attribution",
        label="异动归因",
        kind="executable",
        skill_md=True,
        scenario="market",
        executor="app.agent.skills.anomaly_attribution_agent",
        task_spec_names=("sector-anomaly", "stock-anomaly"),
    ),
    SkillDescriptor(
        skill_id="stock-daily-analysis",
        label="个股每日分析",
        kind="executable",
        skill_md=True,
        scenario="stock",
        executor="app.agent.skills.stock_daily_analysis_agent",
        task_spec_names=("stock-daily-analysis",),
    ),
    SkillDescriptor(
        skill_id="industry-chain-analysis",
        label="产业链分析",
        kind="executable",
        skill_md=True,
        scenario="chain",
        executor="app.agent.skills.industry_chain_analysis",
        task_spec_names=("chain-refresh",),
    ),
    SkillDescriptor(
        skill_id="watchlist-screenshot-recognition",
        label="自选股截图识别",
        kind="executable",
        skill_md=True,
        scenario="stock",
        executor="app.agent.skills.watchlist_screenshot_recognition",
    ),
    SkillDescriptor(
        skill_id="research-report-summary",
        label="研报观点汇总",
        kind="prompt_only",
        skill_md=True,
        scenario="report",
    ),
    SkillDescriptor(
        skill_id="news-score",
        label="资讯重要度分级",
        kind="prompt_only",
        skill_md=True,
        scenario="news",
        task_spec_names=("news-score",),
    ),
    SkillDescriptor(
        skill_id="news-storyline",
        label="事件故事线建线",
        kind="prompt_only",
        skill_md=True,
        scenario="news",
        task_spec_names=("news-storyline",),
    ),
    SkillDescriptor(
        skill_id="news-topic",
        label="热点主题聚类",
        kind="prompt_only",
        skill_md=True,
        scenario="news",
        task_spec_names=("news-topic",),
    ),
    SkillDescriptor(
        skill_id="financial-report-summary",
        label="财报结构化摘要",
        kind="prompt_only",
        skill_md=True,
        scenario="report",
    ),
    SkillDescriptor(
        skill_id="chain-breakthrough",
        label="供应链突破检测",
        kind="doc_only",
        skill_md=True,
        scenario="chain",
    ),
    SkillDescriptor(
        skill_id="financial-health-check",
        label="个股财务体检",
        kind="doc_only",
        skill_md=True,
        scenario="stock",
    ),
    SkillDescriptor(
        skill_id="hotspot-detection",
        label="市场热点检测",
        kind="doc_only",
        skill_md=True,
        scenario="market",
    ),
)

_SKILL_INDEX: dict[str, SkillDescriptor] = {d.skill_id: d for d in BUILTIN_SKILLS}


def get_skill(skill_id: str) -> SkillDescriptor | None:
    """按 skill_id 取描述符；未登记返回 None。"""
    return _SKILL_INDEX.get(skill_id)


def iter_skills() -> Iterator[SkillDescriptor]:
    """按注册表顺序遍历全部 builtin skill。"""
    return iter(BUILTIN_SKILLS)


def builtin_skill_ids() -> frozenset[str]:
    """全部 builtin skill_id 集合（custom skill 创建时的保留字校验依据）。"""
    return frozenset(_SKILL_INDEX)
