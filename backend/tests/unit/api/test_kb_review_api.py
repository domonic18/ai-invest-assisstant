"""知识审核端点契约测试（/admin/kb 章节树 + 知识点工作台路由）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.kb import (
    KbChapterNode,
    KbChaptersResponse,
    KbKnowledgePointResponse,
    KbPointCounts,
    KbPointListResponse,
)

_TS = datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    mock_session = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.role = "admin"

    async def _override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_admin_user] = lambda: mock_user
    yield client, mock_session
    app.dependency_overrides.clear()


def _point_view(**overrides: object) -> KbKnowledgePointResponse:
    fields: dict[str, object] = {
        "id": 5,
        "source_id": 1,
        "media_id": 3,
        "episode_no": 7,
        "media_title": "第 7 集",
        "point_type": "concept",
        "title": "复利",
        "body": "正文",
        "excerpt": "摘抄",
        "related_ids": [9],
        "chapter_path": ["价值篇", "复利"],
        "status": "draft",
        "needs_review": False,
        "created_at": _TS,
        "updated_at": _TS,
    }
    fields.update(overrides)
    return KbKnowledgePointResponse(**fields)


def test_chapters_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    tree = KbChaptersResponse(
        draft=[KbChapterNode(id="1", title="价值篇", children=[])],
        published=None,
    )
    with patch(
        "app.services.kb.review_service.get_chapters",
        new=AsyncMock(return_value=tree),
    ):
        resp = http.get("/api/v1/admin/kb/sources/1/chapters")
    assert resp.status_code == 200
    body = resp.json()
    assert body["draft"][0]["title"] == "价值篇"
    assert body["published"] is None

    with patch(
        "app.services.kb.review_service.publish_chapters",
        new=AsyncMock(return_value=tree),
    ) as p_pub:
        resp = http.post(
            "/api/v1/admin/kb/sources/1/chapters/publish",
            json={"chapters": [{"id": "1", "title": "价值篇", "children": []}]},
        )
    assert resp.status_code == 200
    assert p_pub.call_args.kwargs["actor_id"] == 1


def test_list_points_route_with_query_params(admin_client: tuple) -> None:
    http, _ = admin_client
    listing = KbPointListResponse(
        items=[_point_view()],
        total=1,
        counts=KbPointCounts(draft=1, published=0, rejected=0, needs_review=0),
    )
    with patch(
        "app.services.kb.review_service.list_points",
        new=AsyncMock(return_value=listing),
    ) as p_list:
        resp = http.get(
            "/api/v1/admin/kb/sources/1/points?status=draft&page=2&page_size=10"
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["counts"]["draft"] == 1
    assert body["items"][0]["episodeNo"] == 7
    assert body["items"][0]["mediaTitle"] == "第 7 集"
    assert body["items"][0]["chapterPath"] == ["价值篇", "复利"]
    assert p_list.call_args.kwargs == {
        "status": "draft",
        "page": 2,
        "page_size": 10,
    }

    # 非法 status 枚举 → 422
    with patch(
        "app.services.kb.review_service.list_points",
        new=AsyncMock(return_value=listing),
    ):
        resp = http.get("/api/v1/admin/kb/sources/1/points?status=bogus")
    assert resp.status_code == 422


def test_point_mutation_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    view = _point_view()

    with patch(
        "app.services.kb.review_service.create_point",
        new=AsyncMock(return_value=view),
    ) as p_create:
        resp = http.post(
            "/api/v1/admin/kb/points",
            json={
                "mediaId": 3,
                "pointType": "method",
                "title": "现金流折现",
                "body": "正文",
            },
        )
    assert resp.status_code == 201
    assert p_create.call_args.kwargs["actor_id"] == 1

    with patch(
        "app.services.kb.review_service.patch_point",
        new=AsyncMock(return_value=view),
    ) as p_patch:
        resp = http.patch(
            "/api/v1/admin/kb/points/5",
            json={"title": "复利效应", "chapterPath": ["价值篇"]},
        )
    assert resp.status_code == 200
    assert resp.json()["title"] == "复利"
    assert p_patch.call_args.args[1] == 5
    assert p_patch.call_args.args[2].title == "复利效应"

    # 定位字段不可改（excerpt 在白名单外）→ 422
    resp = http.patch(
        "/api/v1/admin/kb/points/5",
        json={"excerpt": "试图改摘抄"},
    )
    assert resp.status_code == 422

    with patch(
        "app.services.kb.review_service.approve_point",
        new=AsyncMock(return_value=_point_view(status="published")),
    ) as p_approve:
        resp = http.post("/api/v1/admin/kb/points/5/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"
    assert p_approve.call_args.kwargs["actor_id"] == 1

    with patch(
        "app.services.kb.review_service.reject_point",
        new=AsyncMock(return_value=_point_view(status="rejected")),
    ) as p_reject:
        resp = http.post(
            "/api/v1/admin/kb/points/5/reject", json={"reason": "口径错误"}
        )
    assert resp.status_code == 200
    assert p_reject.call_args.args[2].reason == "口径错误"


def test_merge_route(admin_client: tuple) -> None:
    http, _ = admin_client
    with patch(
        "app.services.kb.review_service.merge_points",
        new=AsyncMock(return_value=_point_view()),
    ) as p_merge:
        resp = http.post(
            "/api/v1/admin/kb/points/merge",
            json={"targetId": 5, "sourceIds": [6, 7]},
        )
    assert resp.status_code == 200
    assert p_merge.call_args.args[1].target_id == 5
    assert p_merge.call_args.args[1].source_ids == [6, 7]
    assert p_merge.call_args.kwargs["actor_id"] == 1
