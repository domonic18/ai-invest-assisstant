"""助手运行（run）端点：流式输出、取消、状态与历史。"""

import ast
import asyncio
import json
import uuid as uuid_mod
from collections.abc import AsyncIterator
from typing import Annotated, Any, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import wire
from app.agent.runtime.assistant_agent import get_assistant_agent
from app.api.v1.assistant.threads import _require_thread
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.assistant import RunCancelRequest, RunStreamRequest, ThreadStateResponse
from app.services.assistant_service import AssistantService

logger = structlog.get_logger(__name__)

router = APIRouter()


def _with_page_context(content: Any, page_context: Any) -> Any:
    """把页面上下文（run metadata.page_context）注入首条用户消息前缀。

    使"这只股票/当前板块"等指代可解析；content 可能是 str 或内容块列表，
    块列表时把上下文行作为首个 text 块插入。
    """
    if not isinstance(page_context, dict) or not page_context:
        return content
    context_line = f"[页面上下文] {json.dumps(page_context, ensure_ascii=False)}"
    if isinstance(content, str):
        return f"{context_line}\n\n{content}"
    if isinstance(content, list):
        return [{"type": "text", "text": context_line}, *content]
    return content


def _first_text(messages_in: list[dict[str, Any]]) -> str | None:
    """取首条用户消息前 20 字作会话标题。"""
    if not messages_in:
        return None
    content = messages_in[0].get("content")
    if isinstance(content, str):
        return content[:20]
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                return str(block["text"])[:20]
    return None


def _extract_event_marker(content: Any) -> dict[str, Any] | None:
    """从 ToolMessage content 中提取 ``__event__`` 标记。

    LangChain 可能把工具返回的 dict 序列化为 JSON 字符串或 Python repr，
    因此同时支持 dict、JSON 字符串与 ``ast.literal_eval`` 可解析的字符串。
    """
    raw = content
    if isinstance(raw, dict):
        marker = raw.get("__event__")
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
            marker = parsed.get("__event__")
            return marker if isinstance(marker, dict) else None
    return None


@router.get("/threads/{thread_id}/state", response_model=ThreadStateResponse)
async def get_thread_state(
    thread_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ThreadStateResponse:
    """线程状态快照：values.messages（历史）+ tasks[].interrupts（未完成 HITL）。"""
    await _require_thread(session, user, thread_id)
    agent = await get_assistant_agent()
    snapshot = await agent.aget_state({"configurable": {"thread_id": thread_id}})
    tasks = [
        {
            "task_id": task.id,
            "name": task.name,
            "interrupts": [wire.jsonable(item) for item in (task.interrupts or [])],
        }
        for task in snapshot.tasks
    ]
    return ThreadStateResponse(
        values=wire.jsonable(snapshot.values or {}),
        next=list(snapshot.next or []),
        tasks=tasks,
        metadata=wire.jsonable(snapshot.metadata or {}),
    )


@router.get("/threads/{thread_id}/history")
async def get_thread_history(
    thread_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    """checkpoint 历史（消息编辑/重新生成定位父节点）。"""
    await _require_thread(session, user, thread_id)
    agent = await get_assistant_agent()
    history: list[dict[str, Any]] = []
    async for snapshot in agent.aget_state_history(
        {"configurable": {"thread_id": thread_id}}
    ):
        configurable = snapshot.config.get("configurable", {})
        parent = (snapshot.parent_config or {}).get("configurable", {})
        history.append(
            {
                "checkpoint_id": configurable.get("checkpoint_id"),
                "parent_checkpoint_id": parent.get("checkpoint_id"),
                "values": wire.jsonable(snapshot.values or {}),
                "next": list(snapshot.next or []),
                "created_at": (snapshot.metadata or {}).get("created_at"),
            }
        )
        if len(history) >= limit:
            break
    return history


@router.post("/threads/{thread_id}/runs/stream")
async def stream_run(
    thread_id: str,
    data: RunStreamRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """SSE 流式运行：messages/updates/custom 三通道；input（新输入）或
    command（HITL resume）二选一。客户端断开即取消（on_disconnect=cancel）。
    """
    await _require_thread(session, user, thread_id)

    messages_in = (data.input or {}).get("messages") or []
    if data.input is not None and not messages_in:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "input.messages 不能为空")

    lc_input: dict[str, Any] | None = None
    for message in messages_in:
        if message.get("type") != "human":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "仅接受 human 类型输入消息"
            )
    page_context = (data.metadata or {}).get("page_context")
    lc_input = (
        {
            "messages": [
                HumanMessage(
                    content=_with_page_context(m.get("content", ""), page_context),
                    id=m.get("id"),
                )
                for m in messages_in
            ]
        }
        if messages_in
        else None
    )

    # langgraph 1.x：resume 时 Command 直接作为 astream 的 input 传入
    stream_input: Any = None
    if data.command and "resume" in data.command:
        stream_input = Command(resume=data.command["resume"])
    elif lc_input is not None:
        stream_input = lc_input

    configurable: dict[str, Any] = {"thread_id": thread_id, "user_id": user.id}
    if data.checkpoint and data.checkpoint.get("checkpoint_id"):
        configurable["checkpoint_id"] = data.checkpoint["checkpoint_id"]

    agent = await get_assistant_agent()
    run_id = uuid_mod.uuid4().hex
    first_title = _first_text(messages_in)

    async def event_stream() -> AsyncIterator[str]:
        task = asyncio.current_task()
        if task is not None:
            wire.run_registry.register(thread_id, run_id, task)
        try:
            yield wire.sse_event(
                "metadata", {"run_id": run_id, "thread_id": thread_id}
            )
            async for namespaces, mode, payload in agent.astream(
                stream_input,
                {"configurable": configurable},
                stream_mode=["messages", "updates", "custom"],
                subgraphs=True,
            ):
                # 根图事件全量透传；子图只透传节点完成快照（updates|ns），
                # 子代理 token 流不透传以控制事件量
                if mode == "messages":
                    if namespaces:
                        continue
                    message, meta = cast("tuple[Any, Any]", payload)
                    serialized = wire.serialize_message(message)
                    yield wire.sse_event(
                        "messages",
                        [serialized, wire.jsonable(meta or {})],
                    )
                    if (
                        isinstance(message, ToolMessage)
                        and (event_marker := _extract_event_marker(message.content))
                    ):
                        yield wire.sse_event(
                            "custom", wire.jsonable(event_marker)
                        )
                elif mode == "updates":
                    label = wire.namespace_label(cast("tuple[str, ...]", namespaces))
                    event = "updates" if not label else f"updates|{label}"
                    yield wire.sse_event(event, wire.jsonable(payload))
                elif mode == "custom":
                    if namespaces:
                        continue
                    yield wire.sse_event("custom", wire.jsonable(payload))
            yield wire.sse_event("end", {})
        except asyncio.CancelledError:
            logger.info("assistant_run_cancelled", thread_id=thread_id, run_id=run_id)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "assistant_run_failed", thread_id=thread_id, run_id=run_id, error=str(exc)
            )
            yield wire.sse_event("error", {"error": str(exc), "status_code": 500})
        finally:
            wire.run_registry.unregister(run_id)
            # 用户取消时本任务已收到 CancelledError，若在取消上下文里直接
            # 操作数据库，会把 SQLAlchemy 池中的 asyncpg 连接打断成脏连接，
            # 导致后续请求 500（connection is closed）。放独立任务 + shield，
            # 让回写在取消传播之外完成。
            touch = asyncio.create_task(_touch_session(thread_id, first_title))
            try:
                await asyncio.shield(touch)
            except Exception:  # noqa: BLE001  # 失败已在任务内记录
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_run(
    thread_id: str,
    run_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    data: RunCancelRequest | None = None,
) -> dict[str, str]:
    """取消运行：中断输出，客户端随即可在同一线程开新 run。"""
    await _require_thread(session, user, thread_id)
    if not wire.run_registry.cancel(thread_id, run_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "运行不存在或已结束")
    return {"status": "cancelled"}


async def _touch_session(thread_id: str, title: str | None) -> None:
    """run 结束后回写 last_message_at/标题；失败只记日志不影响流。"""
    from app.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await AssistantService(db).touch_session(thread_id, title)
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant_touch_failed", thread_id=thread_id, error=str(exc))
