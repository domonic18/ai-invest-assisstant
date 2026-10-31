"""复盘只读查询面：读取已生成复盘、跨窗口对比、日历打点日期。"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.repositories.review import ai_analysis_repository
from app.services.trading.agent_review_cache import input_hash, load_cached
from app.services.trading.agent_review_content import (
    REVIEW_SKILL_ID,
    PaperTradeReviewRecord,
)
from app.services.trading.agent_review_errors import TradingReviewNotFoundError
from app.services.trading.agent_review_metrics import compute_window_metrics
from app.services.trading.agent_review_periods import ReviewPeriod, ReviewWindow
from app.services.trading.agent_review_window import (
    ReviewWindowRequest,
    resolve_requested_window,
)


async def get_review(
    session: AsyncSession,
    agent_key: str,
    request: ReviewWindowRequest,
) -> PaperTradeReviewRecord | None:
    """读取指定 Agent 已生成的复盘（不触发 LLM）。

    窗口入参与生成路径同口径（``ReviewWindowRequest``）。空仓无复盘对象的
    标记行（no_target_reason 非空）同样返回，由展示层区分。
    """
    from app.services.trading import account_service

    window = await resolve_requested_window(session, request)
    if window.is_empty:
        return None
    account = await account_service.resolve_agent_account(session, agent_key)
    row = await ai_analysis_repository.load_latest_success(
        session,
        skill_id=REVIEW_SKILL_ID,
        trade_date=window.end,
        input_hash=input_hash(
            agent_key, account.id, window.period, window.start, window.end
        ),
    )
    if row is None or not row.structured_output:
        return None
    return PaperTradeReviewRecord.model_validate(row.structured_output)


@dataclass(frozen=True)
class ReviewCompareResult:
    """跨窗口等比指标对比结果（metrics 为 wire 形状字典）。"""

    window_a: dict[str, Any]
    window_b: dict[str, Any]
    aligned_trading_days: int
    note: str


#: 对比视图可比性提示（§4.5：市场环境不同不能直接等同于策略优劣）
_COMPARE_NOTE = (
    "两窗口已按最近 {days} 个交易日等长对齐，指标同口径可复算；"
    "市场环境不同，差异不能直接等同于策略优劣。"
)


def _truncate_window(window: ReviewWindow, trading_days: int) -> ReviewWindow:
    """保留窗口最近 N 个交易日（等长对齐，§4.5）。"""
    days = window.trading_days[-trading_days:]
    return ReviewWindow(
        period=window.period,
        requested_start=days[0],
        requested_end=days[-1],
        start=days[0],
        end=days[-1],
        trading_days=days,
    )


def _window_text(window: ReviewWindow) -> str:
    return f"{window.start.isoformat()} 至 {window.end.isoformat()}"


async def compare_reviews(
    session: AsyncSession,
    agent_key: str,
    *,
    window_a: ReviewWindowRequest,
    window_b: ReviewWindowRequest,
) -> ReviewCompareResult:
    """两个已生成窗口按等长交易日对齐后重算指标并对比（§4.5）。

    对齐取两窗口较短的一方，各自截取**最近** N 个交易日重算（口径不变）。
    仅对比已完成生成的窗口：任一窗口未生成抛 ``TradingReviewNotFoundError``。

    Raises:
        BadRequestError: 窗口入参非法或区间内无交易日。
        TradingReviewNotFoundError: 任一窗口尚未生成复盘。
    """
    from app.services.trading import account_service

    resolved_a = await resolve_requested_window(session, window_a)
    resolved_b = await resolve_requested_window(session, window_b)
    if resolved_a.is_empty or resolved_b.is_empty:
        raise BadRequestError("对比窗口内没有交易日")

    account = await account_service.resolve_agent_account(session, agent_key)
    for window in (resolved_a, resolved_b):
        cached = await load_cached(
            session,
            input_hash(
                agent_key,
                account.id,
                window.period,
                window.start,
                window.end,
            ),
        )
        if cached is None:
            raise TradingReviewNotFoundError(
                f"{_window_text(window)} 的 {window.period} 复盘尚未生成，无法对比"
            )

    aligned = min(resolved_a.trading_day_count, resolved_b.trading_day_count)
    metrics_a = await compute_window_metrics(
        session,
        account_id=account.id,
        agent_key=agent_key,
        window=_truncate_window(resolved_a, aligned),
    )
    metrics_b = await compute_window_metrics(
        session,
        account_id=account.id,
        agent_key=agent_key,
        window=_truncate_window(resolved_b, aligned),
    )
    return ReviewCompareResult(
        window_a=metrics_a.to_dict(),
        window_b=metrics_b.to_dict(),
        aligned_trading_days=aligned,
        note=_COMPARE_NOTE.format(days=aligned),
    )


async def list_review_dates(
    session: AsyncSession, agent_key: str, *, period: ReviewPeriod
) -> list[date]:
    """指定 Agent 已生成该周期复盘的基准交易日（升序），日历打点用。"""
    return await ai_analysis_repository.list_success_trade_dates(
        session,
        skill_id=REVIEW_SKILL_ID,
        structured_filter={"period": period, "agent_key": agent_key},
    )
