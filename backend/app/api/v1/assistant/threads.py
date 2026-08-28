"""助手线程 CRUD 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

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


def _to_response(row: AssistantSession) -> ThreadResponse:
    return ThreadResponse(
        thread_id=str(row.id),
        title=row.title,
        last_message_at=row.last_message_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata={"user_id": row.user_id},
    )


async def _require_thread(
    session: AsyncSession, user: User, thread_id: str
) -> None:
    """校验会话存在且归属当前用户，否则 404。"""
    row = await AssistantService(session).get_session(user.id, thread_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")


@router.post("", response_model=ThreadResponse)
async def create_thread(
    data: ThreadCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ThreadResponse:
    """新建助手线程（同步建 assistant_session，id 即 thread_id）。"""
    row = await AssistantService(session).create_session(user.id, data.title)
    return _to_response(row)


@sessions_router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SessionListResponse:
    """当前用户会话列表（分页，最近活跃优先；业务端点，非协议部分）。"""
    rows, total = await AssistantService(session).list_sessions(
        user.id, limit, offset
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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
