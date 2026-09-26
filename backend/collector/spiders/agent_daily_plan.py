"""交易 Agent 每日选股与交易计划生成采集器（internal 渠道，heavy 队列）。

19:30 串行在 16:00 sync / 19:00 agent 复盘（D30 重排，晚于大盘复盘 18:35）
/ 16:30 涨停归因 / ≥17:45 异动之后；核心输入「当日复盘解读」18:35 才生成。
循环全部 active Agent（planned 天然
跳过），按注册行 plan_cadence 门控生成日（D28：daily 每交易日 / weekly
周期末 / monthly 月末，非 due 记跳过明细）；单 Agent 异常隔离记入明细，
聚合成一条 CollectResult：全跳过 → SKIPPED、部分成功 → PARTIAL、全失败 →
FAILED；全部 Agent 输入未就绪（``ReviewInputDataNotReadyError``）不吞掉，
交由 Celery 退避重试。
"""

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.paper_trade import TradingAgent
from app.services.review.market_review_service import ReviewInputDataNotReadyError
from app.services.trading import agent_plan_service, agent_registry, agent_review_service
from app.services.trading.agent_plan_service import PlanGenerationLockedError
from app.services.trading.errors import (
    AgentAccountNotDesignatedError,
    PaperTradeNotConfiguredError,
)
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day

_PER_AGENT_SKIPPABLE = (
    AgentAccountNotDesignatedError,
    PaperTradeNotConfiguredError,
    PlanGenerationLockedError,
)


async def _plan_due(session: AsyncSession, agent: TradingAgent, trade_date: date) -> bool:
    """按注册行 plan_cadence 判定 trade_date 是否为计划生成日（D28）。"""
    if agent.plan_cadence == "weekly":
        return await agent_review_service.is_last_trading_day_of_week(
            session, trade_date
        )
    if agent.plan_cadence == "monthly":
        return await agent_review_service.is_last_trading_day_of_month(
            session, trade_date
        )
    return True


class AgentDailyPlanCollector(BaseCollector):
    """每日选股与交易计划生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def _run_one(self, agent_key: str, trade_date: Any) -> dict[str, Any]:
        """单 Agent 生成（独立 session，失败不污染其他 Agent）。

        agent 注册行为外层批量读取的行（列属性已加载，跨 session 访问安全）。
        """
        async with AsyncSessionLocal() as session:
            result = await agent_plan_service.generate_daily_plan(
                session,
                await agent_registry.get_agent(session, agent_key),
                trade_date=trade_date,
                regenerate=False,
            )
        dropped = result.dropped_codes
        return {
            "cached": result.cached,
            "selections": len(result.content.selections),
            "plans": len(result.content.plans),
            **({"dropped_codes": dropped} if dropped else {}),
        }

    async def run(self, **kwargs: Any) -> CollectResult:
        """循环 active Agent 生成或复用当日选股与交易计划。"""
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
            plan_due = {
                agent.agent_key: await _plan_due(session, agent, trade_date)
                for agent in agents
            }
        if not agents:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="无 active 状态的交易 Agent，每日计划未启用",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        lines: list[str] = []
        errors: list[str] = []
        details: dict[str, dict[str, Any]] = {}
        not_ready = 0
        for agent in agents:
            if not plan_due[agent.agent_key]:
                lines.append(
                    f"{agent.agent_key}: {agent.plan_cadence} 频计划未到生成日，跳过"
                )
                continue
            try:
                details[agent.agent_key] = await self._run_one(
                    agent.agent_key, trade_date
                )
            except ReviewInputDataNotReadyError:
                # 不吞掉：全部 Agent 未就绪时向 Celery 退避重试抛出。
                not_ready += 1
                lines.append(f"{agent.agent_key}: 输入未就绪，等待重试")
            except _PER_AGENT_SKIPPABLE as exc:
                lines.append(f"{agent.agent_key}: {exc}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{agent.agent_key}: {exc}")

        stored = sum(1 for d in details.values() if not d["cached"])
        if details and not errors and not_ready == 0:
            status = CollectStatus.SUCCESS
        elif details:
            status = CollectStatus.PARTIAL
        elif errors:
            status = CollectStatus.FAILED
        elif not_ready == len(agents):
            raise ReviewInputDataNotReadyError(
                f"全部 {len(agents)} 个交易 Agent 的计划输入未就绪"
            )
        else:
            status = CollectStatus.SKIPPED

        message = "；".join(lines) or (
            "当日已生成（缓存命中）" if details and not stored else None
        )
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
