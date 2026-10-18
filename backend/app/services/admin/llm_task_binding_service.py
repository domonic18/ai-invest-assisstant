"""AI 任务级模型绑定：任务槽位注册表、解析与管理端读写。

定时 AI 任务默认共用系统默认对话模型（主模型 + ``backup_config_id`` 主备链）；
本模块提供按任务槽位绑定独立 llm_config 条目的能力——轻任务可绑廉价模型、
重任务绑强模型。槽位清单 ``TASK_SLOTS`` 是 catalog 唯一真相源（API/前端不硬编码）；
绑定行的引用有效性（存在/启用/purpose=chat）写侧校验，读侧失效时
降级系统默认并告警（未绑定本就是合法态，调度任务可用性优先）。
"""

from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnprocessableEntityError
from app.models.llm_config import LLMConfig
from app.models.llm_task_binding import LLMTaskBinding
from app.schemas.llm_config import (
    TASK_KEY,
    TaskBindingReplaceRequest,
    TaskBindingSlotResponse,
)
from app.services.admin.llm_config_service import (
    ResolvedLLMConfig,
    resolve_default_llm,
    resolve_llm_by_id,
)


async def _get_binding(session: AsyncSession, task_key: str) -> LLMTaskBinding | None:
    """按 task_key（唯一键，非主键）取绑定行。"""
    return (
        await session.execute(
            select(LLMTaskBinding).where(LLMTaskBinding.task_key == task_key)
        )
    ).scalar_one_or_none()

logger = structlog.get_logger()


@dataclass(frozen=True)
class TaskSlotSpec:
    """任务槽位声明（key/中文标签/一句话说明）。"""

    key: TASK_KEY
    label: str
    description: str


#: 任务槽位注册表（catalog 唯一真相源）。调整清单只改这里；
#: schemas.llm_config.TASK_KEY Literal 集合由单测钉死与本表一致。
TASK_SLOTS: dict[str, TaskSlotSpec] = {
    spec.key: spec
    for spec in (
        TaskSlotSpec("news_score", "新闻重要度分级", "电报快讯 AI 重要度打分（高频轻任务）"),
        TaskSlotSpec("social_sentiment", "大V情绪判断", "社媒作品情绪 LLM 判断（高频轻任务）"),
        TaskSlotSpec("news_storyline", "事件故事线", "资讯事件故事线生成"),
        TaskSlotSpec("news_topic", "热点主题榜", "热点主题聚合榜单"),
        TaskSlotSpec("market_daily_review", "每日大盘复盘", "大盘每日复盘六分区生成（重任务）"),
        TaskSlotSpec("sector_anomaly", "板块异动归因", "板块异动检测的 AI 归因（重任务）"),
        TaskSlotSpec("stock_anomaly", "个股异动归因", "个股异动检测的 AI 归因（重任务）"),
        TaskSlotSpec("stock_daily_analysis", "自选股每日分析", "自选股 AI 每日复盘（重任务）"),
        TaskSlotSpec("limit_up_review", "涨停归因", "涨停池 AI 归因（重任务）"),
        TaskSlotSpec("chain_refresh", "产业链图谱刷新", "产业链图谱周度 AI 刷新"),
    )
}


async def resolve_task_llm(
    session: AsyncSession, task_key: str
) -> ResolvedLLMConfig:
    """按任务槽位解析 LLM 出口：绑定条目优先，未绑定/失效降级系统默认。

    绑定生效时走 ``resolve_llm_by_id``（健康门 + 绑定条目自身主备链）；
    绑定条目事后失效（删除/停用/用途变更）降级默认并告警。
    """
    if task_key not in TASK_SLOTS:
        logger.warning("task_binding_unknown_key", task_key=task_key)
        return await resolve_default_llm(session)
    binding = await _get_binding(session, task_key)
    if binding is None:
        return await resolve_default_llm(session)
    try:
        return await resolve_llm_by_id(session, binding.config_id)
    except Exception as exc:
        logger.warning(
            "task_binding_degraded_to_default",
            task_key=task_key,
            config_id=binding.config_id,
            error=str(exc),
        )
        return await resolve_default_llm(session)


async def resolve_task_config_id(session: AsyncSession, task_key: str) -> int | None:
    """按任务槽位返回绑定 llm_config 条目 id；未绑定或条目失效返回 None。

    供 ``run_structured(task_key=...)`` 回填 ``config_id``：命中后由
    ``resolve_llm_by_id`` 走健康门与主备链，语义与显式 config_id 路径一致。
    """
    if task_key not in TASK_SLOTS:
        logger.warning("task_binding_unknown_key", task_key=task_key)
        return None
    binding = await _get_binding(session, task_key)
    if binding is None:
        return None
    row = await session.get(LLMConfig, binding.config_id)
    if row is None or not row.is_active or row.purpose != "chat":
        logger.warning(
            "task_binding_config_invalid",
            task_key=task_key,
            config_id=binding.config_id,
        )
        return None
    return binding.config_id


async def get_task_bindings_view(session: AsyncSession) -> list[TaskBindingSlotResponse]:
    """槽位目录 × 绑定行的全量视图（注册表顺序，供列表 UI）。"""
    rows = (await session.execute(select(LLMTaskBinding))).scalars().all()
    bindings = {row.task_key: row for row in rows}
    config_ids = {row.config_id for row in bindings.values()}
    configs: dict[int, LLMConfig] = {}
    if config_ids:
        found = (
            await session.execute(select(LLMConfig).where(LLMConfig.id.in_(config_ids)))
        ).scalars().all()
        configs = {config.id: config for config in found}

    view: list[TaskBindingSlotResponse] = []
    for spec in TASK_SLOTS.values():
        binding = bindings.get(spec.key)
        config = configs.get(binding.config_id) if binding is not None else None
        view.append(
            TaskBindingSlotResponse(
                task_key=spec.key,
                label=spec.label,
                description=spec.description,
                config_id=binding.config_id if binding is not None else None,
                config_name=config.name if config is not None else None,
                model_name=config.model_name if config is not None else None,
                updated_at=binding.updated_at if binding is not None else None,
            )
        )
    return view


async def replace_task_bindings(
    session: AsyncSession,
    *,
    admin_id: int,
    data: TaskBindingReplaceRequest,
) -> list[TaskBindingSlotResponse]:
    """整表单全量替换绑定：config_id 非空 upsert、空删行，一事务提交。

    Raises:
        UnprocessableEntityError: task_key 不在注册表 / 重复提交 /
            指向的配置不存在、停用或用途非 chat。
    """
    seen: set[str] = set()
    for item in data.bindings:
        if item.task_key not in TASK_SLOTS:
            raise UnprocessableEntityError(f"未知任务槽位：{item.task_key}")
        if item.task_key in seen:
            raise UnprocessableEntityError(f"任务槽位重复提交：{item.task_key}")
        seen.add(item.task_key)
        if item.config_id is None:
            continue
        row = await session.get(LLMConfig, item.config_id)
        if row is None:
            raise UnprocessableEntityError(
                f"任务 {item.task_key} 指向的 LLM 配置 {item.config_id} 不存在"
            )
        if not row.is_active:
            raise UnprocessableEntityError(
                f"任务 {item.task_key} 指向的 LLM 配置 {item.config_id} 已停用"
            )
        if row.purpose != "chat":
            raise UnprocessableEntityError(
                f"任务 {item.task_key} 要求用途为 chat 的模型条目，"
                f"配置 {item.config_id}（{row.name}）用途为 {row.purpose}"
            )

    existing = (await session.execute(select(LLMTaskBinding))).scalars().all()
    existing_by_key = {row.task_key: row for row in existing}
    submitted = {item.task_key: item.config_id for item in data.bindings}

    for task_key, config_id in submitted.items():
        if config_id is None:
            if task_key in existing_by_key:
                await session.delete(existing_by_key[task_key])
            continue
        row = existing_by_key.get(task_key)
        if row is None:
            session.add(
                LLMTaskBinding(
                    task_key=task_key, config_id=config_id, updated_by=admin_id
                )
            )
        else:
            row.config_id = config_id
            row.updated_by = admin_id

    await session.commit()
    logger.info(
        "task_bindings_replaced",
        admin_id=admin_id,
        bound=sorted(k for k, v in submitted.items() if v is not None),
        unbound=sorted(k for k, v in submitted.items() if v is None),
    )
    return await get_task_bindings_view(session)
