"""skill 链路的 LLM 主备切换。

deepagents skill 在入口解析一次模型配置并把配置固化进 agent 实例：上游额度
耗尽（429/402）时 ``FailoverHealthCallback`` 会把配置标记进冷却，却没有人
重新解析配置，备用模型因此永远不会被选中——skill 直接以失败告终
（2026-11-05 生产大盘复盘事故：kimi 429 后只有 ``llm_failover_marked``、
没有 ``llm_failover_switched``，任务直接进死信）。

本模块在 skill 执行外层补上「标记冷却 → 重新解析（过健康门）→ 换模型重跑」
的一次重试，与 ``run_structured`` 的 failover 语义一致。skill 工具全是读
操作，重跑无副作用。
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog

from app.services.admin.llm_config_service import ResolvedLLMConfig
from app.services.admin.llm_failover import classify_llm_error, mark_unhealthy

logger = structlog.get_logger(__name__)

T = TypeVar("T")


async def run_with_llm_failover(
    resolve: Callable[[], Awaitable[ResolvedLLMConfig]],
    run: Callable[[ResolvedLLMConfig], Awaitable[T]],
    *,
    task_key: str,
) -> tuple[T, ResolvedLLMConfig]:
    """执行 skill 逻辑，额度/限流类失败时切备用模型重跑一次。

    Args:
        resolve: 解析 LLM 配置的协程；重试时再次调用以过健康门切到备用。
        run: 拿到配置后执行 skill 逻辑的协程。
        task_key: 任务槽位标识，仅用于日志。

    Returns:
        (执行结果, 最终生效的配置)。

    Raises:
        Exception: 非额度类异常原样上抛；额度类失败且无备用可切时原样上抛
            （不对同一死模型重复消耗时间）。
    """
    cfg = await resolve()
    try:
        return await run(cfg), cfg
    except Exception as exc:
        if not classify_llm_error(exc):
            raise
        # 额度耗尽：主配置进冷却（callback 已标记，此处确定性补一次），
        # 重新解析过健康门切备用后重跑
        await mark_unhealthy(cfg.config_id)
        retried = await resolve()
        if retried.config_id == cfg.config_id:
            raise
        logger.warning(
            "skill_llm_failover_switched",
            task=task_key,
            config_id=cfg.config_id,
            backup_config_id=retried.config_id,
            backup_model=retried.model_name,
        )
        return await run(retried), retried
