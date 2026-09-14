"""助手交互工具：ask_user 问题卡（arch/09 §7.3）。

Agent 以结构化问题**结束本轮**（不引入长连接暂停）：工具返回值携带
``__question__`` 标记，运行端点（``runs.py``）在 messages 通道检测到后经
SSE ``custom`` 事件下发 ``{"type": "question", ...}``；前端侧边栏渲染
选项按钮，用户点击即作为新消息续跑线程，Agent 凭上下文继续执行。
"""

from typing import Any

from langchain_core.tools import tool

_MAX_OPTIONS = 5


def build_question_marker(
    question: str,
    options: list[dict[str, str]],
    default: str | None,
) -> dict[str, Any]:
    """构造 ``__question__`` 标记（wire 与单测共用，字段 snake_case 兼容）。"""
    return {
        "type": "question",
        "question": question,
        "options": [
            {"value": str(opt.get("value", "")).strip(), "label": str(opt.get("label", "")).strip()}
            for opt in options
        ],
        "default": default,
    }


@tool
async def ask_user(
    question: str,
    options: list[dict[str, str]],
    default: str | None = None,
) -> dict[str, Any]:
    """向用户提出结构化选择题并结束本轮（问题卡交互）。

    适用：执行写操作前需要用户决策的确认场景（如发现已有画线时确认处理
    策略）。调用后用户侧边栏会渲染选项按钮，用户点击后其选择会作为新消息
    进入对话，你凭上下文继续执行。

    调用后必须：先用一两句话向用户说明背景，然后**立即结束本轮输出**——
    不要自行假设答案、不要继续后续步骤、不要重复提问。

    Args:
        question: 问题文本（一句话，用户脱离上下文也能理解）。
        options: 选项列表，每项 {"value": "短值", "label": "中文按钮文案"}，2-5 项，value 组内唯一。
        default: 可选推荐项的 value（按钮渲染为推荐样式）。
    """
    cleaned = [opt for opt in options if str(opt.get("label", "")).strip()]
    if not question.strip():
        return {"error": "question 不能为空"}
    if not (2 <= len(cleaned) <= _MAX_OPTIONS):
        return {"error": f"options 须为 2-{_MAX_OPTIONS} 项（label 非空）"}
    values = [str(opt.get("value", "")).strip() for opt in cleaned]
    if len(set(values)) != len(values) or any(not v for v in values):
        return {"error": "options 的 value 必须非空且组内唯一"}
    if default is not None and default not in values:
        return {"error": "default 必须是 options 中某一项的 value"}
    return {
        "__question__": build_question_marker(question.strip(), cleaned, default),
        "note": "问题卡已发送给用户。立即结束本轮（说明背景即可），等待用户选择后继续。",
    }
