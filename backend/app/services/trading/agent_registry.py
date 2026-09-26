"""交易 Agent 注册表服务（``trading_agent``，agent-hub-plan.md D21）。

身份/介绍/模型绑定（空 = 平台默认 chat 模型）、方法论知识源绑定（空 = 未启用
方法论基座注入）、风控阈值（批次 8 盘中执行消费）、auto_exec_enabled 总闸全部
按 agent_key 维度维护，改选即时生效（每次构建 agent / 生成计划时现读）。
注册行 seed-only：新 Agent 手工 SQL 注册，管理端只开放信息/配置更新，不做 CRUD。
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.kb import KbSource
from app.models.llm_config import LLMConfig
from app.models.paper_trade import TradingAgent
from app.schemas.paper_trade import (
    TradingAgentProfileResponse,
    TradingAgentProfileUpdateRequest,
)

logger = structlog.get_logger(__name__)

AGENT_STATUS_ACTIVE = "active"
AGENT_STATUS_PLANNED = "planned"
AGENT_STATUS_DISABLED = "disabled"


async def get_agent(session: AsyncSession, agent_key: str) -> TradingAgent:
    """按 agent_key 读取注册行。

    Raises:
        NotFoundError: agent_key 未注册。
    """
    row = await session.get(TradingAgent, agent_key)
    if row is None:
        raise NotFoundError(f"交易 Agent {agent_key} 不存在")
    return row


async def get_active_agent(session: AsyncSession, agent_key: str) -> TradingAgent:
    """读取 active 状态的注册行（执行/写入路径消费；planned/disabled 只读）。

    Raises:
        NotFoundError: agent_key 未注册。
        UnprocessableEntityError: Agent 未激活（planned / disabled）。
    """
    row = await get_agent(session, agent_key)
    if row.status != AGENT_STATUS_ACTIVE:
        raise UnprocessableEntityError(
            f"交易 Agent {agent_key}（{row.name}）当前状态为 {row.status}，未激活"
        )
    return row


async def list_agents(
    session: AsyncSession, *, statuses: list[str] | None = None
) -> list[TradingAgent]:
    """按状态过滤列出注册行（sort_order 升序）；statuses 空 = 全量。"""
    stmt = select(TradingAgent).order_by(TradingAgent.sort_order.asc())
    if statuses:
        stmt = stmt.where(TradingAgent.status.in_(statuses))
    return list((await session.execute(stmt)).scalars().all())


async def get_active_agents(session: AsyncSession) -> list[TradingAgent]:
    """active Agent 集（spider 多 Agent 循环 / 总览 busy 节点消费）。"""
    return await list_agents(session, statuses=[AGENT_STATUS_ACTIVE])


def to_view(row: TradingAgent) -> TradingAgentProfileResponse:
    """注册行 → wire 视图（camelCase）。"""
    return TradingAgentProfileResponse(
        agent_key=row.agent_key,
        name=row.name,
        tagline=row.tagline,
        strategy_desc=row.strategy_desc,
        style_desc=row.style_desc,
        llm_config_id=row.llm_config_id,
        methodology_source_id=row.methodology_source_id,
        risk_max_position_pct=float(row.risk_max_position_pct),
        risk_max_total_pct=float(row.risk_max_total_pct),
        risk_max_daily_orders=row.risk_max_daily_orders,
        auto_exec_enabled=row.auto_exec_enabled,
        status=row.status,
        plan_cadence=row.plan_cadence,
        review_cadence=row.review_cadence,
        sort_order=row.sort_order,
        prompt_id=row.prompt_id,
        accent_color=row.accent_color,
        updated_at=row.updated_at,
    )


async def get_agent_view(session: AsyncSession, agent_key: str) -> TradingAgentProfileResponse:
    """读取单个 Agent 的 wire 视图。"""
    return to_view(await get_agent(session, agent_key))


async def list_agent_views(
    session: AsyncSession, *, statuses: list[str] | None = None
) -> list[TradingAgentProfileResponse]:
    """列出 Agent wire 视图。"""
    return [to_view(row) for row in await list_agents(session, statuses=statuses)]


async def update_agent(
    session: AsyncSession, agent_key: str, *, data: TradingAgentProfileUpdateRequest
) -> TradingAgentProfileResponse:
    """保存 Agent 信息/配置（D28：任意状态可写——未上线/停用的 Agent 也可先配置）。

    提交的 llm_config_id 校验存在、启用且用途为 chat，methodology_source_id
    校验存在且启用；status 仅接受 active/disabled（'planned' 为种子初始态，
    API 不可设置——启用即置 active）。

    Raises:
        NotFoundError: agent_key 或关联条目不存在。
        UnprocessableEntityError: 关联条目停用/用途不符。
    """
    row = await get_agent(session, agent_key)
    payload = data.model_dump(exclude_unset=True)

    if "llm_config_id" in payload:
        config_id = payload["llm_config_id"]
        if config_id is not None:
            llm = await session.get(LLMConfig, config_id)
            if llm is None:
                raise NotFoundError(f"LLM 配置 {config_id} 不存在")
            if not llm.is_active:
                raise UnprocessableEntityError(f"LLM 配置 {config_id}（{llm.name}）已停用")
            if llm.purpose != "chat":
                raise UnprocessableEntityError(
                    f"交易 Agent 要求用途为 chat 的模型条目，"
                    f"配置 {config_id}（{llm.name}）用途为 {llm.purpose}"
                )
        row.llm_config_id = config_id

    if "methodology_source_id" in payload:
        source_id = payload["methodology_source_id"]
        if source_id is not None:
            source = await session.get(KbSource, source_id)
            if source is None:
                raise NotFoundError(f"知识库 {source_id} 不存在")
            if not source.enabled:
                raise UnprocessableEntityError(f"知识库 {source_id}（{source.name}）已停用")
        row.methodology_source_id = source_id

    for field in (
        "name",
        "tagline",
        "strategy_desc",
        "style_desc",
        "risk_max_position_pct",
        "risk_max_total_pct",
        "risk_max_daily_orders",
        "auto_exec_enabled",
        "accent_color",
        "status",
        "plan_cadence",
        "review_cadence",
    ):
        if field in payload:
            setattr(row, field, payload[field])

    row.updated_at = utc_now()
    await session.commit()
    logger.info(
        "trading_agent_updated",
        agent_key=agent_key,
        fields=sorted(payload.keys()),
        status=row.status,
    )
    return to_view(row)
