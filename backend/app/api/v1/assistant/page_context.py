"""页面上下文注入辅助。"""

import json
from typing import Any

from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer
from app.core.config import get_settings


def _with_page_context(content: Any, page_context: Any) -> Any:
    """把页面上下文（run metadata.page_context）注入首条用户消息前缀。

    使"这只股票/当前板块"等指代可解析；content 可能是 str 或内容块列表，
    块列表时把上下文行作为首个 text 块插入。前缀模板由 prompts YAML 提供
    （Prompt 只放 YAML）。
    """
    if not isinstance(page_context, dict) or not page_context:
        return content
    template = (
        PromptLoader(get_settings().prompts_dir)
        .load("agents", "page_context")
        .user_prompt_template
    )
    context_line = PromptRenderer.render(
        template, context=json.dumps(page_context, ensure_ascii=False)
    )
    if isinstance(content, str):
        return f"{context_line}\n\n{content}"
    if isinstance(content, list):
        return [{"type": "text", "text": context_line}, *content]
    return content
