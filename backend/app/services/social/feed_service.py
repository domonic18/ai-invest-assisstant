"""情绪流读服务（资讯中心第四 Tab：feed / 账号卡 / 单账号时间线 + 复盘情绪输入）。"""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.social import post_repository
from app.schemas.social import (
    SocialAccountCardResponse,
    SocialAccountsResponse,
    SocialFeedItemResponse,
    SocialFeedResponse,
    SocialTimelineItemResponse,
    SocialTimelineResponse,
)


async def get_feed(
    session: AsyncSession,
    *,
    category: str | None = None,
    stance: str | None = None,
    hours: int | None = None,
    strong_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> SocialFeedResponse:
    """情绪流：已判相关内容分页（新内容优先）。"""
    items, total = await post_repository.list_feed(
        session,
        category=category,
        stance=stance,
        hours=hours,
        strong_only=strong_only,
        page=page,
        page_size=page_size,
    )
    return SocialFeedResponse(
        items=[SocialFeedItemResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_account_cards(
    session: AsyncSession, *, hours: int | None = 168
) -> SocialAccountsResponse:
    """账号维度卡（统计窗口内多空分布与按日时序 + 最新判断）。"""
    cards = await post_repository.list_account_cards(session, hours=hours)
    return SocialAccountsResponse(
        accounts=[SocialAccountCardResponse.model_validate(card) for card in cards]
    )


async def get_timeline(
    session: AsyncSession, account_id: int, *, page: int = 1, page_size: int = 20
) -> SocialTimelineResponse:
    """单账号已判内容时间线（立场轨迹由前端按序派生）。"""
    items, total = await post_repository.list_timeline(
        session, account_id, page=page, page_size=page_size
    )
    return SocialTimelineResponse(
        items=[SocialTimelineItemResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


_REVIEW_MIN_SAMPLE = 3  # 当日判定低于该条数视为样本不足，反向指标不作数


async def get_review_sentiment(
    session: AsyncSession, trade_date: date
) -> dict[str, Any]:
    """复盘情绪面输入：当日散户情绪分布、近 7 日净多空走势与代表观点。

    当日判定条数低于 ``_REVIEW_MIN_SAMPLE`` 时附 ``sample_insufficient``
    标记并在 note 中如实说明，提示下游反向指标解读不足为凭。
    """
    daily = await post_repository.daily_stance_overview(session, trade_date, days=7)
    counts = daily.get(trade_date, {})
    bullish = counts.get("bullish", 0)
    bearish = counts.get("bearish", 0)
    neutral = counts.get("neutral", 0)
    total = bullish + bearish + neutral

    trend = [
        {
            "date": day.isoformat(),
            "bullish": day_counts.get("bullish", 0),
            "bearish": day_counts.get("bearish", 0),
            "net_bullish": day_counts.get("bullish", 0) - day_counts.get("bearish", 0),
        }
        for day, day_counts in sorted(daily.items())
    ]
    top = await post_repository.top_stances(session, trade_date)
    active_accounts = await post_repository.count_day_active_accounts(
        session, trade_date
    )

    insufficient = total < _REVIEW_MIN_SAMPLE
    note = (
        f"当日有效判定仅 {total} 条（活跃账号 {active_accounts} 个），样本不足，"
        "情绪结论不足为凭，应与其他维度互证或如实披露。"
        if insufficient
        else f"当日有效判定 {total} 条（看多 {bullish}/看空 {bearish}/中性 {neutral}，"
        f"活跃账号 {active_accounts} 个）。散户情绪作反向指标解读："
        "显著净看多且升温=风险积聚，净看空/冰点=机会大于风险。"
    )
    return {
        "trade_date": trade_date.isoformat(),
        "counts": {"bullish": bullish, "bearish": bearish, "neutral": neutral},
        "net_bullish": bullish - bearish,
        "total": total,
        "active_accounts": active_accounts,
        "daily_trend": trend,
        "top_stances": top,
        "sample_insufficient": insufficient,
        "note": note,
    }
