"""CME FedWatch 官方概率快照的派生聚合服务。

无算法假设：hike/hold/cut 分别是高于/等于/低于当前目标区间的概率求和，
最可能区间取该会议概率最大的落位区间。
"""

from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fed_watch import FedWatchProbability
from app.repositories.market import fed_watch_repository
from app.schemas.market import FedWatchMeeting, FedWatchResponse

logger = structlog.get_logger(__name__)

# 官网概率四舍五入到 0.1%，会议内求和容差
_PROB_SUM_TOLERANCE = 0.5


def derive_meetings(
    probabilities: list[FedWatchProbability], current_low: int, current_high: int
) -> list[FedWatchMeeting]:
    """按会议聚合概率行 → hike/hold/cut 求和与最可能区间（升序）。

    概率和异常（官网数据截断/结构变化）的会议跳过并告警，不中断整体。
    """
    by_meeting: dict[date, list[FedWatchProbability]] = {}
    for row in probabilities:
        by_meeting.setdefault(row.meeting_date, []).append(row)

    meetings: list[FedWatchMeeting] = []
    for meeting_date in sorted(by_meeting):
        rows = by_meeting[meeting_date]
        total = float(sum(row.probability for row in rows))
        if abs(total - 100) > _PROB_SUM_TOLERANCE:
            logger.warning(
                "fed_watch_prob_sum_abnormal",
                meeting_date=meeting_date.isoformat(),
                total=float(total),
            )
            continue
        likely = max(rows, key=lambda r: r.probability)
        meetings.append(
            FedWatchMeeting(
                meeting_date=meeting_date,
                prob_hike=float(
                    sum(r.probability for r in rows if r.range_low >= current_high)
                ),
                prob_hold=float(
                    sum(
                        r.probability
                        for r in rows
                        if r.range_low == current_low and r.range_high == current_high
                    )
                ),
                prob_cut=float(
                    sum(r.probability for r in rows if r.range_high <= current_low)
                ),
                likely_range_low=likely.range_low,
                likely_range_high=likely.range_high,
            )
        )
    return meetings


async def get_fed_watch(session: AsyncSession) -> FedWatchResponse | None:
    """最新快照 + 概率分布 → 各会议 hike/hold/cut 派生视图；无数据返回 None。"""
    snapshot = await fed_watch_repository.get_latest_snapshot(session)
    if snapshot is None:
        return None
    probabilities = await fed_watch_repository.list_probabilities(
        session, snapshot.as_of_date
    )
    meetings = derive_meetings(
        probabilities, snapshot.current_range_low, snapshot.current_range_high
    )
    return FedWatchResponse(
        as_of=snapshot.as_of_date,
        data_as_at=snapshot.data_as_at,
        current_range_low=snapshot.current_range_low,
        current_range_high=snapshot.current_range_high,
        meetings=meetings,
    )
