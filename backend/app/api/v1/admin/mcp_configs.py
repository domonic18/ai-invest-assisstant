"""管理后台 MCP 服务配置 API 端点。"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_db
from app.schemas.mcp_config import (
    McpServerCreateRequest,
    McpServerResponse,
    McpServerTestResponse,
    McpServerUpdateRequest,
)
from app.services.admin.mcp_config_service import McpConfigService

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/servers", response_model=list[McpServerResponse])
async def list_servers(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[McpServerResponse]:
    """全部 MCP 服务配置。"""
    return await McpConfigService(session).list_servers()


@router.post(
    "/servers",
    response_model=McpServerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_server(
    payload: McpServerCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> McpServerResponse:
    """创建 MCP 服务配置。"""
    return await McpConfigService(session).create_server(payload)


@router.post("/servers/test", response_model=McpServerTestResponse)
async def test_draft(
    payload: McpServerCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> McpServerTestResponse:
    """测试未保存的草稿配置。"""
    return await McpConfigService(session).test_draft(payload)


@router.patch("/servers/{server_id}", response_model=McpServerResponse)
async def update_server(
    server_id: int,
    payload: McpServerUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> McpServerResponse:
    """更新 MCP 服务配置。"""
    return await McpConfigService(session).update_server(server_id, payload)


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除 MCP 服务配置。"""
    await McpConfigService(session).delete_server(server_id)


@router.post("/servers/{server_id}/test", response_model=McpServerTestResponse)
async def test_server(
    server_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> McpServerTestResponse:
    """连接测试并列出工具（回写 last_status）。"""
    return await McpConfigService(session).test_server(server_id)
