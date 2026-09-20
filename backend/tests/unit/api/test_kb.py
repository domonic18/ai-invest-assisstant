"""知识库消费侧 API 契约测试：admin/白名单权限门与检索/章节透传。"""

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app
from app.schemas.kb import (
    KbPublishedChaptersResponse,
    KbSearchResponse,
)


@contextmanager
def _as_user(role: str, user_id: int, whitelist: list[int]) -> Iterator[None]:
    """以指定身份覆盖鉴权依赖（get_settings_row 返回固定白名单）。"""
    mock_session = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.role = role

    async def _override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    settings = SimpleNamespace(authorized_user_ids=whitelist)
    try:
        with patch(
            "app.api.v1.kb.settings_service.get_settings_row",
            new=AsyncMock(return_value=settings),
        ):
            yield
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
class TestKbConsumerEndpoints:
    def test_admin_search_allowed(self, client: TestClient) -> None:
        with _as_user("admin", 1, []):
            payload = KbSearchResponse(query="支撑位")
            with patch(
                "app.api.v1.kb.search_service.search",
                new=AsyncMock(return_value=payload),
            ) as mock_search:
                response = client.get("/api/v1/kb/search", params={"q": "支撑位"})
            assert response.status_code == 200
            assert response.json()["query"] == "支撑位"
            kwargs = mock_search.await_args.kwargs
            assert kwargs["q"] == "支撑位"
            assert kwargs["point_type"] is None

    def test_whitelisted_user_search_allowed(self, client: TestClient) -> None:
        with _as_user("user", 7, [7, 9]):
            payload = KbSearchResponse(query="x")
            with patch(
                "app.api.v1.kb.search_service.search",
                new=AsyncMock(return_value=payload),
            ):
                response = client.get(
                    "/api/v1/kb/search",
                    params={"q": "x", "kind": "point", "point_type": "case"},
                )
            assert response.status_code == 200

    def test_plain_user_forbidden(self, client: TestClient) -> None:
        with _as_user("user", 8, [7, 9]):
            response = client.get("/api/v1/kb/search", params={"q": "x"})
            assert response.status_code == 403

    def test_chapter_path_and_filters_forwarded(self, client: TestClient) -> None:
        with _as_user("admin", 1, []):
            payload = KbSearchResponse(query="形态")
            with patch(
                "app.api.v1.kb.search_service.search",
                new=AsyncMock(return_value=payload),
            ) as mock_search:
                response = client.get(
                    "/api/v1/kb/search",
                    params={
                        "q": "形态",
                        "source_id": 3,
                        "chapter_path": "第一章,形态",
                        "kind": "segment",
                    },
                )
            assert response.status_code == 200
            kwargs = mock_search.await_args.kwargs
            assert kwargs["chapter_path"] == ["第一章", "形态"]
            assert kwargs["source_id"] == 3
            assert kwargs["kind"] == "segment"

    def test_chapters_returns_published_tree(self, client: TestClient) -> None:
        with _as_user("user", 7, [7]):
            payload = KbPublishedChaptersResponse.model_validate(
                {"chapters": [{"id": "p1", "title": "生效章", "children": []}]}
            )
            with patch(
                "app.api.v1.kb.search_service.get_published_chapters",
                new=AsyncMock(return_value=payload),
            ):
                response = client.get("/api/v1/kb/sources/3/chapters")
            assert response.status_code == 200
            assert response.json()["chapters"][0]["title"] == "生效章"
