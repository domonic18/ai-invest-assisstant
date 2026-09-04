"""财联社电报 API 响应模型。"""

import html
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

_TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_html(raw: str | None) -> str | None:
    """剥除富文本标签并还原实体。

    cls 正文为 ``<p>`` 富文本，前端纯文本渲染，出 API 前一次剥净。
    """
    if raw is None:
        return None
    text = _TAG_PATTERN.sub("", html.unescape(raw))
    return text.strip() or None


class TelegraphResponse(BaseModel):
    """电报条目。"""

    model_config = ConfigDict(from_attributes=True)

    cls_msg_id: int
    title: str | None = None
    content: str | None = None
    category: str | None = None
    importance: int | None = None
    shared: int | None = None
    stock_codes: list[str] | None = None
    publish_time: datetime

    @field_validator("title", "content", mode="before")
    @classmethod
    def _strip_rich_text(cls, value: object) -> object:
        if isinstance(value, str):
            return strip_html(value)
        return value
