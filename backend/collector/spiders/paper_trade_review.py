"""模拟盘复盘生成采集器（internal 渠道，heavy 队列）。

19:00 串行在盘后同步与大盘 AI 复盘（18:35）之后（D30 重排，实例名
paper_trade_review_1610 沿用），循环全部 active Agent 按注册行 review_cadence
生成复盘（D28）：daily=每交易日日度 + 周期末加发周度 / 月末加发月度；
weekly=仅周期末生成周度；monthly=仅月末生成月度——非 due 记跳过明细。
单 Agent 异常隔离记入明细，聚合成一条 CollectResult：全跳过 → SKIPPED、
部分成功 → PARTIAL、全失败 → FAILED；全部 Agent 输入未就绪
（``ReviewInputDataNotReadyError``）不吞掉，交由 Celery 退避重试。

按需通道（B4）：params 带 ``agent_key`` 时只生成该 Agent 的指定 ``period``
（季/半年/年不设定时，由页面接口或 Agent 工具派生同一任务），``regenerate``
强制重跑；页面接口与对话路径都落到同一个 service 入口与解析锁。
"""

from datetime import date, datetime, timezone
from typing import Any, Literal, cast

from app.core.database import AsyncSessionLocal
from app.core.exceptions import NotFoundError
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_registry, agent_review_service
from app.services.trading.agent_review_periods import REVIEW_PERIODS, ReviewPeriod
from app.services.trading.agent_review_service import PaperTradeReviewLockedError
from app.services.trading.errors import AgentAccountNotDesignatedError
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day


def _coerce_trade_date(value: Any) -> date | None:
    """显式日期参数经 Celery JSON 后会变成 ISO 字符串。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


class PaperTradeReviewCollector(BaseCollector):
    """模拟盘复盘生成器（定时日/周/月 + 按需单周期，不直接写表）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def _run_on_demand(
        self, agent_key: str, **kwargs: Any
    ) -> CollectResult:
        """按需生成单 Agent 指定周期复盘（页面接口 / Agent 工具共用）。

        ``regenerate`` 为真时绕过缓存强制重跑；生成中锁冲突记 SKIPPED 并
        提示稍后刷新，不当作失败。输入未就绪向上抛交由 Celery 退避重试。
        """
        started_at = datetime.now(timezone.utc)
        period = kwargs.get("period")
        if period is not None and period not in REVIEW_PERIODS:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[f"未知复盘周期：{period}"],
                message=f"未知复盘周期：{period}",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        raw_trade_date = kwargs.get("trade_date")
        parsed_date = _coerce_trade_date(raw_trade_date)
        if raw_trade_date is not None and parsed_date is None:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[f"无效的 trade_date：{raw_trade_date}"],
                message=f"无效的 trade_date：{raw_trade_date}",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        raw_start = kwargs.get("start_date")
        raw_end = kwargs.get("end_date")
        start_date = _coerce_trade_date(raw_start) if raw_start is not None else None
        end_date = _coerce_trade_date(raw_end) if raw_end is not None else None

        def _failed(message: str) -> CollectResult:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[message],
                message=message,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        if (raw_start is None) != (raw_end is None):
            return _failed("自定义区间须同时提供开始日与结束日")
        if raw_start is not None and start_date is None:
            return _failed(f"无效的 start_date：{raw_start}")
        if raw_end is not None and end_date is None:
            return _failed(f"无效的 end_date：{raw_end}")
        if start_date is not None and end_date is not None:
            if end_date < start_date:
                return _failed(
                    f"区间结束日 {end_date.isoformat()} 早于开始日 "
                    f"{start_date.isoformat()}"
                )
        elif period is None:
            return _failed("缺少复盘周期：须提供 period 或自定义区间")

        trade_date = parsed_date
        if start_date is None and trade_date is None:
            trade_date = latest_trading_day()
        # 自定义区间的基准日由服务层按收边窗口确定，跳过单日交易日预检
        if start_date is None and trade_date is not None and not is_trading_day(
            trade_date
        ):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                message=f"{trade_date.isoformat()} 不是交易日，复盘只对交易日有效",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        async with AsyncSessionLocal() as session:
            try:
                agent = await agent_registry.get_agent(session, agent_key)
            except NotFoundError as exc:
                return CollectResult(
                    source=self.source,
                    data_type=self.data_type,
                    status=CollectStatus.FAILED,
                    errors=[str(exc)],
                    message=str(exc),
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )

            scope = kwargs.get("scope") or "current"
            try:
                result = await agent_review_service.generate_review(
                    session,
                    agent,
                    period=cast(ReviewPeriod | None, period),
                    trade_date=trade_date,
                    scope=cast(Literal["current", "previous"], scope),
                    start_date=start_date,
                    end_date=end_date,
                    regenerate=bool(kwargs.get("regenerate")),
                    trigger="manual",
                    collector_log_id=kwargs.get("collector_log_id"),
                )
            except PaperTradeReviewLockedError as exc:
                return CollectResult(
                    source=self.source,
                    data_type=self.data_type,
                    status=CollectStatus.SKIPPED,
                    message=f"{exc}，请稍后刷新查看",
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    metadata={
                        "agent_key": agent_key,
                        "period": period,
                        "start_date": (
                            start_date.isoformat() if start_date else None
                        ),
                        "end_date": (end_date.isoformat() if end_date else None),
                    },
                )
            except AgentAccountNotDesignatedError as exc:
                return CollectResult(
                    source=self.source,
                    data_type=self.data_type,
                    status=CollectStatus.FAILED,
                    errors=[str(exc)],
                    message=str(exc),
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )

        # 报告框架与基准日以收边后的窗口为准（自定义区间可能映射到另一档）
        result_period = result.content.period
        result_trade_date = result.content.trade_date
        if result.content.no_target_reason is not None:
            message = f"{agent_key} {result_period} 已执行但无复盘对象（空仓无持仓）"
        elif result.cached:
            message = f"{agent_key} {result_period} 复盘已存在，本次未重新生成"
        else:
            message = f"{agent_key} {result_period} 复盘已生成"
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS,
            items_collected=1,
            items_stored=0 if result.cached else 1,
            message=message,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "agent_key": agent_key,
                "period": result_period,
                "trade_date": result_trade_date,
                "start_date": (start_date.isoformat() if start_date else None),
                "end_date": (end_date.isoformat() if end_date else None),
                "cached": result.cached,
                "no_target": result.content.no_target_reason is not None,
            },
        )

    async def _run_one(
        self, agent_key: str, trade_date: Any, collector_log_id: Any = None
    ) -> dict[str, Any] | None:
        """单 Agent 按 review_cadence 生成复盘（独立 session，失败不污染其他 Agent）。

        collector_log_id 透传服务层做 agent_run 溯源关联（D35 会话管理）。

        Returns:
            各周期生成明细；非生成日返回 None（调用方记跳过明细）。
        """
        metadata: dict[str, Any] = {}
        async with AsyncSessionLocal() as session:
            agent = await agent_registry.get_agent(session, agent_key)
            cadence = agent.review_cadence

            if cadence == "weekly":
                periods = (
                    ["week"]
                    if await agent_review_service.is_last_trading_day_of_week(
                        session, trade_date
                    )
                    else []
                )
            elif cadence == "monthly":
                periods = (
                    ["month"]
                    if await agent_review_service.is_last_trading_day_of_month(
                        session, trade_date
                    )
                    else []
                )
            else:
                periods = ["day"]
                # 周期末日历判定加发（失败不拖垮日度结果）
                for period, checker in (
                    ("week", agent_review_service.is_last_trading_day_of_week),
                    ("month", agent_review_service.is_last_trading_day_of_month),
                ):
                    if await checker(session, trade_date):
                        periods.append(period)

            if not periods:
                return None

            for idx, period in enumerate(periods):
                # 首周期（day/week/month）异常向上传播（未就绪退避重试依赖）；
                # 加发周期失败不拖垮首周期结果，隔离记入 metadata。
                try:
                    result = await agent_review_service.generate_review(
                        session,
                        agent,
                        period=period,  # type: ignore[arg-type]
                        trade_date=trade_date,
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
        return metadata

    async def run(self, **kwargs: Any) -> CollectResult:
        """按需单 Agent 生成，或循环 active Agent 生成/复用当日复盘。"""
        agent_key = kwargs.pop("agent_key", None)
        if agent_key:
            return await self._run_on_demand(str(agent_key), **kwargs)

        started_at = datetime.now(timezone.utc)
        trade_date = kwargs.get("trade_date") or latest_trading_day()

        if not is_trading_day(trade_date):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=f"{trade_date.isoformat()} 不是交易日",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        async with AsyncSessionLocal() as session:
            agents = await agent_registry.get_active_agents(session)
        if not agents:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="无 active 状态的交易 Agent，复盘未启用",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        lines: list[str] = []
        errors: list[str] = []
        details: dict[str, dict[str, Any]] = {}
        not_ready = 0
        for agent in agents:
            try:
                result = await self._run_one(
                    agent.agent_key,
                    trade_date,
                    collector_log_id=kwargs.get("collector_log_id"),
                )
                if result is None:
                    lines.append(
                        f"{agent.agent_key}: {agent.review_cadence} 频复盘未到生成日，跳过"
                    )
                    continue
                details[agent.agent_key] = result
                if any(
                    isinstance(v, dict) and v.get("no_target") for v in result.values()
                ):
                    lines.append(
                        f"{agent.agent_key}: 已执行复盘但无对象（空仓无持仓，已记录）"
                    )
            except ReviewInputDataNotReadyError:
                # 不吞掉：全部 Agent 未就绪时向 Celery 退避重试抛出。
                not_ready += 1
                lines.append(f"{agent.agent_key}: 输入未就绪，等待重试")
            except AgentAccountNotDesignatedError as exc:
                lines.append(f"{agent.agent_key}: {exc}")
            except Exception as exc:  # noqa: BLE001
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
        elif not_ready == len(agents):
            raise ReviewInputDataNotReadyError(
                f"全部 {len(agents)} 个交易 Agent 的复盘输入未就绪"
            )
        else:
            status = CollectStatus.SKIPPED

        all_cached = bool(details) and stored == 0
        message = "；".join(lines) or ("当日已生成（缓存命中）" if all_cached else None)
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=status,
            items_collected=len(details),
            items_stored=stored,
            errors=errors,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            message=message,
            metadata={"trade_date": trade_date.isoformat(), "agents": details},
        )
