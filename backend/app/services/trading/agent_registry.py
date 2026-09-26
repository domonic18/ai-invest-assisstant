"""交易 Agent 注册表服务（``trading_agent``，agent-hub-plan.md D21/D29）。

身份/介绍/模型绑定（空 = 平台默认 chat 模型）、方法论知识源绑定（空 = 未启用
方法论基座注入）、风控阈值（批次 8 盘中执行消费）、auto_exec_enabled 总闸全部
按 agent_key 维度维护，改选即时生效（每次构建 agent / 生成计划时现读）。
D29 开放 CRUD：create（创建即 active，技能/人设走共享兜底）、delete（级联清理
其计划/选股/记忆/会话并解绑模拟盘账户）。
"""

import re
from decimal import Decimal
from pathlib import Path

import structlog
import yaml
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.agent_trading import AgentMemory, AgentStockSelection, AgentTradePlan
from app.models.assistant_session import AssistantSession
from app.models.kb import KbSource
from app.models.llm_config import LLMConfig
from app.models.paper_trade import PaperTradeAccount, TradingAgent
from app.schemas.paper_trade import (
    TradingAgentCreateRequest,
    TradingAgentProfileResponse,
    TradingAgentProfileUpdateRequest,
    TradingAgentPromptContent,
    TradingAgentPromptTemplate,
)

logger = structlog.get_logger(__name__)

AGENT_STATUS_ACTIVE = "active"
AGENT_STATUS_PLANNED = "planned"
AGENT_STATUS_DISABLED = "disabled"

AGENT_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")

# 新建 Agent 的保守默认（plan：风控 20/60/10、不开盘中自主执行，绑定账户后再开）
_CREATE_RISK_POSITION_PCT = Decimal("20")
_CREATE_RISK_TOTAL_PCT = Decimal("60")
_CREATE_RISK_DAILY_ORDERS = 10

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "agents"


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
    校验存在且启用；prompt_id 须在模板清单内（D30 开放换绑）；status 仅接受
    active/disabled（'planned' 为种子初始态，API 不可设置——启用即置 active）。

    Raises:
        NotFoundError: agent_key 或关联条目不存在。
        UnprocessableEntityError: 关联条目停用/用途不符/人设模板不存在。
    """
    row = await get_agent(session, agent_key)
    payload = data.model_dump(exclude_unset=True)

    if "prompt_id" in payload and payload["prompt_id"] not in {
        t.prompt_id for t in list_prompt_templates()
    }:
        raise UnprocessableEntityError(f"人设模板 {payload['prompt_id']} 不存在")

    if "llm_config_id" in payload:
        if payload["llm_config_id"] is not None:
            await _validate_llm_config(session, payload["llm_config_id"])
        row.llm_config_id = payload["llm_config_id"]

    if "methodology_source_id" in payload:
        if payload["methodology_source_id"] is not None:
            await _validate_methodology_source(session, payload["methodology_source_id"])
        row.methodology_source_id = payload["methodology_source_id"]

    for field in (
        "name",
        "tagline",
        "strategy_desc",
        "style_desc",
        "prompt_id",
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


async def _validate_llm_config(session: AsyncSession, llm_config_id: int) -> None:
    """模型绑定校验：存在、启用且用途为 chat。

    Raises:
        NotFoundError: 配置不存在。
        UnprocessableEntityError: 停用或用途不符。
    """
    row = await session.get(LLMConfig, llm_config_id)
    if row is None:
        raise NotFoundError(f"模型配置 {llm_config_id} 不存在")
    if not row.is_active or row.purpose != "chat":
        raise UnprocessableEntityError(
            f"模型配置 {llm_config_id}（{row.name}）已停用或用途不是 chat"
        )


async def _validate_methodology_source(
    session: AsyncSession, source_id: int
) -> None:
    """方法论知识源校验：存在且启用。

    Raises:
        NotFoundError: 源不存在。
        UnprocessableEntityError: 源已停用。
    """
    row = await session.get(KbSource, source_id)
    if row is None:
        raise NotFoundError(f"知识库源 {source_id} 不存在")
    if not row.enabled:
        raise UnprocessableEntityError(f"知识库源 {source_id}（{row.name}）已停用")


def list_prompt_templates() -> list[TradingAgentPromptTemplate]:
    """可用会话人设模板清单（prompts/agents/trading_agent_*.yaml 扫描）。

    label 取 YAML name（人设名，如「短线猎手」），缺失时回退 description。
    """
    templates: list[TradingAgentPromptTemplate] = []
    for path in sorted(_PROMPTS_DIR.glob("trading_agent_*.yaml")):
        try:
            meta = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            logger.warning("trading_agent_prompt_template_unreadable", path=str(path))
            continue
        if not isinstance(meta, dict):
            continue
        label = str(meta.get("name") or meta.get("description") or path.stem)
        templates.append(TradingAgentPromptTemplate(prompt_id=path.stem, label=label))
    return templates


def get_prompt_content(prompt_id: str) -> TradingAgentPromptContent:
    """读取会话人设 YAML 原文（配置页只读浏览，D30）。

    prompt_id 经模板清单白名单校验（glob stem，不含路径分隔符），天然免疫
    路径穿越；YAML 缺失/不可读按模板不存在处理。

    Raises:
        NotFoundError: prompt_id 不在模板清单内或 YAML 不可读。
    """
    template = next(
        (t for t in list_prompt_templates() if t.prompt_id == prompt_id), None
    )
    if template is None:
        raise NotFoundError(f"人设模板 {prompt_id} 不存在")
    path = _PROMPTS_DIR / f"{prompt_id}.yaml"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise NotFoundError(f"人设模板 {prompt_id} 文件不可读") from exc
    return TradingAgentPromptContent(
        prompt_id=prompt_id, label=template.label, content=content
    )


async def create_agent(
    session: AsyncSession, *, data: TradingAgentCreateRequest
) -> TradingAgentProfileResponse:
    """新建 Agent（D29：创建即 active 参与调度；技能走 trading-default 共享兜底）。

    agent_key 须匹配 URL 安全约定；重复注册 409；prompt_id 必须在模板清单内；
    模型/方法论绑定校验同 update_agent。风控取保守默认（20/60/10）、不开
    自主执行，绑定账户后再开。

    Raises:
        UnprocessableEntityError: agent_key 非法 / prompt_id 不在模板清单 /
            模型或方法论绑定停用。
        ConflictError: agent_key 已注册。
    """
    if not AGENT_KEY_PATTERN.fullmatch(data.agent_key):
        raise UnprocessableEntityError(
            "agent_key 须为 2-32 位小写字母/数字/连字符，且以字母或数字开头"
        )
    if await session.get(TradingAgent, data.agent_key) is not None:
        raise ConflictError(f"交易 Agent {data.agent_key} 已存在")
    if data.prompt_id not in {t.prompt_id for t in list_prompt_templates()}:
        raise UnprocessableEntityError(f"人设模板 {data.prompt_id} 不存在")
    if data.llm_config_id is not None:
        await _validate_llm_config(session, data.llm_config_id)
    if data.methodology_source_id is not None:
        await _validate_methodology_source(session, data.methodology_source_id)

    max_sort = int(
        await session.scalar(select(func.max(TradingAgent.sort_order))) or 0
    )
    row = TradingAgent(
        agent_key=data.agent_key,
        name=data.name,
        tagline=data.tagline or "",
        strategy_desc=data.strategy_desc or "",
        style_desc=data.style_desc or "",
        llm_config_id=data.llm_config_id,
        methodology_source_id=data.methodology_source_id,
        prompt_id=data.prompt_id,
        accent_color=data.accent_color or "#38bdf8",
        plan_cadence=data.plan_cadence or "daily",
        review_cadence=data.review_cadence or "daily",
        risk_max_position_pct=_CREATE_RISK_POSITION_PCT,
        risk_max_total_pct=_CREATE_RISK_TOTAL_PCT,
        risk_max_daily_orders=_CREATE_RISK_DAILY_ORDERS,
        auto_exec_enabled=False,
        status=AGENT_STATUS_ACTIVE,
        sort_order=max_sort + 1,
    )
    session.add(row)
    await session.commit()
    logger.info("trading_agent_created", agent_key=row.agent_key, prompt_id=row.prompt_id)
    return to_view(row)


async def delete_agent(session: AsyncSession, agent_key: str) -> int:
    """删除 Agent 并级联清理其数据（D29；注册行本身 last）。

    顺序：解绑模拟盘账户（保留账户本体）→ 删计划/选股/记忆 → 删会话
    （先逐条删 LangGraph checkpoint 线程再删业务行，user_watchlist_group 由
    DB CASCADE）→ 删注册行。

    Raises:
        NotFoundError: agent_key 未注册。
    """
    row = await get_agent(session, agent_key)

    await session.execute(
        update(PaperTradeAccount)
        .where(PaperTradeAccount.agent_key == agent_key)
        .values(agent_key=None)
    )
    for model in (AgentStockSelection, AgentTradePlan, AgentMemory):
        await session.execute(delete(model).where(model.agent_key == agent_key))

    from app.agent.runtime.assistant_agent import get_checkpointer

    thread_ids = list(
        await session.scalars(
            select(AssistantSession.id).where(AssistantSession.agent_type == agent_key)
        )
    )
    if thread_ids:
        checkpointer = await get_checkpointer()
        for thread_id in thread_ids:
            await checkpointer.adelete_thread(str(thread_id))
        await session.execute(
            delete(AssistantSession).where(AssistantSession.agent_type == agent_key)
        )

    await session.delete(row)
    await session.commit()
    logger.info(
        "trading_agent_deleted", agent_key=agent_key, name=row.name, sessions=len(thread_ids)
    )
    return len(thread_ids)
