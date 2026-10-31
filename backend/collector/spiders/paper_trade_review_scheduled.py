"""复盘定时生成通道：循环 active Agent 按 review_cadence 生成日/周/月复盘。

daily=每交易日日度 + 周期末加发周度 / 月末加发月度；weekly=仅周期末生成
周度；monthly=仅月末生成月度——非 due 记跳过明细。单 Agent 异常隔离记入
明细，聚合成一条 CollectResult：全跳过 → SKIPPED、部分成功 → PARTIAL、
全失败 → FAILED；当日应生成的 Agent 全部输入未就绪
（``ReviewInputDataNotReadyError``）不吞掉，交由 Celery 退避重试。
"""

from datetime import date, datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.market.trade_calendar_service import (
    is_trading_day,
    resolve_latest_trade_date,
)
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_registry, agent_review_service
from app.services.trading.agent_review_errors import PaperTradeReviewLockedError
from app.services.trading.agent_review_periods import (
    AUTO_REVIEW_PERIODS,
    CADENCE_PERIODS,
    DEFAULT_REVIEW_PERIOD,
    is_period_end,
)
from app.services.trading.agent_review_window import ReviewWindowRequest
from app.services.trading.errors import AgentAccountNotDesignatedError
from collector.core.base import CollectResult, CollectStatus
from collector.spiders.paper_trade_review_common import (
    build_result,
    coerce_trade_date,
    is_soft_timeout,
)


async def _run_one(
    agent_key: str, trade_date: date, collector_log_id: Any = None
) -> dict[str, Any] | None:
    """单 Agent 按 review_cadence 生成复盘（独立 session，失败不污染其他 Agent）。

    collector_log_id 透传服务层做 agent_run 溯源关联（D35 会话管理）。

    Returns:
        各周期生成明细；非生成日返回 None（调用方记跳过明细）。
    """
    metadata: dict[str, Any] = {}
    async with AsyncSessionLocal() as session:
        agent = await agent_registry.get_agent(session, agent_key)
        primary = CADENCE_PERIODS.get(agent.review_cadence, DEFAULT_REVIEW_PERIOD)

        if primary == DEFAULT_REVIEW_PERIOD:
            # 日度：每交易日生成日度，周期末日历判定加发周/月（失败不拖垮日度结果）
            periods = [primary]
            for extra in AUTO_REVIEW_PERIODS:
                if extra != primary and await is_period_end(
                    session, extra, trade_date
                ):
                    periods.append(extra)
        else:
            # 周/月频：仅周期末生成对应周期
            periods = (
                [primary] if await is_period_end(session, primary, trade_date) else []
            )

        if not periods:
            return None

        for idx, period in enumerate(periods):
            # 首周期（day/week/month）异常向上传播（未就绪退避重试依赖）；
            # 加发周期失败不拖垮首周期结果，隔离记入 metadata。软超时例外
            # ——必须上抛由 run_collector_task 统一收尾，否则会拖到硬限被
            # SIGKILL 且 collector_log 停留 running。
            try:
                result = await agent_review_service.generate_review(
                    session,
                    agent,
                    ReviewWindowRequest(period=period, trade_date=trade_date),
                    regenerate=False,
                    trigger="scheduled",
                    collector_log_id=collector_log_id,
                )
                metadata[period] = {
                    "cached": result.cached,
                    "no_target": result.content.no_target_reason is not None,
                }
            except PaperTradeReviewLockedError as exc:
                if idx == 0:
                    raise
                metadata[period] = {"skipped": str(exc)}
            except Exception as exc:  # noqa: BLE001
                if idx == 0 or is_soft_timeout(exc):
                    raise
                metadata[period] = {"error": str(exc)}
    return metadata


async def run_scheduled(source: str, data_type: str, **kwargs: Any) -> CollectResult:
    """循环 active Agent 生成/复用当日复盘（默认通道）。"""
    started_at = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        trade_date = coerce_trade_date(kwargs.get("trade_date"))
        if trade_date is None:
            trade_date = await resolve_latest_trade_date(session)
        if not await is_trading_day(session, trade_date):
            return build_result(
                source,
                data_type,
                started_at,
                CollectStatus.SKIPPED,
                message=f"{trade_date.isoformat()} 不是交易日",
            )
        agents = await agent_registry.get_active_agents(session)
    if not agents:
        return build_result(
            source,
            data_type,
            started_at,
            CollectStatus.SKIPPED,
            message="无 active 状态的交易 Agent，复盘未启用",
        )

    lines: list[str] = []
    errors: list[str] = []
    details: dict[str, dict[str, Any]] = {}
    not_ready = 0
    #: 当日应生成复盘的 Agent 数（非生成日的 Agent 不计入，避免重试门槛被稀释）
    due = 0
    not_ready_reasons: list[str] = []
    for agent in agents:
        try:
            result = await _run_one(
                agent.agent_key,
                trade_date,
                collector_log_id=kwargs.get("collector_log_id"),
            )
            if result is None:
                lines.append(
                    f"{agent.agent_key}: {agent.review_cadence} 频复盘未到生成日，跳过"
                )
                continue
            due += 1
            details[agent.agent_key] = result
            if any(
                isinstance(v, dict) and v.get("no_target") for v in result.values()
            ):
                lines.append(
                    f"{agent.agent_key}: 已执行复盘但无对象（空仓无持仓，已记录）"
                )
        except ReviewInputDataNotReadyError as exc:
            # 不吞掉：应生成的 Agent 全部未就绪时向 Celery 退避重试抛出。
            due += 1
            not_ready += 1
            reason = str(exc) or exc.default_message
            if reason not in not_ready_reasons:
                not_ready_reasons.append(reason)
            lines.append(f"{agent.agent_key}: 输入未就绪（{reason}），等待重试")
        except AgentAccountNotDesignatedError as exc:
            lines.append(f"{agent.agent_key}: {exc}")
        except Exception as exc:  # noqa: BLE001
            if is_soft_timeout(exc):
                raise
            errors.append(f"{agent.agent_key}: {exc}")

    # 新落库口径跨周期：任一周期 fresh 生成（非缓存命中）即计入
    stored = sum(
        1
        for d in details.values()
        if any(
            isinstance(v, dict) and v.get("cached") is False
            for v in d.values()
        )
    )
    if details and not errors and not_ready == 0:
        status = CollectStatus.SUCCESS
    elif details:
        status = CollectStatus.PARTIAL
    elif errors:
        status = CollectStatus.FAILED
    elif due and not_ready == due:
        detail = "；".join(not_ready_reasons) or "原因未知"
        raise ReviewInputDataNotReadyError(
            f"全部 {due} 个应生成复盘的交易 Agent 输入未就绪：{detail}"
        )
    else:
        status = CollectStatus.SKIPPED

    all_cached = bool(details) and stored == 0
    message = "；".join(lines) or ("当日已生成（缓存命中）" if all_cached else None)
    return build_result(
        source,
        data_type,
        started_at,
        status,
        message=message,
        errors=errors,
        items_collected=len(details),
        items_stored=stored,
        metadata={"trade_date": trade_date.isoformat(), "agents": details},
    )
