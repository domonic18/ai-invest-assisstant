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
    KbChapterPointsResponse,
    KbPlaybackTokenResponse,
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

    def test_chapter_points_forwards_path_and_pagination(
        self, client: TestClient
    ) -> None:
        with _as_user("admin", 1, []):
            payload = KbChapterPointsResponse.model_validate(
                {"total": 1, "page": 2, "pageSize": 5, "points": []}
            )
            with patch(
                "app.api.v1.kb.search_service.list_chapter_points",
                new=AsyncMock(return_value=payload),
            ) as mock_list:
                response = client.get(
                    "/api/v1/kb/sources/3/points",
                    params={"chapter_path": "6, 6.3", "page": 2, "page_size": 5},
                )
            assert response.status_code == 200
            body = response.json()
            assert body["total"] == 1 and body["pageSize"] == 5
            kwargs = mock_list.await_args.kwargs
            assert kwargs["chapter_path"] == ["6", "6.3"]
            assert kwargs["page"] == 2 and kwargs["page_size"] == 5

    def test_chapter_points_requires_path_and_bounds(self, client: TestClient) -> None:
        with _as_user("admin", 1, []):
            assert (
                client.get("/api/v1/kb/sources/3/points").status_code == 422
            )
            assert (
                client.get(
                    "/api/v1/kb/sources/3/points",
                    params={"chapter_path": "6", "page": 0},
                ).status_code
                == 422
            )
            assert (
                client.get(
                    "/api/v1/kb/sources/3/points",
                    params={"chapter_path": "6", "page_size": 101},
                ).status_code
                == 422
            )

    def test_consumer_sources_minimal_projection(self, client: TestClient) -> None:
        from app.schemas.kb import KbConsumerSourceResponse

        with _as_user("user", 7, [7]):
            payload = [
                KbConsumerSourceResponse(id=3, name="课程库", source_type="course")
            ]
            with patch(
                "app.api.v1.kb.source_service.list_consumer_sources",
                new=AsyncMock(return_value=payload),
            ):
                response = client.get("/api/v1/kb/sources")
        assert response.status_code == 200
        body = response.json()
        assert body == [{"id": 3, "name": "课程库", "sourceType": "course"}]

    def test_plain_user_cannot_list_consumer_sources(self, client: TestClient) -> None:
        with _as_user("user", 8, [7]):
            response = client.get("/api/v1/kb/sources")
        assert response.status_code == 403

    def test_image_original_url_endpoint(self, client: TestClient) -> None:
        from app.schemas.kb import KbImageUrlResponse

        with _as_user("user", 7, [7]):
            payload = KbImageUrlResponse(url="https://cos/signed", expires_in=900)
            with patch(
                "app.api.v1.kb.playback_service.issue_image_url",
                new=AsyncMock(return_value=payload),
            ) as mock_issue:
                response = client.get("/api/v1/kb/images/5/original-url")
            kwargs = mock_issue.await_args.kwargs
            assert kwargs["image_id"] == 5
        assert response.status_code == 200
        body = response.json()
        assert body["url"] == "https://cos/signed"
        assert body["expiresIn"] == 900


@pytest.mark.unit
class TestKbPlaybackEndpoints:
    """F1 播放凭证（含预签名直链）/书页/字幕端点契约。"""

    def test_playback_token_camel_case_and_forwarding(
        self, client: TestClient
    ) -> None:
        with _as_user("user", 7, [7]):
            payload = KbPlaybackTokenResponse(
                token="t" * 43,
                expires_in=1800,
                media_id=11,
                stream_url="https://cos/signed",
                prev_media_id=10,
                next_media_id=12,
            )
            with patch(
                "app.api.v1.kb.playback_service.issue_playback_token",
                new=AsyncMock(return_value=payload),
            ) as mock_issue:
                response = client.post("/api/v1/kb/media/11/playback-token")
            assert response.status_code == 200
            body = response.json()
            assert body["token"] == "t" * 43
            assert body["expiresIn"] == 1800
            assert body["streamUrl"] == "https://cos/signed"
            assert body["prevMediaId"] == 10 and body["nextMediaId"] == 12
            kwargs = mock_issue.await_args.kwargs
            assert kwargs["user_id"] == 7 and kwargs["media_id"] == 11

    def test_playback_token_denied_without_whitelist(
        self, client: TestClient
    ) -> None:
        with _as_user("user", 7, []):
            response = client.post("/api/v1/kb/media/11/playback-token")
        assert response.status_code == 403

    def test_stream_route_retired(self, client: TestClient) -> None:
        """代理流端点已退役（SCF 6MB 响应上限不可承载媒体，改预签名直链）。"""
        with _as_user("admin", 1, []):
            response = client.get(
                "/api/v1/kb/stream/11",
                params={"token": "t" * 43},
                headers={"Range": "bytes=0-"},
            )
        assert response.status_code == 404

    def test_book_page_png_response(self, client: TestClient) -> None:
        with _as_user("user", 7, [7]):
            with patch(
                "app.api.v1.kb.book_render.render_book_page",
                new=AsyncMock(return_value=b"\x89PNG-data"),
            ) as mock_render:
                response = client.get(
                    "/api/v1/kb/books/11/pages/3",
                    params={"token": "t" * 43},
                )
            kwargs = mock_render.await_args.kwargs
            assert kwargs["page_no"] == 3
            assert kwargs["media_id"] == 11
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert response.content == b"\x89PNG-data"

    def test_book_page_allows_no_bearer(self, client: TestClient) -> None:
        """凭证即鉴权回归：书页位图无 Authorization 头也放行（<img> src 场景）。"""
        mock_session = AsyncMock()

        async def _override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = _override_get_db
        try:
            with patch(
                "app.api.v1.kb.book_render.render_book_page",
                new=AsyncMock(return_value=b"\x89PNG-data"),
            ):
                response = client.get(
                    "/api/v1/kb/books/11/pages/3",
                    params={"token": "t" * 43},
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")

    def test_subtitles_vtt_response(self, client: TestClient) -> None:
        with _as_user("user", 7, [7]):
            with patch(
                "app.api.v1.kb.subtitles.build_subtitle_vtt",
                new=AsyncMock(return_value="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n支撑位\n"),
            ):
                response = client.get("/api/v1/kb/media/11/subtitles.vtt")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/vtt")
        assert response.text.startswith("WEBVTT")
