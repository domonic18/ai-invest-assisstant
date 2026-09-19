"""知识库管理端点契约测试（/admin/kb/sources 与 /admin/kb/media）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.kb import KbUploadSessionPart, KbUploadSessionPartUrl, KbUploadSessionResponse

_TS = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


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


def _set_both(mock: MagicMock, snake: str, value: object) -> None:
    # pydantic from_attributes 按 camel 别名优先读取，Mock 需两种拼写都置值
    head, *rest = snake.split("_")
    camel = head + "".join(part.capitalize() for part in rest)
    setattr(mock, snake, value)
    setattr(mock, camel, value)


def _source_view_mock(**overrides: object) -> MagicMock:
    fields: dict[str, object] = {
        "id": 1,
        "source_type": "course",
        "name": "价值投资课",
        "author": None,
        "description": None,
        "enabled": True,
        "storage_bytes": 0,
        "pending_cleanup_bytes": 0,
        "deleted_at": None,
        "created_at": _TS,
        "updated_at": _TS,
    }
    fields.update(overrides)
    view = MagicMock()
    for snake, value in fields.items():
        _set_both(view, snake, value)
    return view


def _media_view_mock(**overrides: object) -> MagicMock:
    fields: dict[str, object] = {
        "id": 5,
        "source_id": 1,
        "media_kind": "video",
        "episode_no": 1,
        "title": "第 1 集",
        "file_name": "L01.mp4",
        "file_size": 100,
        "file_hash": "a" * 32,
        "duration_seconds": 60,
        "page_count": None,
        "process_status": "uploaded",
        "process_error": None,
        "process_meta": {},
        "edited_at": None,
        "deleted_at": None,
        "point_count": 0,
        "dirty_count": 0,
        "created_at": _TS,
        "updated_at": _TS,
    }
    fields.update(overrides)
    view = MagicMock()
    for snake, value in fields.items():
        _set_both(view, snake, value)
    return view


def test_source_crud_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    with patch(
        "app.services.kb.source_service.create_source",
        new=AsyncMock(return_value=_source_view_mock()),
    ) as p_create:
        resp = http.post(
            "/api/v1/admin/kb/sources",
            json={"sourceType": "course", "name": "价值投资课"},
        )
    assert resp.status_code == 201
    assert resp.json()["sourceType"] == "course"
    assert p_create.call_args.kwargs["actor_id"] == 1

    with patch(
        "app.services.kb.source_service.list_sources",
        new=AsyncMock(return_value=[_source_view_mock()]),
    ):
        resp = http.get("/api/v1/admin/kb/sources")
    assert resp.status_code == 200
    assert resp.json()[0]["storageBytes"] == 0

    with patch(
        "app.services.kb.source_service.soft_delete_source", new=AsyncMock(return_value=None)
    ) as p_del:
        resp = http.delete("/api/v1/admin/kb/sources/1")
    assert resp.status_code == 204
    assert p_del.call_args.args[1] == 1
    assert p_del.call_args.kwargs["actor_id"] == 1

    with patch(
        "app.services.kb.source_service.restore_source",
        new=AsyncMock(return_value=_source_view_mock()),
    ):
        resp = http.post("/api/v1/admin/kb/sources/1/restore")
    assert resp.status_code == 200


def test_media_init_and_uploaded_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    init_result = MagicMock()
    for snake, value in {
        "media_id": 5,
        "file_name": "L01.mp4",
        "cos_key": "kb/1/5/L01.mp4",
        "upload_url": "https://cos/put",
        "conflict_with": None,
    }.items():
        _set_both(init_result, snake, value)
    init_resp = MagicMock()
    init_resp.items = [init_result]

    with patch(
        "app.services.kb.media_service.init_uploads", new=AsyncMock(return_value=init_resp)
    ) as p_init:
        resp = http.post(
            "/api/v1/admin/kb/sources/1/media/init",
            json={
                "items": [
                    {
                        "fileName": "L01.mp4",
                        "relativePath": "L01.mp4",
                        "size": 100,
                        "hash": "a" * 32,
                        "mediaKind": "video",
                    }
                ]
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["mediaId"] == 5
    assert body["items"][0]["uploadUrl"] == "https://cos/put"
    assert p_init.call_args.args[1] == 1
    assert p_init.call_args.args[2].items[0].file_name == "L01.mp4"
    assert p_init.call_args.kwargs["actor_id"] == 1

    with patch(
        "app.services.kb.media_service.confirm_uploaded",
        new=AsyncMock(return_value=_media_view_mock()),
    ) as p_up:
        resp = http.post("/api/v1/admin/kb/media/5/uploaded")
    assert resp.status_code == 200
    assert resp.json()["processStatus"] == "uploaded"
    assert p_up.call_args.args[1] == 5


def test_media_upload_session_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    session_resp = KbUploadSessionResponse(
        media_id=5,
        upload_id="uid-1",
        part_size=16 * 1024 * 1024,
        part_count=2,
        completed_parts=[
            KbUploadSessionPart(part_number=1, etag="aa", size=60),
        ],
        part_urls=[KbUploadSessionPartUrl(part_number=2, url="https://cos/part2")],
    )
    with patch(
        "app.services.kb.media_service.create_upload_session",
        new=AsyncMock(return_value=session_resp),
    ) as p_session:
        resp = http.post(
            "/api/v1/admin/kb/media/5/upload-session",
            json={"partSize": 16 * 1024 * 1024, "partCount": 2},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["uploadId"] == "uid-1"
    assert body["completedParts"][0]["partNumber"] == 1
    assert body["partUrls"][0]["url"] == "https://cos/part2"
    assert p_session.call_args.args[1] == 5
    assert p_session.call_args.args[2].part_count == 2

    with patch(
        "app.services.kb.media_service.abort_upload_session", new=AsyncMock()
    ) as p_abort:
        resp = http.delete("/api/v1/admin/kb/media/5/upload-session")
    assert resp.status_code == 204
    assert p_abort.call_args.args[1] == 5


def test_media_list_and_patch_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    with patch(
        "app.services.kb.media_service.list_media",
        new=AsyncMock(return_value=[_media_view_mock()]),
    ):
        resp = http.get("/api/v1/admin/kb/sources/1/media")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["pointCount"] == 0
    assert body[0]["episodeNo"] == 1

    with patch(
        "app.services.kb.media_service.patch_media",
        new=AsyncMock(return_value=_media_view_mock(episode_no=3, episodeNo=3)),
    ) as p_patch:
        resp = http.patch("/api/v1/admin/kb/media/5", json={"episodeNo": 3})
    assert resp.status_code == 200
    assert resp.json()["episodeNo"] == 3
    assert p_patch.call_args.args[2].episode_no == 3

    with patch(
        "app.services.kb.media_service.soft_delete_media", new=AsyncMock(return_value=None)
    ):
        resp = http.delete("/api/v1/admin/kb/media/5")
    assert resp.status_code == 204


def test_cost_gate_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    item = MagicMock()
    for snake, value in {
        "media_id": 5,
        "title": "第 1 集",
        "media_kind": "video",
        "duration_seconds": 1800,
        "asr_cost": 1.5,
        "clean_tokens": 4800,
        "estimated_cost": 1.5,
    }.items():
        _set_both(item, snake, value)
    est_resp = MagicMock()
    est_resp.currency = "CNY"
    est_resp.Currency = "CNY"
    est_resp.items = [item]
    est_resp.total = 1.5
    est_resp.Total = 1.5

    with patch(
        "app.services.kb.cost_service.estimate_cost",
        new=AsyncMock(return_value=est_resp),
    ) as p_est:
        resp = http.post(
            "/api/v1/admin/kb/cost-estimate",
            json={"sourceId": 1, "mediaIds": [5]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["asrCost"] == 1.5
    assert body["total"] == 1.5
    assert p_est.call_args.args[1:] == (1, [5])

    confirm_resp = MagicMock()
    confirm_resp.queued_ids = [5]
    confirm_resp.queuedIds = [5]
    with patch(
        "app.services.kb.cost_service.confirm_cost",
        new=AsyncMock(return_value=[5]),
    ) as p_conf:
        resp = http.post(
            "/api/v1/admin/kb/sources/1/confirm-cost",
            json={"mediaIds": [5]},
        )
    assert resp.status_code == 200
    assert resp.json()["queuedIds"] == [5]
    assert p_conf.call_args.args[1:] == (1, [5])
    assert p_conf.call_args.kwargs["actor_id"] == 1


def test_transcript_routes(admin_client: tuple) -> None:
    http, _ = admin_client
    seg = MagicMock()
    _set_both(seg, "seq_no", 1)
    seg.text = "句壹"
    _set_both(seg, "start_ms", 0)
    _set_both(seg, "end_ms", 10000)
    _set_both(seg, "page_start", None)
    _set_both(seg, "page_end", None)
    transcript_resp = MagicMock()
    _set_both(transcript_resp, "media_id", 5)
    _set_both(transcript_resp, "edited_at", None)
    transcript_resp.segments = [seg]

    with patch(
        "app.services.kb.transcript_service.get_transcript",
        new=AsyncMock(return_value=transcript_resp),
    ) as p_get:
        resp = http.get("/api/v1/admin/kb/sources/1/transcript/5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["segments"][0]["seqNo"] == 1
    assert p_get.call_args.args[1:] == (1, 5)

    save_resp = MagicMock()
    _set_both(save_resp, "media_id", 5)
    _set_both(save_resp, "edited_at", _TS)
    _set_both(save_resp, "updated_count", 1)
    with patch(
        "app.services.kb.transcript_service.save_transcript",
        new=AsyncMock(return_value=save_resp),
    ) as p_save:
        resp = http.put(
            "/api/v1/admin/kb/sources/1/transcript/5",
            json={"segments": [{"seqNo": 1, "text": "句壹（校正）"}]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updatedCount"] == 1
    assert body["editedAt"].startswith("2026-09-18")
    assert p_save.call_args.args[1:3] == (1, 5)
    assert p_save.call_args.args[3].segments[0].seq_no == 1
    assert p_save.call_args.kwargs["actor_id"] == 1


def test_kb_routes_require_admin(client) -> None:
    app.dependency_overrides.clear()
    assert client.get("/api/v1/admin/kb/sources").status_code in (401, 403)
    assert client.post(
        "/api/v1/admin/kb/sources/1/media/init", json={"items": []}
    ).status_code in (401, 403)
    assert client.post(
        "/api/v1/admin/kb/cost-estimate", json={"sourceId": 1, "mediaIds": [1]}
    ).status_code in (401, 403)
