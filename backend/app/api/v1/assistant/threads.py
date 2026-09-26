"""助手线程 CRUD 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.exceptions import ForbiddenError, NotFoundError, UnprocessableEntityError
from app.dependencies import get_current_user, get_db
from app.models.assistant_session import AssistantSession
from app.models.user import User
from app.schemas.assistant import (
    SessionListResponse,
    ThreadCreateRequest,
    ThreadResponse,
)
from app.services.assistant.assistant_service import AssistantService

router = APIRouter(prefix="/threads")
sessions_router = APIRouter()

AGENT_TYPES = ("assistant", "trading")


def _to_response(row: AssistantSession) -> ThreadResponse:
    return ThreadResponse(
        thread_id=str(row.id),
        title=row.title,
        agent_type=row.agent_type,
        last_message_at=row.last_message_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata={"user_id": row.user_id},
    )


async def _require_thread(
    session: AsyncSession, user: User, thread_id: str
) -> AssistantSession:
    """校验会话存在且归属当前用户，否则 404；返回会话行（runs 端点据此分流 agent）。"""
    row = await AssistantService(session).get_session(user.id, thread_id)
    if row is None:
        raise NotFoundError("会话不存在")
    return row


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    data: ThreadCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ThreadResponse:
    """新建助手线程（同步建 assistant_session，id 即 thread_id）。

    ``agent_type=trading`` 仅 admin 可建（交易 Agent 页）；其余值一律 422。
    """
    agent_type = data.agent_type or "assistant"
    if agent_type not in AGENT_TYPES:
        raise UnprocessableEntityError(
            f"agent_type 须为 {'/'.join(AGENT_TYPES)}（当前 {agent_type}）"
        )
    if agent_type == "trading" and user.role != "admin":
        raise ForbiddenError("交易 Agent 会话仅管理员可用")
    row = await AssistantService(session).create_session(user.id, data.title, agent_type)
    return _to_response(row)


@sessions_router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
    agent_type: Annotated[str | None, Query()] = None,
) -> SessionListResponse:
    """当前用户会话列表（分页，最近活跃优先；业务端点，非协议部分）。"""
    rows, total = await AssistantService(session).list_sessions(
        user.id, limit, offset, agent_type
    )
    return SessionListResponse(
        sessions=[_to_response(row) for row in rows], total=total
    )


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """删除线程：级联删除 LangGraph checkpoint 与 assistant_session。"""
    ok = await AssistantService(session).delete_session(user.id, thread_id)
    if not ok:
        raise NotFoundError("会话不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
