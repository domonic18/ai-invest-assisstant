"""模拟盘复盘生成采集器（internal 渠道，heavy 队列）。

19:00 串行在盘后同步与大盘 AI 复盘（18:35）之后（D30 重排，实例名
paper_trade_review_1610 沿用），循环全部 active Agent 按注册行 review_cadence
生成复盘（D28）：daily=每交易日日度 + 周期末加发周度 / 月末加发月度；
weekly=仅周期末生成周度；monthly=仅月末生成月度——非 due 记跳过明细。
单 Agent 异常隔离记入明细，聚合成一条 CollectResult：全跳过 → SKIPPED、
部分成功 → PARTIAL、全失败 → FAILED；全部 Agent 输入未就绪
（``ReviewInputDataNotReadyError``）不吞掉，交由 Celery 退避重试。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_registry, agent_review_service
from app.services.trading.agent_review_service import (
    NoReviewTargetError,
    PaperTradeReviewLockedError,
)
from app.services.trading.errors import AgentAccountNotDesignatedError
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day


class PaperTradeReviewCollector(BaseCollector):
    """模拟盘日/周/月复盘生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def _run_one(
        self, agent_key: str, trade_date: Any
    ) -> dict[str, Any] | None:
        """单 Agent 按 review_cadence 生成复盘（独立 session，失败不污染其他 Agent）。

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
                    )
                    metadata[period] = {"cached": result.cached}
                except (NoReviewTargetError, PaperTradeReviewLockedError) as exc:
                    if idx == 0:
                        raise
                    metadata[period] = {"skipped": str(exc)}
        return metadata

    async def run(self, **kwargs: Any) -> CollectResult:
        """循环 active Agent 生成或复用当日复盘；周期末加发周/月度。"""
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
                result = await self._run_one(agent.agent_key, trade_date)
                if result is None:
                    lines.append(
                        f"{agent.agent_key}: {agent.review_cadence} 频复盘未到生成日，跳过"
                    )
                    continue
                details[agent.agent_key] = result
            except ReviewInputDataNotReadyError:
                # 不吞掉：全部 Agent 未就绪时向 Celery 退避重试抛出。
                not_ready += 1
                lines.append(f"{agent.agent_key}: 输入未就绪，等待重试")
            except (AgentAccountNotDesignatedError, NoReviewTargetError) as exc:
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
