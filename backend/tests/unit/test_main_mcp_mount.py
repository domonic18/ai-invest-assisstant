"""MCP 精确挂载测试：只接管 /api/v1/mcp，不遮蔽同级 REST 路由。"""

import pytest
from starlette.routing import Match

from app.main import ExactPathMount

pytestmark = pytest.mark.unit


def _scope(path: str) -> dict:
    return {"type": "http", "path": path, "root_path": ""}


def test_matches_exact_path_and_rewrites_inner_path():
    route = ExactPathMount("/api/v1/mcp", app=lambda s, r, se: None, inner_path="/mcp")

    match, child = route.matches(_scope("/api/v1/mcp"))

    assert match == Match.FULL
    assert child["path"] == "/mcp"
    assert child["root_path"] == "/api/v1/mcp"


def test_tolerates_trailing_slash():
    route = ExactPathMount("/api/v1/mcp", app=lambda s, r, se: None, inner_path="/mcp")

    match, child = route.matches(_scope("/api/v1/mcp/"))

    assert match == Match.FULL
    assert child["path"] == "/mcp"


def test_does_not_shadow_sibling_api_paths():
    route = ExactPathMount("/api/v1/mcp", app=lambda s, r, se: None, inner_path="/mcp")

    for path in ("/api/v1/admin/users", "/api/v1/stocks", "/api/v1/mcp/extra"):
        assert route.matches(_scope(path))[0] == Match.NONE
