"""Skill 广场与用户技能管理的 Pydantic schemas。"""

from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class CustomSkillSection(CamelModel):
    """custom skill 的结构化输出分区声明。"""

    key: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=100)
    requirements: str = ""


class CustomSkillDefinition(CamelModel):
    """custom skill 定义（存 ``skill.custom_definition`` JSONB）。"""

    skill_md: str = Field(..., min_length=1)
    system_prompt: str = Field(..., min_length=1)
    user_prompt_template: str | None = None
    sections: list[CustomSkillSection] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)


class SkillItem(CamelModel):
    """广场/我的技能列表项。"""

    skill_id: str
    label: str
    kind: str
    is_builtin: bool
    published: bool
    installed: bool = False
    enabled: bool | None = None
    description: str | None = None


class SkillSquareResponse(CamelModel):
    """技能广场 + 我的技能分组响应。"""

    available: list[SkillItem]
    mine: list[SkillItem]


class CustomSkillCreateRequest(CamelModel):
    """创建 custom skill 请求。"""

    skill_id: str = Field(
        ..., pattern=r"^[a-z0-9][a-z0-9-]{2,99}$", description="kebab-case，全局唯一"
    )
    label: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    custom_definition: CustomSkillDefinition


class CustomSkillUpdateRequest(CamelModel):
    """更新 custom skill 请求（None 字段不变）。"""

    label: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    custom_definition: CustomSkillDefinition | None = None


class SkillResponse(CamelModel):
    """技能详情响应（custom 含定义，builtin 不含）。

    ``custom_definition`` 类型化输出：JSONB 内部 snake_case，wire 层
    经 CamelModel 统一 camelCase。
    """

    skill_id: str
    label: str
    kind: str
    is_builtin: bool
    published: bool
    description: str | None
    owner_user_id: int | None
    version: int
    custom_definition: CustomSkillDefinition | None = None
    created_at: datetime
    updated_at: datetime


class UserSkillResponse(CamelModel):
    """安装/卸载操作后的用户技能状态。"""

    skill_id: str
    installed: bool
    enabled: bool


class SkillFile(CamelModel):
    """技能包内单个文件（builtin 读镜像目录，custom 由配置合成）。"""

    path: str
    size: int
    content: str


class SkillFilesResponse(CamelModel):
    """技能包文件清单响应。

    ``synthetic=True`` 表示文件由 DB ``custom_definition`` 合成（虚拟文件），
    并非镜像内真实路径。
    """

    skill_id: str
    is_builtin: bool
    synthetic: bool
    files: list[SkillFile]
