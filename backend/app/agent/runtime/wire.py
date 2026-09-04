"""Agent Protocol wire 序列化与 SSE 帧。

对齐 ``@langchain/langgraph-sdk`` / ``@assistant-ui/react-langgraph`` 消费的
格式：消息序列化为扁平 LangChain JSON（type=human/ai/tool/AIMessageChunk），
内容块（thinking/text/tool_use/input_json_delta 等 Anthropic 风格 dict）原样
透传，与前端 ``normalizeLangGraphTupleMessage`` / ``appendLangChainChunk``
直接对接。
"""

import asyncio
import json
from datetime import date, datetime
from typing import Any

from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.types import Interrupt


def serialize_message(message: BaseMessage) -> dict[str, Any]:
    """LangChain 消息 → langgraph-sdk wire JSON（扁平结构）。"""
    data: dict[str, Any] = {
        "type": message.type,
        "content": message.content,
        "id": message.id,
    }
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        data["tool_calls"] = [
            {
                "id": call.get("id") or "",
                "name": call.get("name") or "",
                "args": call.get("args") or {},
                "index": index,
            }
            for index, call in enumerate(tool_calls)
        ]
    chunks = getattr(message, "tool_call_chunks", None)
    if chunks:
        data["tool_call_chunks"] = [
            {
                "index": chunk.get("index") or 0,
                "id": chunk.get("id") or "",
                "name": chunk.get("name") or "",
                "args": chunk.get("args") or "",
            }
            for chunk in chunks
        ]
    if isinstance(message, ToolMessage):
        data["tool_call_id"] = message.tool_call_id
        data["name"] = message.name
        data["status"] = getattr(message, "status", "success")
    return data


def jsonable(value: Any) -> Any:
    """任意 state/载荷 → JSON 安全结构（消息、Interrupt、日期递归处理）。"""
    if isinstance(value, BaseMessage):
        return serialize_message(value)
    if isinstance(value, Interrupt):
        return {
            "value": jsonable(value.value),
            "id": value.id,
            "interrupt_id": getattr(value, "interrupt_id", None),
        }
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def sse_event(event: str, data: Any) -> str:
    """构造一帧 SSE（event + data，data 为 JSON）。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def namespace_label(namespaces: tuple[str, ...]) -> str:
    """subgraphs 命名空间 → SSE 事件后缀（取最后一段，如 task:xxx）。"""
    return namespaces[-1] if namespaces else ""


class RunRegistry:
    """活跃 run 注册表：支持跨请求取消（POST /threads/{tid}/runs/{rid}/cancel）。"""

    def __init__(self) -> None:
        self._runs: dict[str, tuple[str, asyncio.Task[None]]] = {}

    def register(self, thread_id: str, run_id: str, task: asyncio.Task[None]) -> None:
        self._runs[run_id] = (thread_id, task)

    def unregister(self, run_id: str) -> None:
        self._runs.pop(run_id, None)

    def cancel(self, thread_id: str, run_id: str) -> bool:
        entry = self._runs.get(run_id)
        if entry is None or entry[0] != thread_id:
            return False
        entry[1].cancel()
        return True


run_registry = RunRegistry()
