"""复盘生成编排：窗口解析 → 预检 → 取数 → LLM → 校验 → 落库 → 经验沉淀。

窗口入参统一为 ``ReviewWindowRequest``，与读取/对比/派发路径同口径。生成
过程经 ``AgentRunRecorder`` 记录执行轨迹（D35 会话管理）：缓存命中落 skipped +
cache_hit，异常落 failed 后原样上抛。

空仓无复盘对象不视为失败：落「无复盘对象」标记行（success，no_target_reason
非空），展示层据此与「未执行」区分。
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.locking import GENERATION_LOCK_TTL_SECONDS, redis_lock
from app.models.paper_trade import TradingAgent
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_memory_service, agent_methodology
from app.services.trading.agent_review_cache import (
    input_hash,
    load_cached,
    persist_review,
)
from app.services.trading.agent_review_content import (
    NO_TARGET_REASON,
    REVIEW_SKILL_ID,
    PaperTradeReviewContent,
    PaperTradeReviewRecord,
    ReviewGenerateResult,
)
from app.services.trading.agent_review_errors import (
    PaperTradeReviewLockedError,
    ReviewWindowNotReadyError,
)
from app.services.trading.agent_review_experiences import filter_period_experiences
from app.services.trading.agent_review_inputs import (
    collect_window_input,
    has_review_target,
    market_review_optional,
    sync_landed,
)
from app.services.trading.agent_review_key_trades import (
    filter_window_input,
    load_key_trade_selection,
)
from app.services.trading.agent_review_llm import run_review_llm, validate_review_trades
from app.services.trading.agent_review_metrics import compute_window_metrics
from app.services.trading.agent_review_periods import is_long_period
from app.services.trading.agent_review_window import (
    ReviewWindowRequest,
    resolve_requested_window,
    sync_pending_message,
)
from app.services.trading.agent_run_recorder import AgentRunRecorder


def _error_text(exc: BaseException) -> str:
    """异常转 agent_run.error_msg 文本（类型名 + 消息，截断 2000 字符）。"""
    return f"{type(exc).__name__}: {exc}"[:2000]


async def generate_review(
    session: AsyncSession,
    agent: TradingAgent,
    request: ReviewWindowRequest,
    *,
    regenerate: bool = False,
    trigger: str = "scheduled",
    collector_log_id: int | None = None,
) -> ReviewGenerateResult:
    """生成（或读取缓存的）指定 Agent 的模拟盘分层复盘。

    Raises:
        BadRequestError: 区间不成对/倒置/无交易日。
        NonTradingDayError: 指定日期不是交易日，或周期窗口内无交易日。
        AgentAccountNotDesignatedError: 该 Agent 未绑定专属账户。
        ReviewInputDataNotReadyError: 盘后同步尚未落库（定时路径，Celery 退避重试）。
        ReviewWindowNotReadyError: 盘后同步尚未落库（手动路径，直接失败不重试）。
        PaperTradeReviewLockedError: 其他实例正在生成。
    """
    from app.services.trading import account_service

    window = await resolve_requested_window(session, request)
    if window.is_empty:
        from app.services.market.trade_calendar_service import NonTradingDayError

        raise NonTradingDayError(
            f"{window.requested_start.isoformat()} 至 "
            f"{window.requested_end.isoformat()} 区间内没有交易日"
        )
    # 报告框架与基准日以收边后的窗口为准：自定义区间按跨度映射周期，
    # 上期窗口的基准日是其最后交易日（与缓存行 trade_date 对齐）
    effective_period = window.period
    resolved = window.end
    account = await account_service.resolve_agent_account(session, agent.agent_key)
    start, end = window.start, window.end
    cache_key = input_hash(agent.agent_key, account.id, effective_period, start, end)

    recorder = AgentRunRecorder(
        agent_key=agent.agent_key,
        kind="review",
        period=effective_period,
        trigger=trigger,
        trade_date=resolved,
        collector_log_id=collector_log_id,
    )
    await recorder.start()
    try:
        if not regenerate:
            cached = await load_cached(session, cache_key)
            if cached:
                await recorder.finish(
                    "skipped", summary={"cache_hit": True, "stage": "pre_lock"}
                )
                return ReviewGenerateResult(content=cached, cached=True)

        landed = False
        has_target = False
        async with recorder.step(
            "precheck",
            "执行预检（盘后同步/复盘对象）",
            payload_builder=lambda: {
                "trade_date": resolved.isoformat(),
                "window": [start.isoformat(), end.isoformat()],
                "account_id": account.id,
                "sync_landed": landed,
                "has_review_target": has_target,
            },
        ):
            landed = await sync_landed(session, account.id, resolved)
            if not landed:
                # 手动触发直接失败并引导改用上期/历史区间；定时路径保持
                # ReviewInputDataNotReadyError 由 Celery 退避等待 16:00 同步
                manual = trigger == "manual"
                error_cls = (
                    ReviewWindowNotReadyError
                    if manual
                    else ReviewInputDataNotReadyError
                )
                raise error_cls(sync_pending_message(resolved, manual=manual))
            has_target = await has_review_target(session, account.id, start, end)

        if not has_target:
            # 空仓无复盘对象：落「无对象」标记行（success，不进 LLM、不沉淀经验），
            # 镜像计划空仓观望语义——执行过但无内容，与「未执行」可区分
            record = PaperTradeReviewRecord(
                **PaperTradeReviewContent(
                    period=effective_period,
                    trade_date=resolved.isoformat(),
                    overall="",
                    trades=[],
                    bias="",
                    suggestion="",
                    sections=[],
                    market_context="",
                    methodology_check=[],
                    experiences=[],
                    no_target_reason=NO_TARGET_REASON,
                ).model_dump(),
                agent_key=agent.agent_key,
            )
            await persist_review(session, input_hash=cache_key, content=record, meta={})
            await session.commit()
            await recorder.finish(
                "success",
                summary={"no_target": True, "reason": NO_TARGET_REASON},
            )
            return ReviewGenerateResult(content=record, cached=False)

        async with redis_lock(
            f"{REVIEW_SKILL_ID}:{agent.agent_key}:{account.id}:"
            f"{effective_period}:{start.isoformat()}:{end.isoformat()}",
            ttl=GENERATION_LOCK_TTL_SECONDS,
        ) as acquired:
            if not acquired:
                cached = await load_cached(session, cache_key)
                if cached:
                    await recorder.finish(
                        "skipped",
                        summary={"cache_hit": True, "stage": "lock_unavailable"},
                    )
                    return ReviewGenerateResult(content=cached, cached=True)
                await recorder.finish(
                    "failed",
                    error_msg=(
                        f"其他实例正在生成 {resolved.isoformat()} 的 {effective_period} 复盘"
                    ),
                )
                raise PaperTradeReviewLockedError(
                    f"其他实例正在生成 {resolved.isoformat()} 的 {effective_period} 复盘"
                )

            if not regenerate:
                cached = await load_cached(session, cache_key)
                if cached:
                    await recorder.finish(
                        "skipped", summary={"cache_hit": True, "stage": "in_lock"}
                    )
                    return ReviewGenerateResult(content=cached, cached=True)

            window_input: dict[str, Any] = {}
            async with recorder.step(
                "input.window",
                "复盘窗口取数（委托/成交/净值）",
                payload_builder=lambda: window_input or None,
            ):
                window_input = await collect_window_input(
                    session, account.id, start, end
                )

            metrics_payload: dict[str, Any] = {}
            async with recorder.step(
                "input.metrics",
                "确定性指标计算（系统口径）",
                payload_builder=lambda: metrics_payload or None,
            ):
                metrics = await compute_window_metrics(
                    session,
                    account_id=account.id,
                    agent_key=agent.agent_key,
                    window=window,
                )
                metrics_payload = metrics.to_dict()
            window_input["metrics"] = metrics_payload

            if is_long_period(effective_period):
                key_trades_payload: dict[str, Any] = {}
                async with recorder.step(
                    "input.key_trades",
                    "关键交易筛选（长周期不做全量逐笔）",
                    payload_builder=lambda: key_trades_payload or None,
                ):
                    selection = await load_key_trade_selection(
                        session,
                        account_id=account.id,
                        agent_key=agent.agent_key,
                        window=window,
                    )
                    window_input = filter_window_input(window_input, selection)
                    key_trades_payload = selection.to_wire()

            market_review: dict[str, Any] | None = None
            async with recorder.step(
                "input.market_review",
                "大盘复盘解读（盘面语境）",
                payload_builder=lambda: {"sections": market_review},
            ):
                market_review = await market_review_optional(session, resolved)
            window_input["market_review"] = market_review

            methodology: dict[str, Any] | None = None
            async with recorder.step(
                "input.methodology",
                "方法论基座检索（KB 直读）",
                payload_builder=lambda: {
                    "source_id": agent.methodology_source_id,
                    "methodology": methodology,
                },
            ):
                methodology = await agent_methodology.build_methodology_input(
                    session, source_id=agent.methodology_source_id, query_text=None
                )
            window_input["methodology"] = methodology

            llm_meta: dict[str, Any] = {}
            prompt_holder: dict[str, str] = {}
            output_holder: dict[str, Any] = {}
            async with recorder.step(
                "llm",
                "LLM 结构化生成",
                payload_builder=lambda: {
                    "prompt": prompt_holder.get("prompt"),
                    "meta": llm_meta,
                    "output": output_holder.get("output"),
                },
            ):
                content = await run_review_llm(
                    session,
                    agent,
                    effective_period,
                    resolved,
                    window_input,
                    meta_out=llm_meta,
                    prompt_out=prompt_holder,
                )
                output_holder["output"] = content.model_dump(mode="json")

            dropped_cl: list[str] = []
            async with recorder.step(
                "validate",
                "后置校验（幻觉委托剔除）",
                payload_builder=lambda: {
                    "dropped_cl_ord_ids": dropped_cl,
                    "trades": len(content.trades),
                },
            ):
                content = validate_review_trades(
                    content, {o["cl_ord_id"] for o in window_input["orders"]}
                )
                # §4.6：长周期只关联体系级经验（报告与记忆沉淀同一口径）
                content = content.model_copy(
                    update={
                        "experiences": filter_period_experiences(
                            effective_period, content.experiences
                        )
                    }
                )
                dropped_cl = sorted(
                    {
                        t["cl_ord_id"]
                        for t in output_holder["output"].get("trades", [])
                        if isinstance(t, dict) and "cl_ord_id" in t
                    }
                    - {t.cl_ord_id for t in content.trades}
                )

            record = PaperTradeReviewRecord(
                **content.model_dump(),
                agent_key=agent.agent_key,
                metrics=metrics_payload,
            )

            cache_row_id = 0
            async with recorder.step(
                "persist",
                "落库（ai_analysis_result 缓存行）",
                payload_builder=lambda: {
                    "trades": len(record.trades),
                    "experiences": len(record.experiences),
                    "methodology_check": len(record.methodology_check),
                    "cache_row_id": cache_row_id,
                },
            ):
                cache_row_id = await persist_review(
                    session, input_hash=cache_key, content=record, meta=llm_meta
                )

            sedimented = 0
            async with recorder.step(
                "memory",
                "经验沉淀 agent_memory（批次 9）",
                payload_builder=lambda: {
                    "source_result_id": cache_row_id,
                    "sedimented": sedimented,
                },
            ):
                # 与缓存行同一事务原子提交：沉淀失败整体回滚，重试重新生成重新沉淀
                sedimented = await agent_memory_service.sediment_experiences(
                    session,
                    agent.agent_key,
                    experiences=record.experiences,
                    source_result_id=cache_row_id,
                )
                await session.commit()

        await recorder.finish(
            "success",
            summary={
                "cache_hit": False,
                "regenerate": regenerate,
                "kb_used": bool(methodology),
                "trades": len(record.trades),
                "sections": len(record.sections),
                "experiences": len(record.experiences),
                "methodology_check": len(record.methodology_check),
                "sedimented_experiences": sedimented,
                "model": llm_meta.get("model_name"),
                "latency_ms": llm_meta.get("latency_ms"),
            },
        )
        return ReviewGenerateResult(content=record, cached=False)
    except Exception as exc:
        await recorder.finish("failed", error_msg=_error_text(exc))
        raise
