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


def _reset_assistant_agent_cache() -> None:
    """配置变更后丢弃助手 agent 缓存单例，使 MCP 工具注入即时生效。

    服务层禁止顶层导入 ``app.agent.runtime``，此处延迟导入。
    """
    from app.agent.runtime.assistant_agent import reset_assistant_agent

    reset_assistant_agent()

_HTTP_ERROR_HINTS = {
    401: "鉴权失败，请检查 Authorization 等请求头凭证",
    403: "无访问权限，请检查请求头凭证或 IP 白名单",
    404: "路径不存在，请确认 URL",
    500: "远程服务内部错误",
}


def _flatten_group(exc: BaseException) -> list[BaseException]:
    """展开异常（组）为叶子异常列表（MCP SDK 基于 anyio，失败以异常组抛出）。"""
    leaves: list[BaseException] = []
    stack: list[BaseException] = [exc]
    while stack:
        current = stack.pop()
        # noqa：3.11 内置类型；ruff target 仍钉 py310（升级会激活 160+ 存量 UP 项）
        if isinstance(current, BaseExceptionGroup):  # noqa: F821
            stack.extend(current.exceptions)
        else:
            leaves.append(current)
    return leaves


def _format_failures(leaves: list[BaseException]) -> str:
    """叶子异常折叠为可读错误：HTTP 状态错误优先展示并附排查提示。"""
    http_leaves = [
        leaf
        for leaf in leaves
        if getattr(getattr(leaf, "response", None), "status_code", None) is not None
    ]
    chosen = (http_leaves[:2] if http_leaves else leaves[:2]) or []
    messages: list[str] = []
    for leaf in chosen:
        status = getattr(getattr(leaf, "response", None), "status_code", None)
        if status is not None:
            hint = _HTTP_ERROR_HINTS.get(status)
            message = f"远程服务返回 HTTP {status}"
            messages.append(f"{message}（{hint}）" if hint else message)
        elif isinstance(leaf, TimeoutError):
            messages.append("连接超时，请检查网络可达性或增大超时秒数")
        else:
            messages.append(f"{type(leaf).__name__}: {leaf}")
    return "；".join(dict.fromkeys(messages))


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
        _reset_assistant_agent_cache()
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
        _reset_assistant_agent_cache()
        logger.info("mcp_server_updated", name=row.name)
        return McpServerResponse.model_validate(row)

    async def delete_server(self, server_id: int) -> None:
        """删除配置。"""
        row = await self._get(server_id)
        await self.session.delete(row)
        await self.session.commit()
        _reset_assistant_agent_cache()
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
    """建立 MCP 客户端连接并列出工具；一切异常（含异常组/取消）折叠为 ok=False。

    SDK 传输任务组崩溃后，取消会直接打进本协程的 await 点（``CancelledError``
    是 ``BaseException``），客户端关闭时任务组还会重抛后台异常，故体与清理
    两侧都收集叶子，最后统一格式化。
    """
    from contextlib import AsyncExitStack

    from mcp import ClientSession

    failures: list[BaseException] = []
    ok_result: McpServerTestResponse | None = None
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
        except BaseException as exc:  # noqa: BLE001 - 测试通道，异常折叠为失败结果
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            failures.extend(_flatten_group(exc))
        else:
            tool_list = [
                McpToolInfo(name=tool.name, description=tool.description)
                for tool in tools.tools
            ]
            ok_result = McpServerTestResponse(
                ok=True, tool_count=len(tool_list), tools=tool_list
            )
    finally:
        try:
            await stack.aclose()
        except BaseException as exc:  # noqa: BLE001 - 清理重抛的后台异常并入失败，不掩盖结果
            failures.extend(_flatten_group(exc))
            logger.debug("mcp_probe_cleanup_failed", exc_info=True)
    if ok_result is not None:
        return ok_result
    return McpServerTestResponse(
        ok=False,
        error=_format_failures(failures) if failures else "连接测试中断，请重试",
    )
