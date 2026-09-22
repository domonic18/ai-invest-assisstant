"""复盘技能 KB 引用契约（grounding）纯函数校验。

蒸馏手册架构的机械校验层：KB 必需分区须含 citation（《来源》+集数/页码/
时间码定位）或显式声明无适用方法论（``SENTINEL_LINE``），防止模型编造引用
或静默忽略方法论。缺口处置（补提示重试一次后 fail-soft 落弃权声明）由各
技能执行器/落库工具编排，本模块无 IO。
"""

import re

# 分区末尾弃权声明：模型显式声明该分区无适用方法论（blockquote 行，与分区
# Markdown 格式一致，前端按普通引用块渲染）
SENTINEL_LINE = "> 知识库佐证：无适用方法论"

# 匹配知识卡片 citation 定位串：`《标题》…第N集/第N-M页`、`《标题》…MM:SS`
# 或 `MM:SS-MM:SS`（书名与定位词之间的间隔不含句号/换行）。同时覆盖
# search_knowledge_base 工具返回与蒸馏手册条目的引用格式。
CITATION_RE = re.compile(
    r"《[^《》\n]{1,80}》[^。\n]{0,40}?"
    r"(?:第\d+(?:-\d+)?[集页]|\d{1,2}:\d{2}(?::\d{2})?(?:-\d{1,2}:\d{2}(?::\d{2})?)?)"
)

MARKET_REQUIRED = ("technical_analysis", "risk_advice")
STOCK_REQUIRED = ("technical_analysis", "strategy", "risk_lines")


def citation_gaps(
    contents: dict[str, str], required: tuple[str, ...]
) -> list[str]:
    """返回既无 citation 也未声明弃权的必需分区 key（按 required 顺序）。"""
    gaps: list[str] = []
    for key in required:
        text = contents.get(key, "")
        if CITATION_RE.search(text) or SENTINEL_LINE in text:
            continue
        gaps.append(key)
    return gaps


def apply_sentinels(
    contents: dict[str, str], gaps: list[str]
) -> dict[str, str]:
    """为缺口分区尾部补弃权声明（返回新 dict；空分区直接填弃权行）。"""
    out = dict(contents)
    for key in gaps:
        text = out.get(key, "").rstrip()
        out[key] = f"{text}\n\n{SENTINEL_LINE}" if text else SENTINEL_LINE
    return out


def warning_lines(gaps: list[str]) -> list[str]:
    """落库工具返回值携带的 warning 文案（fail-soft 告知助手补救）。"""
    return [f"分区 {key} 未引用知识库且未声明无适用方法论" for key in gaps]
