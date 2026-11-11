"""AI 任务级模型绑定：任务槽位注册表、解析与管理端读写。

任务槽位是模型选择的**唯一选择点**（2026-11-11 重构）：每槽位绑定
主模型（必填）与可选备用，主模型冷却/失效时切备，主备皆不可用
fail loud 抛 ``LLMConfigNotConfiguredError``（任务失败可见，不再静默
降级默认——默认概念已消灭，llm_config 只是纯注册表）。

槽位清单 ``TASK_SLOTS`` 是 catalog 唯一真相源（API/前端不硬编码），
每槽位声明 ``purpose``（绑定校验按槽位用途匹配，decision 槽只收
decision 条目）。绑定行引用有效性写侧校验。
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
    LLMConfigNotConfiguredError,
    LLMConfigNotFoundError,
    ResolvedLLMConfig,
    resolve_llm_by_id,
)

logger = structlog.get_logger()


async def _get_binding(session: AsyncSession, task_key: str) -> LLMTaskBinding | None:
    """按 task_key（唯一键，非主键）取绑定行。"""
    return (
        await session.execute(
            select(LLMTaskBinding).where(LLMTaskBinding.task_key == task_key)
        )
    ).scalar_one_or_none()


@dataclass(frozen=True)
class TaskSlotSpec:
    """任务槽位声明（key/中文标签/一句话说明/条目用途约束）。"""

    key: TASK_KEY
    label: str
    description: str
    purpose: str = "chat"


#: 任务槽位注册表（catalog 唯一真相源）。调整清单只改这里；
#: schemas.llm_config.TASK_KEY Literal 集合由单测钉死与本表一致。
TASK_SLOTS: dict[str, TaskSlotSpec] = {
    spec.key: spec
    for spec in (
        TaskSlotSpec(
            "assistant_chat",
            "助手对话",
            "侧边栏助手、工具二次生成与页面手动分析的系统出口（用户 BYOK 优先）",
        ),
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
        TaskSlotSpec(
            "decision",
            "判断模型",
            "交易判断模型（systemone 协议，D23）",
            purpose="decision",
        ),
    )
}


async def resolve_task_llm(
    session: AsyncSession, task_key: str
) -> ResolvedLLMConfig:
    """按任务槽位解析 LLM 出口：主健康且有效走主，否则备用，皆不可用抛错。

    Raises:
        LLMConfigNotConfiguredError: 槽位未知 / 未绑定主模型 / 主备皆不可用。
    """
    spec = TASK_SLOTS.get(task_key)
    if spec is None:
        raise LLMConfigNotConfiguredError(f"未知任务槽位：{task_key}")
    binding = await _get_binding(session, task_key)
    if binding is None:
        raise LLMConfigNotConfiguredError(
            f"任务槽位「{spec.label}」未绑定主模型，请在后台「任务模型」页配置"
        )
    try:
        return await resolve_llm_by_id(
            session,
            binding.config_id,
            backup_config_id=binding.backup_config_id,
        )
    except LLMConfigNotFoundError as exc:
        raise LLMConfigNotConfiguredError(
            f"任务槽位「{spec.label}」主备模型皆不可用：{exc}"
        ) from exc


async def get_task_bindings_view(session: AsyncSession) -> list[TaskBindingSlotResponse]:
    """槽位目录 × 绑定行的全量视图（注册表顺序，供列表 UI）。"""
    rows = (await session.execute(select(LLMTaskBinding))).scalars().all()
    bindings = {row.task_key: row for row in rows}
    config_ids = {row.config_id for row in bindings.values()}
    config_ids.update(
        row.backup_config_id for row in bindings.values() if row.backup_config_id
    )
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
        backup = (
            configs.get(binding.backup_config_id)
            if binding is not None and binding.backup_config_id
            else None
        )
        view.append(
            TaskBindingSlotResponse(
                task_key=spec.key,
                label=spec.label,
                description=spec.description,
                purpose=spec.purpose,
                config_id=binding.config_id if binding is not None else None,
                config_name=config.name if config is not None else None,
                model_name=config.model_name if config is not None else None,
                backup_config_id=(
                    binding.backup_config_id if binding is not None else None
                ),
                backup_config_name=backup.name if backup is not None else None,
                backup_model_name=backup.model_name if backup is not None else None,
                updated_at=binding.updated_at if binding is not None else None,
            )
        )
    return view


async def _validate_slot_reference(
    session: AsyncSession,
    *,
    task_key: str,
    purpose: str,
    config_id: int,
    role: str,
) -> None:
    """校验槽位引用的条目：存在、启用、用途匹配槽位 purpose。"""
    row = await session.get(LLMConfig, config_id)
    if row is None:
        raise UnprocessableEntityError(
            f"任务 {task_key} 的{role}指向的 LLM 配置 {config_id} 不存在"
        )
    if not row.is_active:
        raise UnprocessableEntityError(
            f"任务 {task_key} 的{role}指向的 LLM 配置 {config_id} 已停用"
        )
    if row.purpose != purpose:
        raise UnprocessableEntityError(
            f"任务 {task_key} 要求用途为 {purpose} 的模型条目，"
            f"配置 {config_id}（{row.name}）用途为 {row.purpose}"
        )


async def replace_task_bindings(
    session: AsyncSession,
    *,
    admin_id: int,
    data: TaskBindingReplaceRequest,
) -> list[TaskBindingSlotResponse]:
    """整表单全量替换绑定：主必填、备可空，逐槽位 upsert，一事务提交。

    Raises:
        UnprocessableEntityError: task_key 不在注册表 / 重复提交 /
            主模型缺失或指向的配置不存在、停用、用途不匹配 /
            备用等于主或指向的配置不可用。
    """
    seen: set[str] = set()
    for item in data.bindings:
        spec = TASK_SLOTS.get(item.task_key)
        if spec is None:
            raise UnprocessableEntityError(f"未知任务槽位：{item.task_key}")
        if item.task_key in seen:
            raise UnprocessableEntityError(f"任务槽位重复提交：{item.task_key}")
        seen.add(item.task_key)
        if item.config_id is None:
            raise UnprocessableEntityError(
                f"任务 {item.task_key} 必须绑定主模型（解绑不再合法）"
            )
        await _validate_slot_reference(
            session,
            task_key=item.task_key,
            purpose=spec.purpose,
            config_id=item.config_id,
            role="主模型",
        )
        if item.backup_config_id is not None:
            if item.backup_config_id == item.config_id:
                raise UnprocessableEntityError(
                    f"任务 {item.task_key} 的备用模型不能与主模型相同"
                )
            await _validate_slot_reference(
                session,
                task_key=item.task_key,
                purpose=spec.purpose,
                config_id=item.backup_config_id,
                role="备用模型",
            )

    existing = (await session.execute(select(LLMTaskBinding))).scalars().all()
    existing_by_key = {row.task_key: row for row in existing}
    submitted = {item.task_key: item for item in data.bindings}

    for task_key, item in submitted.items():
        row = existing_by_key.get(task_key)
        if row is None:
            session.add(
                LLMTaskBinding(
                    task_key=task_key,
                    config_id=item.config_id,
                    backup_config_id=item.backup_config_id,
                    updated_by=admin_id,
                )
            )
        else:
            row.config_id = item.config_id
            row.backup_config_id = item.backup_config_id
            row.updated_by = admin_id

    await session.commit()
    logger.info(
        "task_bindings_replaced",
        admin_id=admin_id,
        slots=sorted(submitted),
        with_backup=sorted(
            k for k, v in submitted.items() if v.backup_config_id is not None
        ),
    )
    return await get_task_bindings_view(session)
