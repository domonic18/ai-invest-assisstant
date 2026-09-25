"""助手运行（run）端点：流式输出、取消、状态与历史。"""

import asyncio
import uuid as uuid_mod
from collections.abc import AsyncIterator
from typing import Annotated, Any, cast

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import wire
from app.agent.runtime.assistant_agent import get_assistant_agent
from app.api.v1.assistant.page_context import _with_page_context
from app.api.v1.assistant.threads import _require_thread
from app.constants.pagination import DEFAULT_HISTORY_LIMIT, MAX_HISTORY_LIMIT
from app.core.exceptions import (
    AppError,
    NotFoundError,
    QuotaExhaustedError,
    UnprocessableEntityError,
)
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.assistant import RunCancelRequest, RunStreamRequest, ThreadStateResponse
from app.services.assistant.assistant_service import AssistantService, finalize_run
from app.services.quota import quota_service
from app.services.quota.constants import FEATURE_ASSISTANT
from app.services.quota.context import meter_scope
from app.services.quota.user_llm_service import resolve_llm

logger = structlog.get_logger(__name__)

router = APIRouter()

_CUSTOM_SKILL_INDEX_HEADER = "用户已安装以下自定义技能（需使用时说明技能名称）："


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
    limit: Annotated[int, Query(ge=1, le=MAX_HISTORY_LIMIT)] = DEFAULT_HISTORY_LIMIT,
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


def _with_custom_skills(content: Any, custom_lines: list[str]) -> Any:
    """把用户 custom 技能索引段注入首条用户消息前缀（渐进披露）。

    content 可能是 str 或内容块列表，块列表时索引作为首个 text 块插入；
    无 custom 技能时原样返回（零开销）。仅新输入注入，resume 不注入。
    """
    if not custom_lines:
        return content
    index = _CUSTOM_SKILL_INDEX_HEADER + "\n" + "\n".join(
        f"- {line}" for line in custom_lines
    )
    if isinstance(content, str):
        return f"{index}\n\n{content}"
    if isinstance(content, list):
        return [{"type": "text", "text": index}, *content]
    return content


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
        raise UnprocessableEntityError("input.messages 不能为空")

    lc_input: dict[str, Any] | None = None
    for message in messages_in:
        if message.get("type") != "human":
            raise UnprocessableEntityError("仅接受 human 类型输入消息")
    page_context = (data.metadata or {}).get("page_context")
    custom_lines = (
        await AssistantService(session).custom_skill_index_lines(user.id)
        if messages_in
        else []
    )
    lc_input = (
        {
            "messages": [
                HumanMessage(
                    content=_with_page_context(
                        _with_custom_skills(m.get("content", ""), custom_lines),
                        page_context,
                    ),
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

    run_id = uuid_mod.uuid4().hex

    # 配额入口预检（callback 内 raise 会被 LangChain 吞掉，拦截须在入口）。
    # 拒绝不走 HTTP 429：langgraph-sdk 对流前错误静默结束（界面无任何提示），
    # 改为合法 SSE 流并合成一条 AI 提示消息，用户在对话框直接看到引导文案。
    try:
        await quota_service.precheck(user.id)
    except QuotaExhaustedError as exc:
        from langchain_core.messages import AIMessage

        # except 块结束即删除 exc，闭包须捕获普通变量
        refusal_message = exc.message

        async def quota_refused_stream() -> AsyncIterator[str]:
            try:
                yield wire.sse_event(
                    "metadata", {"run_id": run_id, "thread_id": thread_id}
                )
                notice = AIMessage(content=refusal_message, id=f"quota-{run_id}")
                yield wire.sse_event("messages", [wire.serialize_message(notice), {}])
                yield wire.sse_event("end", {})
            finally:
                await finalize_run(thread_id, messages_in)

        return StreamingResponse(
            quota_refused_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # 出口分流：BYOK 用户获得独立 agent 实例（失败不回退，arch/07 §5）；
    # 知识库检索工具随对话「使用知识库」开关注入（metadata.use_kb，缺省开）
    cfg, _outlet = await resolve_llm(session, user.id)
    use_kb = bool((data.metadata or {}).get("use_kb", True))
    agent = await get_assistant_agent(cfg=cfg, use_kb=use_kb)

    async def event_stream() -> AsyncIterator[str]:
        task = asyncio.current_task()
        if task is not None:
            wire.run_registry.register(thread_id, run_id, task)
        with meter_scope(user.id, FEATURE_ASSISTANT):
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
                            and (event_marker := wire.extract_event_marker(message.content))
                        ):
                            yield wire.sse_event(
                                "custom", wire.jsonable(event_marker)
                            )
                        if (
                            isinstance(message, ToolMessage)
                            and (question_marker := wire.extract_question_marker(message.content))
                        ):
                            yield wire.sse_event(
                                "custom", wire.jsonable(question_marker)
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
            except AppError as exc:
                logger.warning(
                    "assistant_run_app_error", thread_id=thread_id, run_id=run_id, error=str(exc)
                )
                yield wire.sse_event(
                    "error", {"error": exc.message, "status_code": exc.status_code}
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "assistant_run_failed", thread_id=thread_id, run_id=run_id, error=str(exc)
                )
                yield wire.sse_event("error", {"error": str(exc), "status_code": 500})
            finally:
                wire.run_registry.unregister(run_id)
                await finalize_run(thread_id, messages_in)

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
        raise NotFoundError("运行不存在或已结束")
    return {"status": "cancelled"}
