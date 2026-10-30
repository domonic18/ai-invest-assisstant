"""复盘经验的周期口径（§4.6：长周期只沉淀体系级经验）。

日/周/月保留全部微观经验；季/半年/年只保留体系级条目（method/discipline
的迭代结论），避免长周期把日/周的微观教训再沉淀一遍。落库侧同标题由新结论
覆盖（见 ``agent_memory_service.sediment_experiences``）。
"""

from collections.abc import Sequence

from app.services.trading.agent_review_content import ReviewExperience
from app.services.trading.agent_review_periods import ReviewPeriod, is_long_period

#: 体系级经验类型（长周期沉淀白名单）
SYSTEM_LEVEL_MEM_TYPES = frozenset({"method", "discipline"})


def filter_period_experiences(
    period: ReviewPeriod, experiences: Sequence[ReviewExperience]
) -> list[ReviewExperience]:
    """按周期裁剪经验条目（长周期仅保留体系级）。"""
    if not is_long_period(period):
        return list(experiences)
    return [
        experience
        for experience in experiences
        if experience.mem_type in SYSTEM_LEVEL_MEM_TYPES
    ]
