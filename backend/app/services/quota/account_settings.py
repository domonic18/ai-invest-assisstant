"""运行时全局设置（system_setting KV）读写。

管理端可变的设置走 DB 而非 config.py；读取以 DEFAULT_SETTINGS 兜底，
行缺失或值非法时返回缺省值（缺省值与迁移回填共用同一真相源）。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_quota import SystemSetting
from app.services.quota.constants import (
    DEFAULT_SETTINGS,
    SETTING_ADMIN_EXEMPT,
    SETTING_DEFAULT_QUOTA_TOKENS,
    SETTING_PENDING_EXPIRE_DAYS,
)

_SYSTEM_SETTING_KEYS = tuple(DEFAULT_SETTINGS.keys())


async def _read_value(session: AsyncSession, key: str) -> Any:
    row = await session.get(SystemSetting, key)
    if row is None or row.value is None:
        return DEFAULT_SETTINGS.get(key)
    return row.value


async def get_setting(session: AsyncSession, key: str) -> Any:
    """读取单个全局设置（缺失回退缺省值）。"""
    if key not in _SYSTEM_SETTING_KEYS:
        raise KeyError(f"未知全局设置键: {key}")
    return await _read_value(session, key)


async def get_default_quota_tokens(session: AsyncSession) -> int:
    """新用户审批通过的默认一次性配额（tokens）。"""
    value = await _read_value(session, SETTING_DEFAULT_QUOTA_TOKENS)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(DEFAULT_SETTINGS[SETTING_DEFAULT_QUOTA_TOKENS])


async def get_pending_expire_days(session: AsyncSession) -> int:
    """待审申请过期天数（超期惰性清理）。"""
    value = await _read_value(session, SETTING_PENDING_EXPIRE_DAYS)
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return int(DEFAULT_SETTINGS[SETTING_PENDING_EXPIRE_DAYS])


async def get_admin_exempt(session: AsyncSession) -> bool:
    """admin 角色是否豁免配额（豁免仍计量）。"""
    value = await _read_value(session, SETTING_ADMIN_EXEMPT)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(DEFAULT_SETTINGS[SETTING_ADMIN_EXEMPT])


async def list_settings(session: AsyncSession) -> dict[str, Any]:
    """读全部账号治理设置（管理端展示）。"""
    rows = (
        (await session.execute(select(SystemSetting))).scalars().all()
    )
    stored = {row.key: row.value for row in rows}
    return {key: stored.get(key, DEFAULT_SETTINGS[key]) for key in _SYSTEM_SETTING_KEYS}


async def update_setting(
    session: AsyncSession, key: str, value: Any, updated_by: int
) -> None:
    """写入单个全局设置（upsert；事务由调用方提交）。"""
    if key not in _SYSTEM_SETTING_KEYS:
        raise KeyError(f"未知全局设置键: {key}")
    row = await session.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(key=key, value=value, updated_by=updated_by)
        session.add(row)
    else:
        row.value = value
        row.updated_by = updated_by
