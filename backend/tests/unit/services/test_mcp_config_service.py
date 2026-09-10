"""MCP 服务配置管理服务单元测试。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.mcp_config import McpServerCreateRequest, McpServerTestResponse
from app.services.admin.mcp_config_service import McpConfigService, _conn_params


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
