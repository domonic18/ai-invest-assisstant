"""复盘窗口入参：统一校验、日历收边与派发前预检（四入口共用）。

窗口三形态（本期 / 上期 / 自定义区间）的结构校验集中在
``ReviewWindowRequest.from_values``（周期词表、区间成对与顺序、作用域），
交易日历收边与显式交易日合法性由 ``resolve_requested_window`` 负责。
Admin API、service、采集器与 Agent 工具只构造请求对象，不再各自复制规则。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PAPER_TRADE_SYNC_CUTOFF
from app.core.exceptions import BadRequestError
from app.models.paper_trade import TradingAgent
from app.services.trading.agent_review_errors import ReviewWindowNotReadyError
from app.services.trading.agent_review_inputs import sync_landed
from app.services.trading.agent_review_periods import (
    REVIEW_PERIODS,
    ReviewPeriod,
    ReviewWindow,
    period_bounds,
    resolve_custom_window,
    resolve_explicit_window,
    resolve_previous_window,
    resolve_review_window,
)

#: 快捷项作用域：current=本期（周期至今）/ previous=上一完整周期
ReviewWindowScope = Literal["current", "previous"]

#: 作用域运行时白名单（Literal 不可迭代）：MCP 等外部入口校验共用
REVIEW_WINDOW_SCOPES: tuple[ReviewWindowScope, ...] = ("current", "previous")

#: 未显式指定作用域时的默认值
DEFAULT_REVIEW_SCOPE: ReviewWindowScope = "current"

#: 缺少周期与区间时的统一文案（结构校验与防御式契约共用）
_MISSING_PERIOD_MESSAGE = "缺少复盘周期：请提供 period 或自定义区间"

#: 盘后同步未落库提示；手动路径附引导（定时路径由 Celery 退避重试，不加引导）
_SYNC_PENDING_MESSAGE = (
    "{day} 盘后同步（" + PAPER_TRADE_SYNC_CUTOFF + "）尚未落库，复盘输入未就绪"
)
_MANUAL_SYNC_HINT = "；请改用「上期」或历史区间，或 " + PAPER_TRADE_SYNC_CUTOFF + " 后再试"


def sync_pending_message(day: date, *, manual: bool) -> str:
    """盘后同步未落库的统一文案（手动路径附改用上期/历史区间的引导）。"""
    message = _SYNC_PENDING_MESSAGE.format(day=day.isoformat())
    return message + _MANUAL_SYNC_HINT if manual else message


@dataclass(frozen=True)
class ReviewWindowRequest:
    """读/生成/对比/派发共用的窗口入参。"""

    period: ReviewPeriod | None = None
    trade_date: date | None = None
    scope: ReviewWindowScope = DEFAULT_REVIEW_SCOPE
    start_date: date | None = None
    end_date: date | None = None

    @classmethod
    def from_values(
        cls,
        *,
        period: str | None = None,
        trade_date: date | None = None,
        scope: str = DEFAULT_REVIEW_SCOPE,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ReviewWindowRequest:
        """把原始入参收敛为合法请求对象。

        Raises:
            BadRequestError: 周期不在六档词表、作用域非法、区间不成对/倒置，
                或既无周期也无区间。
        """
        if period is not None and period not in REVIEW_PERIODS:
            raise BadRequestError(f"未知复盘周期：{period}")
        if scope not in REVIEW_WINDOW_SCOPES:
            raise BadRequestError(f"未知复盘作用域：{scope}")
        if (start_date is None) != (end_date is None):
            raise BadRequestError("自定义区间须同时提供开始日与结束日")
        if start_date is not None and end_date is not None:
            if end_date < start_date:
                raise BadRequestError(
                    f"区间结束日 {end_date.isoformat()} 早于开始日 "
                    f"{start_date.isoformat()}"
                )
        elif period is None:
            raise BadRequestError(_MISSING_PERIOD_MESSAGE)
        return cls(
            period=cast(ReviewPeriod | None, period),
            trade_date=trade_date,
            scope=cast(ReviewWindowScope, scope),
            start_date=start_date,
            end_date=end_date,
        )


def resolve_window(period: ReviewPeriod, trade_date: date) -> tuple[date, date]:
    """按周期解析本期窗口（周期首日 → 基准日），未按交易日历收边。"""
    return period_bounds(period, trade_date)


async def resolve_requested_window(
    session: AsyncSession, request: ReviewWindowRequest
) -> ReviewWindow:
    """把请求入参解析为已收边的复盘窗口。

    显式区间为空（区间内无交易日）抛 ``BadRequestError``；快捷项为空窗口
    原样返回由调用方按「未生成」处理。显式交易日须为交易日。

    Raises:
        BadRequestError: 显式区间内没有交易日。
        NonTradingDayError: 显式交易日不是交易日。
    """
    from app.services.market import trade_calendar_service
    from app.services.market.trade_calendar_service import NonTradingDayError

    if request.start_date is not None and request.end_date is not None:
        window = (
            await resolve_custom_window(
                session, request.start_date, request.end_date
            )
            if request.period is None
            else await resolve_explicit_window(
                session, request.period, request.start_date, request.end_date
            )
        )
        if window.is_empty:
            raise BadRequestError(
                f"{request.start_date.isoformat()} 至 "
                f"{request.end_date.isoformat()} 区间内没有交易日"
            )
        return window

    if request.period is None:  # from_values 已拦截；保持防御式契约
        raise BadRequestError(_MISSING_PERIOD_MESSAGE)
    if request.trade_date is not None:
        if not await trade_calendar_service.is_trading_day(
            session, request.trade_date
        ):
            raise NonTradingDayError(
                f"{request.trade_date.isoformat()} 不是交易日，复盘只对交易日有效"
            )
        resolved = request.trade_date
    else:
        resolved = await trade_calendar_service.resolve_latest_trade_date(session)
    if request.scope == "previous":
        return await resolve_previous_window(session, request.period, resolved)
    return await resolve_review_window(session, request.period, resolved)


async def ensure_window_ready(
    session: AsyncSession, agent: TradingAgent, window: ReviewWindow
) -> None:
    """派发前预检窗口末日的盘后同步是否落库。

    页面按需生成在派发时即拒绝并给出引导，避免进队列后才按 Celery 退避
    重试——当日 16:00 前的手动触发必然等不到同步。

    Raises:
        ReviewWindowNotReadyError: 窗口末日资金快照（盘后同步）缺失。
        AgentAccountNotDesignatedError: Agent 未绑定专属模拟盘账户。
    """
    from app.services.trading import account_service

    account = await account_service.resolve_agent_account(session, agent.agent_key)
    if not await sync_landed(session, account.id, window.end):
        raise ReviewWindowNotReadyError(
            sync_pending_message(window.end, manual=True)
        )
