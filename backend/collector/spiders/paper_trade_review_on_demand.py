"""复盘按需生成通道：params 带 agent_key 时只生成该 Agent 的指定窗口。

页面接口与 Agent 工具都落到同一个 service 入口与解析锁；``regenerate``
强制重跑。生成中锁冲突记 SKIPPED 并提示稍后刷新；盘后同步未落库
（``ReviewWindowNotReadyError``）记 FAILED 并带引导文案，不进重试队列。
"""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, cast

from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.market.trade_calendar_service import (
    is_trading_day,
    resolve_latest_trade_date,
)
from app.services.trading import agent_registry, agent_review_service
from app.services.trading.agent_review_errors import (
    PaperTradeReviewLockedError,
    ReviewWindowNotReadyError,
)
from app.services.trading.agent_review_window import (
    DEFAULT_REVIEW_SCOPE,
    ReviewWindowRequest,
)
from app.services.trading.errors import AgentAccountNotDesignatedError
from collector.core.base import CollectResult, CollectStatus
from collector.spiders.paper_trade_review_common import (
    build_result,
    coerce_trade_date,
)


async def run_on_demand(
    source: str, data_type: str, agent_key: str, **kwargs: Any
) -> CollectResult:
    """生成单 Agent 指定窗口复盘（页面接口 / Agent 工具共用）。"""
    started_at = datetime.now(timezone.utc)

    def failed(message: str) -> CollectResult:
        return build_result(
            source,
            data_type,
            started_at,
            CollectStatus.FAILED,
            message=message,
            errors=[message],
        )

    raw_trade_date = kwargs.get("trade_date")
    parsed_date = coerce_trade_date(raw_trade_date)
    if raw_trade_date is not None and parsed_date is None:
        return failed(f"无效的 trade_date：{raw_trade_date}")

    raw_start = kwargs.get("start_date")
    raw_end = kwargs.get("end_date")
    start_date = coerce_trade_date(raw_start) if raw_start is not None else None
    end_date = coerce_trade_date(raw_end) if raw_end is not None else None
    if raw_start is not None and start_date is None:
        return failed(f"无效的 start_date：{raw_start}")
    if raw_end is not None and end_date is None:
        return failed(f"无效的 end_date：{raw_end}")

    try:
        request = ReviewWindowRequest.from_values(
            period=cast(str | None, kwargs.get("period")),
            trade_date=parsed_date,
            scope=kwargs.get("scope") or DEFAULT_REVIEW_SCOPE,
            start_date=start_date,
            end_date=end_date,
        )
    except BadRequestError as exc:
        return failed(str(exc))

    async with AsyncSessionLocal() as session:
        # 自定义区间的基准日由服务层按收边窗口确定，跳过单日交易日预检
        if request.start_date is None and request.trade_date is None:
            trade_date = await resolve_latest_trade_date(session)
            request = replace(request, trade_date=trade_date)
        if request.start_date is None and request.trade_date is not None:
            if not await is_trading_day(session, request.trade_date):
                return failed(
                    f"{request.trade_date.isoformat()} 不是交易日，复盘只对交易日有效"
                )

        try:
            agent = await agent_registry.get_agent(session, agent_key)
        except NotFoundError as exc:
            return failed(str(exc))

        try:
            result = await agent_review_service.generate_review(
                session,
                agent,
                request,
                regenerate=bool(kwargs.get("regenerate")),
                trigger="manual",
                collector_log_id=kwargs.get("collector_log_id"),
            )
        except PaperTradeReviewLockedError as exc:
            return build_result(
                source,
                data_type,
                started_at,
                CollectStatus.SKIPPED,
                message=f"{exc}，请稍后刷新查看",
                metadata={
                    "agent_key": agent_key,
                    "period": request.period,
                    "start_date": (
                        request.start_date.isoformat() if request.start_date else None
                    ),
                    "end_date": (
                        request.end_date.isoformat() if request.end_date else None
                    ),
                },
            )
        except (
            AgentAccountNotDesignatedError,
            ReviewWindowNotReadyError,
        ) as exc:
            # 盘后同步未落库的手动触发不排队重试：直接失败并带引导文案
            return failed(str(exc))

    # 报告框架与基准日以收边后的窗口为准（自定义区间可能映射到另一档）
    result_period = result.content.period
    result_trade_date = result.content.trade_date
    if result.content.no_target_reason is not None:
        message = f"{agent_key} {result_period} 已执行但无复盘对象（空仓无持仓）"
    elif result.cached:
        message = f"{agent_key} {result_period} 复盘已存在，本次未重新生成"
    else:
        message = f"{agent_key} {result_period} 复盘已生成"
    return build_result(
        source,
        data_type,
        started_at,
        CollectStatus.SUCCESS,
        message=message,
        items_collected=1,
        items_stored=0 if result.cached else 1,
        metadata={
            "agent_key": agent_key,
            "period": result_period,
            "trade_date": result_trade_date,
            "start_date": (
                request.start_date.isoformat() if request.start_date else None
            ),
            "end_date": request.end_date.isoformat() if request.end_date else None,
            "cached": result.cached,
            "no_target": result.content.no_target_reason is not None,
        },
    )
