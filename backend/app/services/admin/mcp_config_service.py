"""MCP 服务配置管理服务：CRUD + 连接测试（list_tools）。

连接测试走 ``mcp`` SDK 异步客户端（http/sse/stdio 三通道）；工具的实际
注入由 Phase 2 的 ``app.agent.tools.build_mcp_tools`` 消费 enabled 行实现。
"""

from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.mcp_server import McpServerConfig
from app.schemas.mcp_config import (
    McpServerCreateRequest,
    McpServerResponse,
    McpServerTestResponse,
    McpServerUpdateRequest,
    McpToolInfo,
)

logger = structlog.get_logger(__name__)


class McpConfigService:
    """MCP server 配置业务服务（事务边界在本层）。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_servers(self) -> list[McpServerResponse]:
        """全部 MCP server 配置。"""
        rows = (await self.session.execute(select(McpServerConfig))).scalars().all()
        return [McpServerResponse.model_validate(row) for row in rows]

    async def create_server(self, payload: McpServerCreateRequest) -> McpServerResponse:
        """创建配置；name 冲突抛 ConflictError。"""
        if await self._get_by_name(payload.name) is not None:
            raise ConflictError(f"MCP 服务名称已存在: {payload.name}")
        row = McpServerConfig(**payload.model_dump())
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        logger.info("mcp_server_created", name=row.name)
        return McpServerResponse.model_validate(row)

    async def update_server(
        self, server_id: int, payload: McpServerUpdateRequest
    ) -> McpServerResponse:
        """更新配置（None 字段不变）。"""
        row = await self._get(server_id)
        data = payload.model_dump(exclude_unset=True)
        new_name = data.get("name")
        if new_name and new_name != row.name:
            if await self._get_by_name(new_name) is not None:
                raise ConflictError(f"MCP 服务名称已存在: {new_name}")
        for key, value in data.items():
            setattr(row, key, value)
        row.last_status = None
        row.last_error = None
        await self.session.commit()
        await self.session.refresh(row)
        logger.info("mcp_server_updated", name=row.name)
        return McpServerResponse.model_validate(row)

    async def delete_server(self, server_id: int) -> None:
        """删除配置。"""
        row = await self._get(server_id)
        await self.session.delete(row)
        await self.session.commit()
        logger.info("mcp_server_deleted", name=row.name)

    async def test_server(self, server_id: int) -> McpServerTestResponse:
        """对已保存配置做连接测试并回写 last_status/last_error。"""
        row = await self._get(server_id)
        result = await _probe(row.transport_type, _conn_params(row), row.timeout_seconds)
        row.last_status = "ok" if result.ok else "failed"
        row.last_error = None if result.ok else result.error
        await self.session.commit()
        return result

    async def test_draft(self, payload: McpServerCreateRequest) -> McpServerTestResponse:
        """测试未保存的草稿配置（不入库）。"""
        return await _probe(
            payload.transport_type, _conn_params(payload), payload.timeout_seconds
        )

    async def _get(self, server_id: int) -> McpServerConfig:
        row = await self.session.get(McpServerConfig, server_id)
        if row is None:
            raise NotFoundError(f"MCP 服务不存在: {server_id}")
        return row

    async def _get_by_name(self, name: str) -> McpServerConfig | None:
        return (
            await self.session.execute(
                select(McpServerConfig).where(McpServerConfig.name == name)
            )
        ).scalar_one_or_none()


def _conn_params(cfg: Any) -> dict[str, Any]:
    """按 transport 抽取连接参数。"""
    transport = cfg.transport_type
    if transport == "stdio":
        if not cfg.command:
            raise ConflictError("stdio 传输必须填写 command")
        return {"command": cfg.command, "args": list(cfg.args or []), "env": dict(cfg.env or {})}
    if not cfg.url:
        raise ConflictError(f"{transport} 传输必须填写 url")
    return {"url": cfg.url, "headers": dict(cfg.headers or {})}


async def _probe(transport: str, params: dict[str, Any], timeout: int) -> McpServerTestResponse:
    """建立 MCP 客户端连接并列出工具；异常折叠为 ok=False + error。"""
    from contextlib import AsyncExitStack

    from mcp import ClientSession

    stack = AsyncExitStack()
    try:
        try:
            if transport == "stdio":
                from mcp import StdioServerParameters
                from mcp.client.stdio import stdio_client

                server_params = StdioServerParameters(
                    command=params["command"], args=params["args"], env=params["env"] or None
                )
                read, write = await stack.enter_async_context(stdio_client(server_params))
            elif transport == "sse":
                from mcp.client.sse import sse_client

                read, write = await stack.enter_async_context(
                    sse_client(params["url"], headers=params["headers"])
                )
            else:
                from mcp.client.streamable_http import streamablehttp_client

                read, write, _ = await stack.enter_async_context(
                    streamablehttp_client(params["url"], headers=params["headers"])
                )
            session = await stack.enter_async_context(
                ClientSession(read, write, read_timeout_seconds=timedelta(seconds=timeout))
            )
            await session.initialize()
            tools = await session.list_tools()
        except Exception as exc:  # noqa: BLE001 - 测试通道，异常折叠为失败结果
            return McpServerTestResponse(ok=False, error=f"{type(exc).__name__}: {exc}")
        tool_list = [
            McpToolInfo(name=tool.name, description=tool.description)
            for tool in tools.tools
        ]
        return McpServerTestResponse(ok=True, tool_count=len(tool_list), tools=tool_list)
    finally:
        await stack.aclose()
