"""判断模型（System One，D23）解析与 failover 编排。

调用面给批次 8a L1 与未来复用方：``ask_decision(session, state=…, questions=…)``
——经任务槽位 ``decision`` 解析配置（主备绑定 + 健康门）→ 构造
:class:`DecisionModelClient` → 调用；额度/限流/过载类失败
（``DecisionModelUnavailableError``）标记冷却后重解析切备用当次重试一次
（run_structured failover 块同型）。降级契约（advisory）：全部异常由
调用方捕获降级纯 L0，本模块不吞不译。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.decision_model import (
    DecisionModelClient,
    DecisionModelConfigError,
    DecisionModelUnavailableError,
    DecisionThresholds,
    JudgeQuestion,
    JudgeResponse,
    SystemOneAdapter,
    thresholds_from_extra,
)
from app.services.admin.llm_config_service import (
    ResolvedLLMConfig,
)
from app.services.admin.llm_failover import mark_unhealthy
from app.services.admin.llm_task_binding_service import resolve_task_llm

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ResolvedDecisionConfig:
    """解密后的判断模型配置（一条 llm_config = 一个版本 pin + 阈值组）。"""

    config_id: int
    name: str
    model_name: str
    base_url: str
    api_key: str
    timeout_seconds: float
    thresholds: DecisionThresholds


def _timeout_from_extra(extra: dict[str, Any]) -> float:
    """从 ``extra.timeout_seconds`` 解析条目级超时；缺省回全局默认，非法即暴露。"""
    raw = extra.get("timeout_seconds")
    if raw is None:
        return get_settings().decision_model_timeout_seconds
    try:
        timeout = float(raw)
    except (TypeError, ValueError) as exc:
        raise DecisionModelConfigError(f"extra.timeout_seconds 非法: {raw!r}") from exc
    if timeout <= 0:
        raise DecisionModelConfigError(
            f"extra.timeout_seconds 须为正数，当前 {timeout}"
        )
    return timeout


def _resolved_from_config(resolved: ResolvedLLMConfig) -> ResolvedDecisionConfig:
    """槽位解析结果 → 判断配置（健康门之后调用）。"""
    return ResolvedDecisionConfig(
        config_id=resolved.config_id,
        name=resolved.name,
        model_name=resolved.model_name,
        base_url=resolved.base_url,
        api_key=resolved.api_key,
        timeout_seconds=_timeout_from_extra(resolved.extra),
        thresholds=thresholds_from_extra(resolved.extra),
    )


async def resolve_decision_llm(session: AsyncSession) -> ResolvedDecisionConfig:
    """解析判断模型：任务槽位 ``decision``（主备绑定 + 健康门切备）。

    Raises:
        LLMConfigNotConfiguredError: 槽位未绑定或主备皆不可用时抛出。
    """
    return _resolved_from_config(await resolve_task_llm(session, "decision"))


def build_decision_client(cfg: ResolvedDecisionConfig) -> DecisionModelClient:
    """由解析配置构造调用面客户端（adapter 注入 transport 仅测试路径使用）。"""
    adapter = SystemOneAdapter(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=cfg.model_name,
        timeout_seconds=cfg.timeout_seconds,
        config_id=cfg.config_id,
    )
    return DecisionModelClient(
        adapter,
        config_id=cfg.config_id,
        model_name=cfg.model_name,
        thresholds=cfg.thresholds,
    )


async def ask_decision(
    session: AsyncSession,
    *,
    state: Mapping[str, Any],
    questions: Mapping[str, JudgeQuestion],
) -> JudgeResponse:
    """判断模型调用入口：解析 → ask → 额度类失败切备重试一次。

    暂不可用类失败（超时/限流/过载/额度）标记主配置冷却后重解析——健康门
    切到备用则当次重试，无备用可切（重解析同配置）原样上抛；请求类错误
    （认证/pin/题面）重试无意义，直接上抛。全部异常由调用方降级纯 L0。
    """
    cfg = await resolve_decision_llm(session)
    try:
        return await build_decision_client(cfg).ask(state, questions)
    except DecisionModelUnavailableError:
        # 确定性补一次冷却标记（与 langchain 路径的 FailoverHealthCallback 同语义）
        await mark_unhealthy(cfg.config_id)
        retried = await resolve_decision_llm(session)
        if retried.config_id == cfg.config_id:
            raise
        logger.warning(
            "decision_model_failover",
            primary_config_id=cfg.config_id,
            backup_config_id=retried.config_id,
        )
        return await build_decision_client(retried).ask(state, questions)
