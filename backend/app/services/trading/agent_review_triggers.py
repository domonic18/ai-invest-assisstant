"""复盘按需生成入口（B4）：页面接口统一校验后派发 Celery 异步任务。

页面触发不能阻塞在 HTTP 请求里（LLM 分钟级会被代理 504），统一走
``paper-trade-review`` 任务的按需分支（params 带 agent_key/period）：
生成过程与定时路径共用同一 service 入口、redis 解析锁与缓存幂等。
Agent 对话路径直调 ``generate_review``（工具内 await，事件回写），
两者只在触发方式（trigger）与返回通道上不同。
"""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from app.services.market.trade_calendar_service import (
    NonTradingDayError,
    is_trading_day,
)
from app.services.trading.agent_review_periods import REVIEW_PERIODS

#: 复盘任务类型名（TASK_SPECS 键，定时与按需共用）
REVIEW_TASK_NAME = "paper-trade-review"


async def enqueue_review_generation(
    session: AsyncSession,
    agent_key: str,
    *,
    period: str,
    trade_date: date | None = None,
    regenerate: bool = False,
) -> CollectorLog:
    """校验并派发单 Agent 指定周期的复盘生成任务。

    Args:
        session: 请求作用域会话（仅用于校验与写 pending 日志行）。
        agent_key: 交易 Agent 标识。
        period: 六档周期之一。
        trade_date: 基准交易日，缺省由任务取最新交易日。
        regenerate: 是否绕过缓存强制重跑。

    Returns:
        dispatcher 创建的 pending ``CollectorLog``（含 celery_task_id，供前端轮询）。

    Raises:
        ValueError: 周期不在六档词表内。
        NotFoundError: Agent 未注册。
        NonTradingDayError: 显式交易日不是交易日。
    """
    # 延迟 import：dispatcher 依赖 collector 包，服务层保持叶子依赖
    from app.services.trading import agent_registry
    from collector.runtime.dispatcher import dispatch_collector_task

    if period not in REVIEW_PERIODS:
        raise ValueError(f"未知复盘周期：{period}")
    await agent_registry.get_agent(session, agent_key)
    if trade_date is not None and not await is_trading_day(session, trade_date):
        raise NonTradingDayError(
            f"{trade_date.isoformat()} 不是交易日，复盘只对交易日有效"
        )

    params: dict[str, Any] = {
        "agent_key": agent_key,
        "period": period,
        "regenerate": regenerate,
    }
    if trade_date is not None:
        params["trade_date"] = trade_date.isoformat()
    return await dispatch_collector_task(session, REVIEW_TASK_NAME, params)
