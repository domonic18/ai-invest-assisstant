"""权限解析：用户 → 功能模块权限集合。

admin 恒为全量；用户组存在且启用时取组权限（JSONB 数组）；未分组或组停用
为空集（默认受限）。组关系 joined 加载，解析无额外 IO。
"""

from app.constants.features import FEATURE_KEYS
from app.models.user import User
from app.models.user_group import UserGroup
from app.schemas.user import UserResponse


async def resolve_permissions(user: User) -> set[str]:
    """解析用户的可见功能模块 key 集合。"""
    if user.role == "admin":
        return set(FEATURE_KEYS)

    # getattr：测试桩用户（鸭子类型）可能未携带 group，视为未分组受限
    group: UserGroup | None = getattr(user, "group", None)
    if group is None or not group.is_active:
        return set()
    return {str(k) for k in group.permissions or []}


async def build_user_response(user: User) -> UserResponse:
    """构造带权限与组名的用户响应（login/me 等出口统一走此函数）。"""
    resp = UserResponse.model_validate(user)
    resp.permissions = sorted(await resolve_permissions(user))
    group = getattr(user, "group", None)
    resp.group_name = group.name if group is not None else None
    return resp
