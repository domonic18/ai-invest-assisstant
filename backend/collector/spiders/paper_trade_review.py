"""模拟盘复盘生成采集器（internal 渠道，heavy 队列）。

16:10 串行在盘后同步之后，循环全部 active Agent 生成当日分层复盘；周五 /
月末最后一个交易日（日历判定，cron 表达不了）同任务内加发周度 / 月度——
加发失败不影响日度结果（记入 metadata）。单 Agent 异常隔离记入明细，聚
合成一条 CollectResult：全跳过 → SKIPPED、部分成功 → PARTIAL、全失败 →
FAILED；全部 Agent 输入未就绪（``ReviewInputDataNotReadyError``）不吞掉，
交由 Celery 退避重试。
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

    async def _run_one(self, agent_key: str, trade_date: Any) -> dict[str, Any]:
        """单 Agent 日度复盘 + 周期末加发（独立 session，失败不污染其他 Agent）。

        agent 注册行为外层批量读取的行（列属性已加载，跨 session 访问安全）。
        """
        metadata: dict[str, Any] = {}
        async with AsyncSessionLocal() as session:
            agent = await agent_registry.get_agent(session, agent_key)
            day = await agent_review_service.generate_review(
                session, agent, period="day", trade_date=trade_date, regenerate=False
            )
            metadata["day"] = {"cached": day.cached}

            # 周期末日历判定加发（失败不拖垮日度结果）
            for period, checker in (
                ("week", agent_review_service.is_last_trading_day_of_week),
                ("month", agent_review_service.is_last_trading_day_of_month),
            ):
                if not await checker(session, trade_date):
                    continue
                try:
                    extra = await agent_review_service.generate_review(
                        session,
                        agent,
                        period=period,  # type: ignore[arg-type]
                        trade_date=trade_date,
                        regenerate=False,
                    )
                    metadata[period] = {"cached": extra.cached}
                except (NoReviewTargetError, PaperTradeReviewLockedError) as exc:
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
                details[agent.agent_key] = await self._run_one(
                    agent.agent_key, trade_date
                )
            except ReviewInputDataNotReadyError:
                # 不吞掉：全部 Agent 未就绪时向 Celery 退避重试抛出。
                not_ready += 1
                lines.append(f"{agent.agent_key}: 输入未就绪，等待重试")
            except (AgentAccountNotDesignatedError, NoReviewTargetError) as exc:
                lines.append(f"{agent.agent_key}: {exc}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{agent.agent_key}: {exc}")

        stored = sum(
            1 for d in details.values() if not d.get("day", {}).get("cached", True)
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
