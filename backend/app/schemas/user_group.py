"""用户组 Pydantic schemas。"""

from datetime import datetime

from pydantic import Field, field_validator

from app.constants.features import FEATURE_KEYS, FEATURE_LABELS
from app.schemas.base import CamelModel


def _check_permissions(value: list[str]) -> list[str]:
    unknown = [k for k in value if k not in FEATURE_KEYS]
    if unknown:
        raise ValueError(f"未知功能模块 key：{', '.join(unknown)}")
    return value


class FeatureCatalogItem(CamelModel):
    """功能模块目录项。"""

    key: str
    label: str


class UserGroupCreate(CamelModel):
    """创建用户组请求。"""

    name: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=200)
    permissions: list[str] = Field(default_factory=list)

    _valid_permissions = field_validator("permissions")(_check_permissions)


class UserGroupUpdate(CamelModel):
    """更新用户组请求（仅声明字段生效）。"""

    name: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = Field(None, max_length=200)
    permissions: list[str] | None = None
    is_active: bool | None = None

    _valid_permissions = field_validator("permissions")(_check_permissions)


class UserGroupResponse(CamelModel):
    """用户组响应模型。"""

    id: int
    name: str
    description: str | None = None
    permissions: list[str] = []
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
