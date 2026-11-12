"""Agent Protocol wire 序列化与 SSE 帧。

对齐 ``@langchain/langgraph-sdk`` / ``@assistant-ui/react-langgraph`` 消费的
格式：消息序列化为扁平 LangChain JSON（type=human/ai/tool/AIMessageChunk），
内容块（thinking/text/tool_use/input_json_delta 等 Anthropic 风格 dict）原样
透传，与前端 ``normalizeLangGraphTupleMessage`` / ``appendLangChainChunk``
直接对接。
"""

import ast
import asyncio
import json
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import date, datetime
from typing import Any, TypeVar, cast

from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.types import Interrupt

T = TypeVar("T")

# SSE 注释帧（keep-alive）：对代理/LB 维持连接活性；对 langgraph-sdk 的空闲
# 看门狗提供字节级心跳，半开连接可在看门狗窗口内被客户端检出并触发对账
SSE_HEARTBEAT = ": ping\n\n"


class Heartbeat:
    """心跳 tick 标记（``merge_heartbeats`` 在源静默超时时产出）。"""

    __slots__ = ()


HEARTBEAT = Heartbeat()


async def merge_heartbeats(
    source: AsyncIterator[T], interval: float
) -> AsyncGenerator[T | Heartbeat, None]:
    """把异步源与心跳 tick 合流：源超过 ``interval`` 秒无产出时产出一个
    ``HEARTBEAT`` 标记，直到源耗尽或异常（异常原样上抛给消费方）。

    助手运行的工具执行可能数分钟无事件，期间连接必须有字节流动，
    否则既过不了代理空闲超时，客户端也无从区分「慢」与「死」。

    注意：消费方提前 break 时 async-for 不会关闭本生成器（finally 不执行，
    pump 任务泄漏且与源的 ``aclose`` 可能并发），须显式 ``await aclose()``。
    自然耗尽（StopAsyncIteration）则 finally 自行执行。
    """
    queue: asyncio.Queue[T | Heartbeat | BaseException | object] = asyncio.Queue()
    done = object()

    async def pump() -> None:
        try:
            async for item in source:
                await queue.put(item)
            await queue.put(done)
        except BaseException as exc:  # noqa: BLE001 - 异常经队列转交消费方原样上抛
            await queue.put(exc)

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval)
            except asyncio.TimeoutError:
                yield HEARTBEAT
                continue
            if item is done:
                break
            if isinstance(item, BaseException):
                raise item
            yield cast("T | Heartbeat", item)
    finally:
        pump_task.cancel()
        try:
            await pump_task
        except asyncio.CancelledError:
            pass


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


def _extract_marker(content: Any, key: str) -> dict[str, Any] | None:
    """从 ToolMessage content 中提取指定 ``__key__`` 标记。

    LangChain 可能把工具返回的 dict 序列化为 JSON 字符串或 Python repr，
    因此同时支持 dict、JSON 字符串与 ``ast.literal_eval`` 可解析的字符串。
    """
    raw = content
    if isinstance(raw, dict):
        marker = raw.get(key)
        return marker if isinstance(marker, dict) else None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(raw)
            except Exception:  # noqa: BLE001
                return None
        if isinstance(parsed, dict):
            marker = parsed.get(key)
            return marker if isinstance(marker, dict) else None
    return None


def extract_event_marker(content: Any) -> dict[str, Any] | None:
    """提取页面回写事件标记（``__event__``）。"""
    return _extract_marker(content, "__event__")


def extract_question_marker(content: Any) -> dict[str, Any] | None:
    """提取 ask_user 问题卡标记（``__question__``，payload 含 type=question）。"""
    return _extract_marker(content, "__question__")


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

    def has_active_run(self, thread_id: str) -> bool:
        """线程是否有正在执行的 run（前端断连对账依据：active=继续等，inactive=拉终态）。"""
        return any(tid == thread_id for tid, _ in self._runs.values())


run_registry = RunRegistry()
