"""自定义技能压缩包解析（预填建议）schema。"""

from pydantic import Field

from app.schemas.base import CamelModel
from app.schemas.skill import CustomSkillSection


class SkillArchiveFileInfo(CamelModel):
    """压缩包内单个文件的索引项。"""

    path: str
    size: int


class SkillAnalyzeResponse(CamelModel):
    """POST /skills/analyze 响应：表单预填建议。"""

    skill_id: str = Field(..., description="kebab-case skill_id 建议")
    label: str
    description: str | None = None
    skill_md: str
    system_prompt: str
    user_prompt_template: str | None = None
    sections: list[CustomSkillSection] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    file_index: list[SkillArchiveFileInfo]
