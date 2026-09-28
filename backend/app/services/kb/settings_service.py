"""知识库域设置服务（F-KB）：域参数与模型角色槽位的读写校验（arch/09 §2）。

四类管线模型角色（清洗/抽取 = chat、视觉 = vision 用途或视觉能力条目、
嵌入 = embedding）全部落 ``llm_config`` 条目，``kb_settings`` 持槽位引用
——代码不硬编码模型名。
校验双侧生效：保存时校验槽位条目存在且匹配角色要求；读取解析时再次校验
（条目被停用/改用途/去能力后立即显式失败，管线任务 FAILED 归因而非静默走
错模型）。
"""

from typing import Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.models.kb import KbSettings
from app.models.llm_config import LLMConfig
from app.schemas.kb import KbSettingsResponse, KbSettingsUpdateRequest

logger = structlog.get_logger(__name__)

KbModelRole = Literal["embedding", "clean", "extract", "vision"]

#: 角色 → (kb_settings 字段名, 要求的 llm_config.purpose)
ROLE_REQUIREMENTS: dict[KbModelRole, tuple[str, str]] = {
    "embedding": ("embedding_config_id", "embedding"),
    "clean": ("clean_model_id", "chat"),
    "extract": ("extract_model_id", "chat"),
    "vision": ("vision_model_id", "vision"),
}


async def get_settings_row(session: AsyncSession) -> KbSettings:
    """读取设置单行（迁移已 seed id=1；缺失时兜底创建）。"""
    row = await session.get(KbSettings, 1)
    if row is None:
        row = KbSettings(id=1)
        session.add(row)
        await session.commit()
    return row


def _to_view(row: KbSettings) -> KbSettingsResponse:
    return KbSettingsResponse(
        hotwords=list(row.hotwords or []),
        segment_max_seconds=row.segment_max_seconds,
        asr_concurrency=row.asr_concurrency,
        top_k=row.top_k,
        auto_approve_points=row.auto_approve_points,
        unit_prices=dict(row.unit_prices or {}),
        embedding_config_id=row.embedding_config_id,
        clean_model_id=row.clean_model_id,
        extract_model_id=row.extract_model_id,
        vision_model_id=row.vision_model_id,
        authorized_user_ids=list(row.authorized_user_ids or []),
        updated_at=row.updated_at,
    )


async def get_settings_view(session: AsyncSession) -> KbSettingsResponse:
    """读取设置的脱敏视图（wire camelCase）。"""
    return _to_view(await get_settings_row(session))


def _role_accepts(role: KbModelRole, row: LLMConfig) -> bool:
    """条目是否满足角色要求。

    视觉槽接受「vision 用途」或「chat 用途且标记视觉能力」（
    ``extra.capabilities.vision``）的条目——后者与用户侧截图识别
    ``resolve_vision_llm`` 的能力语义对齐；其余角色严格 purpose 匹配。
    """
    if role == "vision":
        if row.purpose == "vision":
            return True
        capabilities = (row.extra or {}).get("capabilities") or {}
        return row.purpose == "chat" and capabilities.get("vision") is True
    return row.purpose == ROLE_REQUIREMENTS[role][1]


def _role_rejection_detail(role: KbModelRole, config_id: int, row: LLMConfig) -> str:
    """槽位校验失败的提示文案（视觉槽按能力语义表述）。"""
    if role == "vision":
        return (
            f"角色 {role} 须为开启视觉能力的启用条目"
            "（vision 用途，或对话模型勾选「视觉能力」），"
            f"配置 {config_id}（{row.name}）用途为 {row.purpose} 且未开启视觉能力"
        )
    _field, expected_purpose = ROLE_REQUIREMENTS[role]
    return (
        f"角色 {role} 要求用途为 {expected_purpose} 的模型条目，"
        f"配置 {config_id}（{row.name}）用途为 {row.purpose}"
    )


async def _validate_role_slot(
    session: AsyncSession, *, role: KbModelRole, config_id: int
) -> None:
    """校验槽位指向的 llm_config 条目存在、启用且匹配角色要求。"""
    row = await session.get(LLMConfig, config_id)
    if row is None:
        raise NotFoundError(f"角色 {role} 指向的 LLM 配置 {config_id} 不存在")
    if not row.is_active:
        raise UnprocessableEntityError(f"角色 {role} 指向的 LLM 配置 {config_id} 已停用")
    if not _role_accepts(role, row):
        raise UnprocessableEntityError(_role_rejection_detail(role, config_id, row))


async def update_settings(
    session: AsyncSession,
    *,
    admin_id: int,
    data: KbSettingsUpdateRequest,
) -> KbSettingsResponse:
    """保存设置；提交的模型角色槽位逐项校验角色要求（含视觉能力语义）。

    Raises:
        NotFoundError: 槽位指向的 LLM 配置不存在。
        UnprocessableEntityError: 槽位条目停用或不满足角色要求。
    """
    row = await get_settings_row(session)
    payload = data.model_dump(exclude_unset=True)

    role_fields = {field for field, _ in ROLE_REQUIREMENTS.values()}
    for field_name in role_fields & payload.keys():
        config_id = payload[field_name]
        role = next(r for r, (f, _) in ROLE_REQUIREMENTS.items() if f == field_name)
        if config_id is not None:
            await _validate_role_slot(session, role=role, config_id=config_id)
        setattr(row, field_name, config_id)

    for field_name in ("hotwords", "segment_max_seconds", "asr_concurrency",
                       "top_k", "auto_approve_points", "unit_prices",
                       "authorized_user_ids"):
        if field_name in payload:
            setattr(row, field_name, payload[field_name])

    row.updated_by = admin_id
    row.updated_at = utc_now()
    await session.commit()
    logger.info("kb_settings_updated", admin_id=admin_id, fields=sorted(payload.keys()))
    return _to_view(row)


async def resolve_role_model(
    session: AsyncSession, role: KbModelRole
) -> LLMConfig:
    """解析角色槽位指向的 llm_config 条目（管线调用前统一入口）。

    Raises:
        UnprocessableEntityError: 角色未配置，或条目停用/用途能力被改为不匹配
            （保存后再变更的场景，读取侧二次校验兜底）。
    """
    row = await get_settings_row(session)
    field_name, _expected_purpose = ROLE_REQUIREMENTS[role]
    config_id: int | None = getattr(row, field_name)
    if config_id is None:
        raise UnprocessableEntityError(
            f"知识库设置未配置 {role} 模型角色，请在后台「知识库设置」中选择"
        )
    config = await session.get(LLMConfig, config_id)
    if config is None or not config.is_active or not _role_accepts(role, config):
        raise UnprocessableEntityError(
            f"角色 {role} 指向的 LLM 配置 {config_id} 不可用"
            "（不存在/停用/不满足角色要求），请检查知识库设置"
        )
    return config
