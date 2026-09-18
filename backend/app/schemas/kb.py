"""知识库域 Pydantic schemas（F-KB）。

两个分层：

- **LLM 输出契约**（``KbPointDraft``/``KbExtractionResult``/``EpisodeOutline``/
  ``ChapterTreeDraft``/``ImageUnderstanding``）：裸 BaseModel、全字段 required、
  禁带默认值（默认值不进 JSON Schema required，LLM 会静默省略——项目铁律；
  无数据由模型显式输出空串/空列表/null）。契约由
  ``tests/unit/services/test_structured_output_contract.py`` 钉死。
- **wire 契约**（``KbSettings*``）：CamelModel，与 ``shared/types/kb.ts``
  单一真相源对齐。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.base import CamelModel

# ---------------------------------------------------------------------------
# LLM 输出契约（结构化抽取）
# ---------------------------------------------------------------------------

KbPointTypeLiteral = Literal["concept", "theorem", "method", "discipline", "case"]


class KbPointDraft(BaseModel):
    """单条知识点草稿（抽取窗口内产出，定位交给服务层校验）。"""

    title: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    point_type: KbPointTypeLiteral
    term_definition: str | None
    applicable_scene: str | None
    excerpt: str = Field(..., min_length=1)
    start_ms: int | None
    end_ms: int | None
    related_titles: list[str]


class KbExtractionResult(BaseModel):
    """一次抽取窗口的完整输出。"""

    points: list[KbPointDraft]


class EpisodeOutlinePoint(BaseModel):
    """单集大纲条目。"""

    title: str = Field(..., min_length=1)
    summary: str


class EpisodeOutline(BaseModel):
    """单集大纲（章节推断第一步）。"""

    episode_no: int
    points: list[EpisodeOutlinePoint]


class ChapterNodeDraft(BaseModel):
    """目录树节点草稿（节点 id 由服务层生成，保证稳定）。"""

    title: str = Field(..., min_length=1)
    children: list["ChapterNodeDraft"]


class ChapterTreeDraft(BaseModel):
    """跨集合并后的目录树草稿。"""

    nodes: list[ChapterNodeDraft]


class ImageUnderstanding(BaseModel):
    """书中图片三文本（图内文字 OCR + 图注推断 + 视觉描述）。"""

    text_in_image: str
    caption: str
    description: str


# ---------------------------------------------------------------------------
# wire 契约（camelCase，shared/types/kb.ts 单一真相源）
# ---------------------------------------------------------------------------


class KbSettingsResponse(CamelModel):
    """知识库设置读取（含四模型角色槽位）。"""

    hotwords: list[str]
    segment_max_seconds: int
    asr_concurrency: int
    top_k: int
    unit_prices: dict[str, Any]
    embedding_config_id: int | None
    clean_model_id: int | None
    extract_model_id: int | None
    vision_model_id: int | None
    authorized_user_ids: list[int]
    updated_at: datetime | None = None


class KbSettingsUpdateRequest(CamelModel):
    """知识库设置保存（全部可选，仅提交的字段更新）。"""

    hotwords: list[str] | None = Field(None, max_length=200)
    segment_max_seconds: int | None = Field(None, ge=5, le=120)
    asr_concurrency: int | None = Field(None, ge=1, le=8)
    top_k: int | None = Field(None, ge=1, le=50)
    unit_prices: dict[str, Any] | None = None
    embedding_config_id: int | None = None
    clean_model_id: int | None = None
    extract_model_id: int | None = None
    vision_model_id: int | None = None
    authorized_user_ids: list[int] | None = Field(None, max_length=500)
