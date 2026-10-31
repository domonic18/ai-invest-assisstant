"""复盘按需生成入口（B4）：页面接口统一校验后派发 Celery 异步任务。

页面触发不能阻塞在 HTTP 请求里（LLM 分钟级会被代理 504），统一走
``paper-trade-review`` 任务的按需分支（params 带 agent_key 与窗口入参）：
生成过程与定时路径共用同一 service 入口、redis 解析锁与缓存幂等。
Agent 对话路径直调 ``generate_review``（工具内 await，事件回写），
两者只在触发方式（trigger）与返回通道上不同。

窗口入参三形态（§4.1/§4.3）：``period`` 本期、``period``+``scope=previous``
上一完整周期、``start_date``/``end_date`` 自定义区间（缺 period 时按跨度映射
报告框架）。派发前解析窗口并预检窗口末日盘后同步是否落库：未就绪直接
400 引导用户改用上期/历史区间，不把注定失败的任务塞进重试队列。
"""

from datetime import date
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collector_log import CollectorLog
from app.services.trading.agent_review_content import REVIEW_SKILL_ID

#: 复盘任务类型名（TASK_SPECS 键，定时与按需共用；与落库 skill_id 同名）
REVIEW_TASK_NAME = REVIEW_SKILL_ID


async def enqueue_review_generation(
    session: AsyncSession,
    agent_key: str,
    *,
    period: str | None = None,
    trade_date: date | None = None,
    scope: Literal["current", "previous"] = "current",
    start_date: date | None = None,
    end_date: date | None = None,
    regenerate: bool = False,
) -> CollectorLog:
    """校验并派发单 Agent 指定窗口的复盘生成任务。

    Args:
        session: 请求作用域会话（仅用于校验与写 pending 日志行）。
        agent_key: 交易 Agent 标识。
        period: 六档周期之一；自定义区间缺省时由任务按跨度映射。
        trade_date: 基准交易日，缺省由任务取最新交易日。
        scope: current=本期 / previous=上一完整周期。
        start_date/end_date: 自定义区间（须成对）。
        regenerate: 是否绕过缓存强制重跑。

    Returns:
        dispatcher 创建的 pending ``CollectorLog``（含 celery_task_id，供前端轮询）。

    Raises:
        BadRequestError: 周期不在六档词表、区间不成对/倒置、缺少周期与区间，
            或窗口末日盘后同步尚未落库（``ReviewWindowNotReadyError``）。
        NotFoundError: Agent 未注册。
        NonTradingDayError: 显式交易日不是交易日。
    """
    # 延迟 import：dispatcher 依赖 collector 包，服务层保持叶子依赖
    from app.services.trading import agent_registry, agent_review_service
    from collector.runtime.dispatcher import dispatch_collector_task

    request = agent_review_service.ReviewWindowRequest.from_values(
        period=period,
        trade_date=trade_date,
        scope=scope,
        start_date=start_date,
        end_date=end_date,
    )
    agent = await agent_registry.get_agent(session, agent_key)
    window = await agent_review_service.resolve_requested_window(session, request)
    await agent_review_service.ensure_window_ready(session, agent, window)

    params: dict[str, Any] = {"agent_key": agent_key, "regenerate": regenerate}
    if period is not None:
        params["period"] = period
    if scope != "current":
        params["scope"] = scope
    if trade_date is not None:
        params["trade_date"] = trade_date.isoformat()
    if start_date is not None and end_date is not None:
        params["start_date"] = start_date.isoformat()
        params["end_date"] = end_date.isoformat()
    return await dispatch_collector_task(session, REVIEW_TASK_NAME, params)
