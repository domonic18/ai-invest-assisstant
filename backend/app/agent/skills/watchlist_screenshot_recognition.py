"""自选股截图识别执行器：视觉模型读取截图中的 A 股列表。

交互入口为 ``POST /users/watchlist/recognize-screenshot``；
识别结果由服务层与 ``stock_basic`` 交叉校验后才返回给用户确认。
"""

import re

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import PromptLoader
from app.agent.runtime.structured import run_structured
from app.core.config import get_settings

SKILL_ID = "watchlist-screenshot-recognition"
_MAX_RECOGNIZED = 50

_CODE_SUFFIX_RE = re.compile(r"^(?:SH|SZ|BJ)[:.]?", re.IGNORECASE)
_SIX_DIGIT_RE = re.compile(r"\d{6}")


class RecognizedStock(BaseModel):
    """截图识别出的单只股票（原始识别结果）。"""

    code: str
    name: str | None = None
    confidence: float | None = None


class RecognizedStockList(BaseModel):
    """输出容器模型：``with_structured_output`` 要求单一 pydantic 模型。"""

    stocks: list[RecognizedStock] = Field(default_factory=list)


def normalize_code(raw: str) -> str | None:
    """规范化股票代码：去除交易所后缀，提取 6 位数字。"""
    text = _CODE_SUFFIX_RE.sub("", raw.strip())
    match = _SIX_DIGIT_RE.search(text)
    return match.group(0) if match else None


async def run_skill(
    session: AsyncSession,
    *,
    data: bytes,
    media_type: str,
) -> list[RecognizedStock]:
    """调用视觉模型识别截图中的股票列表。

    Raises:
        LLMConfigNotConfiguredError: 未配置视觉模型。
        ValidationError: 模型输出不符合 schema（经 langchain 重试后仍失败）。
    """
    prompt_config = PromptLoader(get_settings().prompts_dir).load("skills", SKILL_ID)
    user_prompt: str = prompt_config.user_prompt_template or "请识别截图中的股票列表。"
    result = await run_structured(
        session,
        result_type=RecognizedStockList,
        user_prompt=user_prompt,
        images=[(data, media_type)],
    )
    return _dedupe(result.stocks)[:_MAX_RECOGNIZED]


def _dedupe(items: list[RecognizedStock]) -> list[RecognizedStock]:
    """按规范化代码去重，保留首条。"""
    seen: set[str] = set()
    ordered: list[RecognizedStock] = []
    for item in items:
        code = normalize_code(item.code) if item.code else None
        if code is None or code in seen:
            continue
        seen.add(code)
        ordered.append(item.model_copy(update={"code": code}))
    return ordered
