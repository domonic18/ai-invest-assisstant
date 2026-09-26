"""交易 Agent 配置服务（单例 ``trading_agent_config``，D19）。

LLM 绑定（空 = 平台默认 chat 模型）、方法论知识源绑定（空 = 未启用方法论
基座注入）、风控阈值（批次 8 盘中执行消费）、auto_exec_enabled 总闸全部
DB 化，改选即时生效（每次构建 agent / 生成计划时现读）。
kb_settings 单行先例：迁移 seed id=1，读取缺失时兜底创建。
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.kb import KbSource
from app.models.llm_config import LLMConfig
from app.models.paper_trade import TradingAgentConfig
from app.schemas.paper_trade import (
    TradingAgentConfigResponse,
    TradingAgentConfigUpdateRequest,
)

logger = structlog.get_logger(__name__)

CONFIG_ID = 1


async def get_config_row(session: AsyncSession) -> TradingAgentConfig:
    """读取配置单行（迁移已 seed id=1；缺失时兜底创建）。"""
    row = await session.get(TradingAgentConfig, CONFIG_ID)
    if row is None:
        row = TradingAgentConfig(id=CONFIG_ID)
        session.add(row)
        await session.commit()
    return row


def _to_view(row: TradingAgentConfig) -> TradingAgentConfigResponse:
    return TradingAgentConfigResponse(
        llm_config_id=row.llm_config_id,
        methodology_source_id=row.methodology_source_id,
        risk_max_position_pct=float(row.risk_max_position_pct),
        risk_max_total_pct=float(row.risk_max_total_pct),
        risk_max_daily_orders=row.risk_max_daily_orders,
        auto_exec_enabled=row.auto_exec_enabled,
        updated_at=row.updated_at,
    )


async def get_config_view(session: AsyncSession) -> TradingAgentConfigResponse:
    """读取配置的 wire 视图（camelCase）。"""
    return _to_view(await get_config_row(session))


async def update_config(
    session: AsyncSession, *, data: TradingAgentConfigUpdateRequest
) -> TradingAgentConfigResponse:
    """保存配置；提交的 llm_config_id 校验存在、启用且用途为 chat，
    methodology_source_id 校验存在且启用。

    Raises:
        NotFoundError: llm_config_id / methodology_source_id 指向的条目不存在。
        UnprocessableEntityError: 条目停用或 llm_config_id 用途不是 chat。
    """
    row = await get_config_row(session)
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
        "risk_max_position_pct",
        "risk_max_total_pct",
        "risk_max_daily_orders",
        "auto_exec_enabled",
    ):
        if field in payload:
            setattr(row, field, payload[field])

    row.updated_at = utc_now()
    await session.commit()
    logger.info("trading_agent_config_updated", fields=sorted(payload.keys()))
    return _to_view(row)
