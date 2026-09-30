"""交易 Agent 盘中计划校准采集器（internal 渠道，heavy 队列，§11.5）。

10:20 / 13:20 循环校准消费集 Agent（active 且执行与校准均未关）：预取计划
标的实时行情 → 慢模型读观察报告出修正单 → 服务层硬校验后留痕/生效。
窗口按北京时间墙钟推导（12 点前早盘，否则午盘），可用 ``window`` 参数显式
覆盖；非交易日 / 非盘中执行时段整体 SKIPPED（校准是盘中一次性语义）。
单 Agent 异常隔离，聚合成一条 CollectResult：全跳过 → SKIPPED、部分成功 →
PARTIAL、全失败 → FAILED；同窗口幂等（服务层执行前已存在检查），Celery
重试只补失败的 Agent。
"""

from datetime import date, datetime, timezone
from typing import Any

from app.core.clock import in_trading_session, now_cn
from app.core.database import AsyncSessionLocal
from app.services.trading import agent_intraday_service, agent_registry
from app.services.trading.agent_plan_calibration import (
    WINDOW_AFTERNOON,
    WINDOW_MORNING,
    CalibrationLockedError,
    run_calibration,
)
from collector.core.async_helpers import run_in_thread
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import is_trading_day, latest_trading_day
from collector.spiders.sina_snapshot import fetch_sina_quotes


def _current_window() -> str:
    """按北京时间墙钟推导校准窗口：12 点前早盘，否则午盘。"""
    return WINDOW_MORNING if now_cn().hour < 12 else WINDOW_AFTERNOON


class AgentPlanCalibrationCollector(BaseCollector):
    """盘中计划校准器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际校准逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def _run_one(
        self, agent_key: str, trade_date: date, window: str, quotes: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """单 Agent 校准（独立 session，失败不污染其他 Agent）。"""
        async with AsyncSessionLocal() as session:
            agent = await agent_registry.get_active_agent(session, agent_key)
            return await run_calibration(session, agent, trade_date, window, quotes=quotes)

    async def run(self, **kwargs: Any) -> CollectResult:
        """循环校准消费集 Agent 出修正单。"""
        started_at = datetime.now(timezone.utc)
        trade_date = kwargs.get("trade_date") or latest_trading_day()
        window = kwargs.get("window") or _current_window()

        if not is_trading_day(trade_date):
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message=f"{trade_date.isoformat()} 不是交易日",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        if not in_trading_session():
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="非盘中执行时段，校准仅限盘中（10:20/13:20 定时触发）",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        async with AsyncSessionLocal() as session:
            agents = await agent_registry.get_calibration_agents(session)
            codes = await agent_intraday_service.plan_stock_codes(session, trade_date=trade_date)
        if not agents:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="无启用盘中校准的交易 Agent",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        quotes = await run_in_thread(fetch_sina_quotes, sorted(codes)) if codes else {}
        lines: list[str] = []
        errors: list[str] = []
        details: dict[str, dict[str, Any]] = {}
        for agent in agents:
            try:
                detail = await self._run_one(agent.agent_key, trade_date, window, quotes)
                details[agent.agent_key] = detail
                if detail.get("cached"):
                    lines.append(f"{agent.agent_key}: 该窗口已校准，幂等跳过")
                elif detail.get("skipped_reason"):
                    lines.append(f"{agent.agent_key}: {detail['skipped_reason']}")
                else:
                    lines.append(
                        f"{agent.agent_key}: 修正单 {detail['total']} 条"
                        f"（生效 {detail['applied']} / 影子 {detail['shadow']}"
                        f" / 拒绝 {detail['rejected']}）"
                    )
            except CalibrationLockedError as exc:
                lines.append(f"{agent.agent_key}: {exc}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{agent.agent_key}: {exc}")

        if details and not errors:
            status = CollectStatus.SUCCESS
        elif details:
            status = CollectStatus.PARTIAL
        elif errors:
            status = CollectStatus.FAILED
        else:
            status = CollectStatus.SKIPPED

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=status,
            items_collected=len(details),
            items_stored=sum(
                d.get("applied", 0) + d.get("shadow", 0) + d.get("rejected", 0)
                for d in details.values()
            ),
            errors=errors,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            message="；".join(lines) or None,
            metadata={"trade_date": trade_date.isoformat(), "window": window, "agents": details},
        )
