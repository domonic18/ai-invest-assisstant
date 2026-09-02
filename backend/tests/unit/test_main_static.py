"""SPA 静态托管与 ForceForwardedHttpsMiddleware 单元测试。"""

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.main import ForceForwardedHttpsMiddleware, app, register_spa_routes


@pytest.fixture
def spa_app(tmp_path: Path) -> FastAPI:
    static_dir = tmp_path / "static"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (static_dir / "assets" / "app-abc123.js").write_text(
        "console.log(1)", encoding="utf-8"
    )

    spa = FastAPI()

    @spa.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "1"}

    register_spa_routes(spa, static_dir)
    return spa


@pytest.mark.unit
class TestSpaRoutes:
    def test_index_no_cache_no_csp_over_http(self, spa_app: FastAPI) -> None:
        resp = TestClient(spa_app).get("/")
        assert resp.status_code == 200
        assert "index" in resp.text
        assert resp.headers["cache-control"] == "no-cache, must-revalidate"
        assert "content-security-policy" not in resp.headers
        assert "strict-transport-security" not in resp.headers

    def test_assets_immutable(self, spa_app: FastAPI) -> None:
        resp = TestClient(spa_app).get("/assets/app-abc123.js")
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"

    def test_spa_fallback_serves_index(self, spa_app: FastAPI) -> None:
        resp = TestClient(spa_app).get("/dashboard/some-route")
        assert resp.status_code == 200
        assert "index" in resp.text
        assert resp.headers["cache-control"] == "no-cache, must-revalidate"

    def test_path_traversal_rejected(self, spa_app: FastAPI) -> None:
        resp = TestClient(spa_app).get("/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code == 404

    def test_api_route_still_resolves(self, spa_app: FastAPI) -> None:
        resp = TestClient(spa_app).get("/api/v1/ping")
        assert resp.status_code == 200
        assert resp.json() == {"pong": "1"}

    def test_api_unmatched_path_returns_json_404(self, spa_app: FastAPI) -> None:
        resp = TestClient(spa_app).get("/api/v1/nonexistent")
        assert resp.status_code == 404
        assert "index" not in resp.text
        assert resp.json()["detail"]


@pytest.mark.unit
class TestRealAppWithoutStaticDir:
    def test_no_spa_catch_all_when_static_dir_unset(self) -> None:
        paths = [getattr(route, "path", "") for route in app.router.routes]
        assert "/{full_path:path}" not in paths


@pytest.mark.unit
class TestForceForwardedHttpsMiddleware:
    def test_rewrites_scheme_and_header(self) -> None:
        app_with_mw = FastAPI()
        app_with_mw.add_middleware(ForceForwardedHttpsMiddleware)

        @app_with_mw.get("/scheme")
        async def scheme(request: Request) -> dict[str, str]:
            return {
                "scheme": request.url.scheme,
                "proto": request.headers.get("x-forwarded-proto", ""),
            }

        resp = TestClient(app_with_mw).get(
            "/scheme", headers={"x-forwarded-proto": "http"}
        )
        assert resp.json() == {"scheme": "https", "proto": "https"}
