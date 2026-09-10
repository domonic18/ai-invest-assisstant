"""MCP 服务配置管理服务单元测试。"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools import build_mcp_tools
from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.mcp_config import McpServerCreateRequest, McpServerTestResponse
from app.services.admin.mcp_config_service import McpConfigService, _conn_params, _probe


def _row(**overrides: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "id": 1,
        "name": "finance-mcp",
        "transport_type": "http",
        "command": None,
        "args": [],
        "url": "https://example.com/mcp",
        "env": {},
        "headers": {},
        "enabled": False,
        "timeout_seconds": 30,
        "last_status": None,
        "last_error": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.unit
async def test_create_server_ok() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    now = datetime.now(UTC)
    values = dict(
        id=7,
        name="finance-mcp",
        transport_type="http",
        command=None,
        args=[],
        url="https://example.com/mcp",
        env={},
        headers={},
        enabled=False,
        timeout_seconds=30,
        last_status=None,
        last_error=None,
        created_at=now,
        updated_at=now,
    )

    async def _refresh(obj: object, *args: object, **kwargs: object) -> None:
        for key, value in values.items():
            setattr(obj, key, value)

    session.refresh = AsyncMock(side_effect=_refresh)

    resp = await McpConfigService(session).create_server(
        McpServerCreateRequest(name="finance-mcp", url="https://example.com/mcp")
    )
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    assert resp.id == 7
    assert resp.name == "finance-mcp"


@pytest.mark.unit
async def test_create_server_name_conflict() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _row()
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(ConflictError):
        await McpConfigService(session).create_server(
            McpServerCreateRequest(name="finance-mcp", url="https://example.com/mcp")
        )


@pytest.mark.unit
async def test_update_server_resets_probe_state() -> None:
    row = _row(last_status="failed", last_error="boom")
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    from app.schemas.mcp_config import McpServerUpdateRequest

    resp = await McpConfigService(session).update_server(
        1, McpServerUpdateRequest(url="https://new.example.com/mcp")
    )
    assert row.url == "https://new.example.com/mcp"
    assert row.last_status is None
    assert row.last_error is None
    session.commit.assert_awaited_once()
    assert resp.name == "finance-mcp"


@pytest.mark.unit
async def test_update_server_missing() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    from app.schemas.mcp_config import McpServerUpdateRequest

    with pytest.raises(NotFoundError):
        await McpConfigService(session).update_server(99, McpServerUpdateRequest(enabled=True))


@pytest.mark.unit
async def test_delete_server_ok() -> None:
    row = _row()
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)

    await McpConfigService(session).delete_server(1)
    session.delete.assert_awaited_once_with(row)
    session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_get_missing_raises() -> None:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await McpConfigService(session).delete_server(99)


@pytest.mark.unit
async def test_test_server_writes_status_ok() -> None:
    row = _row()
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)
    probe_result = McpServerTestResponse(ok=True, tool_count=2)

    with patch(
        "app.services.admin.mcp_config_service._probe", new=AsyncMock(return_value=probe_result)
    ):
        resp = await McpConfigService(session).test_server(1)

    assert resp.ok is True
    assert row.last_status == "ok"
    assert row.last_error is None
    session.commit.assert_awaited_once()


@pytest.mark.unit
async def test_test_server_writes_status_failed() -> None:
    row = _row()
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)
    probe_result = McpServerTestResponse(ok=False, error="ConnectError: boom")

    with patch(
        "app.services.admin.mcp_config_service._probe", new=AsyncMock(return_value=probe_result)
    ):
        resp = await McpConfigService(session).test_server(1)

    assert resp.ok is False
    assert row.last_status == "failed"
    assert row.last_error == "ConnectError: boom"


@pytest.mark.unit
async def test_conn_params_stdio_requires_command() -> None:
    with pytest.raises(ConflictError):
        _conn_params(_row(transport_type="stdio", command=None))


@pytest.mark.unit
async def test_conn_params_http_requires_url() -> None:
    with pytest.raises(ConflictError):
        _conn_params(_row(transport_type="http", url=None))


class _FakeHTTPStatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.response = SimpleNamespace(status_code=status_code)


def _failing_http_client(exc: BaseException):
    @asynccontextmanager
    async def _client(*args: object, **kwargs: object):
        raise exc
        yield  # pragma: no cover

    return _client


def _ok_http_client_with_session(tools: list[str]):
    @asynccontextmanager
    async def _client(*args: object, **kwargs: object):
        yield SimpleNamespace(), SimpleNamespace(), (lambda: None)

    @asynccontextmanager
    async def _session(read: object, write: object, **kwargs: object):
        yield SimpleNamespace(
            initialize=AsyncMock(),
            list_tools=AsyncMock(
                return_value=SimpleNamespace(
                    tools=[SimpleNamespace(name=n, description=None) for n in tools]
                )
            ),
        )

    return _client, _session


@pytest.mark.unit
async def test_probe_folds_exception_group_into_http_hint() -> None:
    """anyio 异常组（含 401）应折叠为 ok=False + HTTP 提示，而非向上抛 500。"""
    # noqa 下一行：3.11 内置类型；ruff target 仍钉 py310（升级会激活 160+ 存量 UP 项）
    exc = BaseExceptionGroup("unhandled", [_FakeHTTPStatusError(401)])  # noqa: F821
    with patch(
        "mcp.client.streamable_http.streamablehttp_client",
        _failing_http_client(exc),
    ):
        result = await _probe("http", {"url": "https://x/mcp", "headers": {}}, 5)

    assert result.ok is False
    assert "HTTP 401" in (result.error or "")


@pytest.mark.unit
async def test_probe_folds_cancelled_error() -> None:
    """传输任务组崩溃向协程注入 CancelledError 时应折叠为失败，而非向上抛。"""
    with patch(
        "mcp.client.streamable_http.streamablehttp_client",
        _failing_http_client(asyncio.CancelledError()),
    ):
        result = await _probe("http", {"url": "https://x/mcp", "headers": {}}, 5)

    assert result.ok is False
    assert (result.error or "") != ""


@pytest.mark.unit
async def test_probe_success_lists_tools() -> None:
    client_cm, session_cm = _ok_http_client_with_session(["t1", "t2"])
    with (
        patch("mcp.client.streamable_http.streamablehttp_client", client_cm),
        patch("mcp.ClientSession", session_cm),
    ):
        result = await _probe("http", {"url": "https://x/mcp", "headers": {}}, 5)

    assert result.ok is True
    assert result.tool_count == 2
    assert [t.name for t in result.tools] == ["t1", "t2"]


class _FakeSessionResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def scalars(self) -> "_FakeSessionResult":
        return self

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    async def execute(self, _query: object) -> _FakeSessionResult:
        return _FakeSessionResult(self._rows)

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


def _mcp_row(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 1,
        "name": "a",
        "transport_type": "http",
        "url": "https://a/mcp",
        "headers": {},
        "timeout_seconds": 5,
        "command": None,
        "args": [],
        "env": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.unit
async def test_build_mcp_tools_merges_and_dedupes() -> None:
    """多服务工具合并；重名工具保留先注册的并跳过后者。"""
    rows = [
        _mcp_row(id=1, name="a"),
        _mcp_row(id=2, name="b", transport_type="stdio", command="npx", args=["-y"], url=None),
    ]
    tools_by_server: dict[str, list[SimpleNamespace]] = {
        "a": [SimpleNamespace(name="t1"), SimpleNamespace(name="t2")],
        "b": [SimpleNamespace(name="t1")],
    }

    class _FakeClient:
        def __init__(self, connections: dict[str, object]) -> None:
            self._name = next(iter(connections))

        async def get_tools(self) -> list[SimpleNamespace]:
            return tools_by_server[self._name]

    with (
        patch("app.core.database.AsyncSessionLocal", lambda: _FakeSession(rows)),
        patch("langchain_mcp_adapters.client.MultiServerMCPClient", _FakeClient),
    ):
        tools = await build_mcp_tools()

    assert [t.name for t in tools] == ["t1", "t2"]


@pytest.mark.unit
async def test_build_mcp_tools_isolates_server_failure() -> None:
    """单服务连接失败只记日志，不影响其余服务注入。"""
    rows = [_mcp_row(id=1, name="bad"), _mcp_row(id=2, name="good")]

    class _FakeClient:
        def __init__(self, connections: dict[str, object]) -> None:
            self._name = next(iter(connections))

        async def get_tools(self) -> list[SimpleNamespace]:
            if self._name == "bad":
                raise RuntimeError("boom")
            return [SimpleNamespace(name="t-ok")]

    with (
        patch("app.core.database.AsyncSessionLocal", lambda: _FakeSession(rows)),
        patch("langchain_mcp_adapters.client.MultiServerMCPClient", _FakeClient),
    ):
        tools = await build_mcp_tools()

    assert [t.name for t in tools] == ["t-ok"]


@pytest.mark.unit
async def test_build_mcp_tools_empty_when_none_enabled() -> None:
    with patch("app.core.database.AsyncSessionLocal", lambda: _FakeSession([])):
        tools = await build_mcp_tools()

    assert tools == []


@pytest.mark.unit
async def test_mcp_crud_resets_assistant_agent() -> None:
    """MCP 配置增/改/删后必须丢弃助手 agent 缓存单例。"""
    import app.agent.runtime.assistant_agent as agent_module

    with (
        patch.object(agent_module, "reset_assistant_agent") as reset_mock,
        patch(
            "app.services.admin.mcp_config_service.McpServerResponse.model_validate",
            side_effect=lambda row: row,
        ),
    ):
        session = MagicMock()
        session.get = AsyncMock(return_value=_row(id=7))
        session.refresh = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        session.commit = AsyncMock()
        session.delete = AsyncMock()
        service = McpConfigService(session)
        service.session.add = MagicMock()
        await service.create_server(McpServerCreateRequest(name="x", transport_type="http", url="https://x/mcp"))
        await service.update_server(7, McpServerCreateRequest(name="y", transport_type="http", url="https://y/mcp"))
        await service.delete_server(7)

    assert reset_mock.call_count == 3
