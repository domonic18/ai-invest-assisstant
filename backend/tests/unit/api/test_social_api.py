"""社媒情绪 API 端点契约测试（用户三端点 + 管理端 CRUD/status/ASR 配置/signer 状态）。"""

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.adapters.douyin.signer_client import SignerUnavailableError
from app.core.exceptions import BadRequestError, ConflictError
from app.dependencies import get_current_admin_user, get_db
from app.main import app
from app.schemas.social import (
    AsrConfigResponse,
    AsrConfigTestResponse,
    SocialAccountCardResponse,
    SocialAccountsResponse,
    SocialFeedItemResponse,
    SocialFeedResponse,
    SocialTargetResponse,
    SocialTimelineItemResponse,
    SocialTimelineResponse,
)

_SEC_UID = "MS4wLjABAAAA" + "a" * 20
_NOW = datetime(2026, 9, 15, 10, 0, 0)


@pytest.fixture
def admin_client(client) -> tuple[TestClient, AsyncMock]:
    """绕过管理员认证并注入 AsyncMock session 的客户端。"""
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


def _feed_item() -> SocialFeedItemResponse:
    return SocialFeedItemResponse(
        post_id=11,
        video_id="v123",
        platform="douyin",
        account_id=1,
        account_alias="财经大V",
        category="finance_kol",
        title="今日复盘",
        caption=None,
        topic_tags=["A股"],
        cover_url="https://img.example.com/1.jpg",
        duration_seconds=180,
        published_at=_NOW,
        digg_count=100,
        comment_count=50,
        share_count=10,
        transcript_missing=False,
        is_relevant=True,
        stance="bearish",
        confidence=0.9,
        core_arguments=["量能萎缩"],
        targets=[
            SocialTargetResponse(target_type="index", name="上证指数", code="000001")
        ],
        summary="短线承压",
    )


def _feed_response() -> SocialFeedResponse:
    return SocialFeedResponse(items=[_feed_item()], total=1, page=1, page_size=20)


def _account_mock() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        platform="douyin",
        sec_uid=_SEC_UID,
        alias="财经大V",
        category="finance_kol",
        poll_interval_minutes=60,
        is_active=True,
        remark=None,
        last_collected_at=_NOW,
        last_post_at=_NOW,
        last_error=None,
        last_error_at=None,
        created_at=datetime(2026, 9, 1, 0, 0, 0),
    )


@pytest.mark.unit
class TestUserSocialEndpoints:
    def test_sentiment_feed_wire_contract(self, client) -> None:
        with patch(
            "app.services.social.feed_service.get_feed",
            AsyncMock(return_value=_feed_response()),
        ):
            response = client.get("/api/v1/social/sentiment-feed")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["accountAlias"] == "财经大V"
        assert item["transcriptMissing"] is False
        assert item["coreArguments"] == ["量能萎缩"]
        assert item["targets"][0]["targetType"] == "index"
        assert "transcriptText" not in item

    def test_sentiment_feed_passes_filters(self, client) -> None:
        mock_get = AsyncMock(return_value=_feed_response())
        with patch("app.services.social.feed_service.get_feed", mock_get):
            client.get(
                "/api/v1/social/sentiment-feed"
                "?category=finance_kol&stance=bearish&hours=24"
                "&strong_only=true&page=2&page_size=50"
            )
        kwargs = mock_get.await_args.kwargs
        assert kwargs["category"] == "finance_kol"
        assert kwargs["stance"] == "bearish"
        assert kwargs["hours"] == 24
        assert kwargs["strong_only"] is True
        assert kwargs["page"] == 2
        assert kwargs["page_size"] == 50

    def test_sentiment_feed_defaults(self, client) -> None:
        mock_get = AsyncMock(return_value=_feed_response())
        with patch("app.services.social.feed_service.get_feed", mock_get):
            client.get("/api/v1/social/sentiment-feed")
        kwargs = mock_get.await_args.kwargs
        assert kwargs["category"] is None
        assert kwargs["stance"] is None
        assert kwargs["hours"] is None
        assert kwargs["strong_only"] is False
        assert kwargs["page"] == 1
        assert kwargs["page_size"] == 20

    @pytest.mark.parametrize(
        "query",
        [
            "?page_size=101",
            "?hours=169",
            "?hours=0",
            "?stance=sideways",
            "?page=0",
        ],
    )
    def test_sentiment_feed_param_boundaries_rejected(self, client, query: str) -> None:
        response = client.get(f"/api/v1/social/sentiment-feed{query}")
        assert response.status_code == 422

    def test_sentiment_feed_param_upper_bounds_accepted(self, client) -> None:
        mock_get = AsyncMock(return_value=_feed_response())
        with patch("app.services.social.feed_service.get_feed", mock_get):
            response = client.get(
                "/api/v1/social/sentiment-feed?page_size=100&hours=168"
            )
        assert response.status_code == 200

    def test_account_cards(self, client) -> None:
        payload = SocialAccountsResponse(
            accounts=[
                SocialAccountCardResponse(
                    id=1,
                    alias="财经大V",
                    category="finance_kol",
                    last_post_at=_NOW,
                    latest_stance="bearish",
                    latest_confidence=0.9,
                    latest_summary="短线承压",
                    latest_cover_url=None,
                    bullish_count=2,
                    bearish_count=5,
                    neutral_count=1,
                )
            ]
        )
        with patch(
            "app.services.social.feed_service.get_account_cards",
            AsyncMock(return_value=payload),
        ):
            response = client.get("/api/v1/social/accounts?hours=72")
        assert response.status_code == 200
        card = response.json()["accounts"][0]
        assert card["bullishCount"] == 2
        assert card["bearishCount"] == 5
        assert card["latestStance"] == "bearish"

    def test_account_timeline(self, client) -> None:
        payload = SocialTimelineResponse(
            items=[
                SocialTimelineItemResponse(
                    post_id=11,
                    video_id="v123",
                    title="今日复盘",
                    published_at=_NOW,
                    stance="bullish",
                    confidence=0.8,
                    summary="看多",
                    transcript_missing=True,
                )
            ],
            total=1,
            page=2,
            page_size=20,
        )
        mock_get = AsyncMock(return_value=payload)
        with patch("app.services.social.feed_service.get_timeline", mock_get):
            response = client.get("/api/v1/social/accounts/7/timeline?page=2")
        assert response.status_code == 200
        assert mock_get.await_args.args[1] == 7
        item = response.json()["items"][0]
        assert item["transcriptMissing"] is True
        assert "transcriptText" not in item


@pytest.mark.unit
class TestAdminAccountEndpoints:
    def test_list_accounts(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_list = AsyncMock(return_value=([_account_mock()], 1))
        with patch(
            "app.repositories.social.account_repository.list_accounts_paged", mock_list
        ):
            response = client.get("/api/v1/admin/social/accounts")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["secUid"] == _SEC_UID
        assert data["items"][0]["pollIntervalMinutes"] == 60

    def test_create_account(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_create = AsyncMock(return_value=_account_mock())
        with patch("app.services.social.account_service.create_account", mock_create):
            response = client.post(
                "/api/v1/admin/social/accounts",
                json={
                    "platform": "douyin",
                    "secUidOrUrl": _SEC_UID,
                    "alias": "新账号",
                    "category": "finance_kol",
                    "pollIntervalMinutes": 30,
                },
            )
        assert response.status_code == 201
        assert response.json()["alias"] == "财经大V"
        kwargs = mock_create.await_args.kwargs
        assert kwargs["sec_uid_or_url"] == _SEC_UID
        assert kwargs["poll_interval_minutes"] == 30
        assert kwargs["actor_id"] == 1
        assert kwargs["ip"] == "testclient"

    def test_create_account_interval_fallback_default(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_create = AsyncMock(return_value=_account_mock())
        with patch("app.services.social.account_service.create_account", mock_create):
            client.post(
                "/api/v1/admin/social/accounts",
                json={"secUidOrUrl": _SEC_UID, "alias": "新账号"},
            )
        assert mock_create.await_args.kwargs["poll_interval_minutes"] == 60

    def test_create_account_conflict_maps_409(self, admin_client) -> None:
        client, mock_session = admin_client
        with patch(
            "app.services.social.account_service.create_account",
            AsyncMock(side_effect=ConflictError("该账号已登记")),
        ):
            response = client.post(
                "/api/v1/admin/social/accounts",
                json={"secUidOrUrl": _SEC_UID, "alias": "重复"},
            )
        assert response.status_code == 409

    def test_create_account_bad_request_maps_400(self, admin_client) -> None:
        client, mock_session = admin_client
        with patch(
            "app.services.social.account_service.create_account",
            AsyncMock(side_effect=BadRequestError("未知的账号分类: x")),
        ):
            response = client.post(
                "/api/v1/admin/social/accounts",
                json={"secUidOrUrl": _SEC_UID, "alias": "名", "category": "x"},
            )
        assert response.status_code == 400

    def test_update_account(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_update = AsyncMock(return_value=_account_mock())
        with patch("app.services.social.account_service.update_account", mock_update):
            response = client.patch(
                "/api/v1/admin/social/accounts/3",
                json={"alias": "改名", "isActive": False},
            )
        assert response.status_code == 200
        kwargs = mock_update.await_args.kwargs
        assert kwargs["alias"] == "改名"
        assert kwargs["is_active"] is False
        assert kwargs["actor_id"] == 1
        assert kwargs["ip"] == "testclient"

    def test_delete_account(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_delete = AsyncMock(return_value=None)
        with patch("app.services.social.account_service.delete_account", mock_delete):
            response = client.delete("/api/v1/admin/social/accounts/3")
        assert response.status_code == 204
        assert mock_delete.await_args.args[1] == 3
        assert mock_delete.await_args.kwargs["actor_id"] == 1


@pytest.mark.unit
class TestAdminBackfillEndpoint:
    def test_backfill_returns_dispatch_log(self, admin_client) -> None:
        client, _mock_session = admin_client
        fake_log = SimpleNamespace(id=42, celery_task_id="celery-abc")
        mock_trigger = AsyncMock(return_value=fake_log)
        with patch(
            "app.services.social.account_service.trigger_backfill", mock_trigger
        ):
            response = client.post("/api/v1/admin/social/accounts/3/backfill")
        assert response.status_code == 200
        assert response.json() == {"logId": 42, "celeryTaskId": "celery-abc"}
        assert mock_trigger.await_args.args[1] == 3
        assert mock_trigger.await_args.kwargs["actor_id"] == 1
        assert mock_trigger.await_args.kwargs["ip"] == "testclient"

    def test_backfill_missing_account_maps_404(self, admin_client) -> None:
        from app.core.exceptions import NotFoundError

        client, _mock_session = admin_client
        with patch(
            "app.services.social.account_service.trigger_backfill",
            AsyncMock(side_effect=NotFoundError("追踪账号不存在")),
        ):
            response = client.post("/api/v1/admin/social/accounts/99/backfill")
        assert response.status_code == 404


@pytest.mark.unit
class TestAdminPostsDebug:
    def test_posts_wire_contract(self, admin_client) -> None:
        client, _mock_session = admin_client
        row = {
            "video_id": "v123",
            "title": "今日复盘",
            "cover_url": "https://p.douyinpic.com/cover.jpeg",
            "published_at": _NOW,
            "transcript_status": "missing",
            "transcript_reason": "asr_disabled",
            "judged_at": None,
            "is_relevant": None,
            "stance": None,
            "confidence": None,
        }
        with (
            patch(
                "app.repositories.social.account_repository.get",
                AsyncMock(return_value=_account_mock()),
            ),
            patch(
                "app.repositories.social.post_repository.list_admin_posts",
                AsyncMock(return_value=[row]),
            ) as mock_list,
        ):
            response = client.get("/api/v1/admin/social/accounts/1/posts")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["videoId"] == "v123"
        assert item["coverUrl"] == "https://p.douyinpic.com/cover.jpeg"
        assert item["transcriptStatus"] == "missing"
        assert item["transcriptReason"] == "asr_disabled"
        assert item["judgedAt"] is None
        assert item["isRelevant"] is None
        assert mock_list.await_args.kwargs["limit"] == 30

    def test_posts_missing_account_maps_404(self, admin_client) -> None:
        client, _mock_session = admin_client
        with patch(
            "app.repositories.social.account_repository.get",
            AsyncMock(return_value=None),
        ):
            response = client.get("/api/v1/admin/social/accounts/99/posts")
        assert response.status_code == 404


@pytest.mark.unit
class TestAdminStatusEndpoint:
    def _patch_status_side(self, config_enabled: bool = True) -> SimpleNamespace:
        return SimpleNamespace(enabled=config_enabled, api_key_encrypted="enc")

    def test_status_aggregation(self, admin_client) -> None:
        client, mock_session = admin_client

        r_collected, r_failed, r_error = MagicMock(), MagicMock(), MagicMock()
        r_collected.scalar_one.return_value = 120
        r_failed.scalar_one.return_value = 2
        r_error.scalar_one_or_none.return_value = "SignatureError: verify failed"
        mock_session.get = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(side_effect=[r_collected, r_failed, r_error])

        with (
            patch(
                "app.services.social.collection_service.load_cookie_jars",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.repositories.social.post_repository.count_transcripts_since",
                AsyncMock(return_value={"ok": 5, "missing": 2, "pending": 3}),
            ),
            patch(
                "app.services.social.asr_config_service.get_or_create_config",
                AsyncMock(return_value=self._patch_status_side()),
            ),
        ):
            response = client.get("/api/v1/admin/social/status")

        assert response.status_code == 200
        data = response.json()
        assert data["douyin"]["cookieConfigured"] is False
        assert data["douyin"]["cookieJarsAvailable"] == 0
        assert data["douyin"]["todayCollected"] == 120
        assert data["douyin"]["todayFailed"] == 2
        assert data["douyin"]["signatureWarning"] is True
        assert data["asr"]["enabled"] is True
        assert data["asr"]["configured"] is True
        assert data["asr"]["todayTranscribed"] == 5
        assert data["asr"]["todayDegraded"] == 2
        assert data["asr"]["todayPending"] == 3

    def test_status_no_signature_warning_without_error(self, admin_client) -> None:
        client, mock_session = admin_client

        r_collected, r_failed, r_error = MagicMock(), MagicMock(), MagicMock()
        r_collected.scalar_one.return_value = 0
        r_failed.scalar_one.return_value = 0
        r_error.scalar_one_or_none.return_value = None
        mock_session.get = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(side_effect=[r_collected, r_failed, r_error])

        with (
            patch(
                "app.services.social.collection_service.load_cookie_jars",
                AsyncMock(return_value=[MagicMock(), MagicMock()]),
            ),
            patch(
                "app.repositories.social.post_repository.count_transcripts_since",
                AsyncMock(return_value={"ok": 0, "missing": 0}),
            ),
            patch(
                "app.services.social.asr_config_service.get_or_create_config",
                AsyncMock(
                    return_value=SimpleNamespace(
                        enabled=False, api_key_encrypted=None
                    )
                ),
            ),
        ):
            response = client.get("/api/v1/admin/social/status")

        assert response.status_code == 200
        data = response.json()
        assert data["douyin"]["cookieConfigured"] is True
        assert data["douyin"]["cookieJarsAvailable"] == 2
        assert data["douyin"]["signatureWarning"] is False
        assert data["asr"]["configured"] is False


@contextmanager
def _status_aggregates(mock_session: AsyncMock):
    """status 端点除 signer 外的聚合全部打桩（聚焦 signer 状态块）。"""
    r_collected, r_failed, r_error = MagicMock(), MagicMock(), MagicMock()
    r_collected.scalar_one.return_value = 0
    r_failed.scalar_one.return_value = 0
    r_error.scalar_one_or_none.return_value = None
    mock_session.get = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(side_effect=[r_collected, r_failed, r_error])
    with (
        patch(
            "app.services.social.collection_service.load_cookie_jars",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.repositories.social.post_repository.count_transcripts_since",
            AsyncMock(return_value={"ok": 0, "missing": 0}),
        ),
        patch(
            "app.services.social.asr_config_service.get_or_create_config",
            AsyncMock(
                return_value=SimpleNamespace(enabled=False, api_key_encrypted=None)
            ),
        ),
    ):
        yield


@pytest.mark.unit
class TestAdminSignerStatus:
    """signer 状态块三态：禁用/在线/不可达——探测异常降级为 reachable=False 不 500。"""

    def _get(
        self,
        client: TestClient,
        mock_session: AsyncMock,
        *,
        signer_url: str,
        health: AsyncMock | None,
    ) -> Any:
        with (
            _status_aggregates(mock_session),
            patch(
                "app.services.social.collection_service.get_settings",
                lambda: SimpleNamespace(douyin_signer_url=signer_url),
            ),
            patch(
                "app.services.social.collection_service.DouyinSignerClient"
            ) as client_mock,
        ):
            if health is not None:
                client_mock.return_value.health = health
            return client.get("/api/v1/admin/social/status")

    def test_disabled_when_url_empty(self, admin_client) -> None:
        client, mock_session = admin_client
        response = self._get(client, mock_session, signer_url="", health=None)
        assert response.status_code == 200
        assert response.json()["signer"] == {
            "enabled": False,
            "reachable": False,
            "warmSlots": None,
            "detail": None,
        }

    def test_enabled_reachable_reports_warm_slots(self, admin_client) -> None:
        client, mock_session = admin_client
        response = self._get(
            client,
            mock_session,
            signer_url="http://douyin-signer:8010",
            health=AsyncMock(
                return_value={"status": "ok", "driver": "playwright", "warm_slots": 2}
            ),
        )
        assert response.status_code == 200
        signer = response.json()["signer"]
        assert signer["enabled"] is True
        assert signer["reachable"] is True
        assert signer["warmSlots"] == 2
        assert signer["detail"] is None

    def test_enabled_unreachable_degrades_not_500(self, admin_client) -> None:
        client, mock_session = admin_client
        response = self._get(
            client,
            mock_session,
            signer_url="http://douyin-signer:8010",
            health=AsyncMock(side_effect=SignerUnavailableError("签名服务不可达")),
        )
        assert response.status_code == 200
        signer = response.json()["signer"]
        assert signer["enabled"] is True
        assert signer["reachable"] is False
        assert "不可达" in signer["detail"]

    def test_online_but_unhealthy_reports_detail(self, admin_client) -> None:
        client, mock_session = admin_client
        response = self._get(
            client,
            mock_session,
            signer_url="http://douyin-signer:8010",
            health=AsyncMock(
                return_value={"status": "unavailable", "detail": "browser 未启动"}
            ),
        )
        assert response.status_code == 200
        signer = response.json()["signer"]
        assert signer["reachable"] is False
        assert signer["warmSlots"] is None
        assert signer["detail"] == "browser 未启动"


@pytest.mark.unit
class TestAdminCookieEndpoint:
    def test_import_cookie_success(self, admin_client) -> None:
        client, _mock_session = admin_client
        with patch(
            "app.services.social.collection_service.import_cookie",
            AsyncMock(return_value=3),
        ) as mock_import:
            response = client.post(
                "/api/v1/admin/social/cookies", json={"cookie": "ttwid=abc; x=1"}
            )
        assert response.status_code == 200
        assert response.json() == {"cookieJarsAvailable": 3}
        kwargs = mock_import.await_args.kwargs
        assert kwargs["actor_id"] == 1
        assert kwargs["ip"] == "testclient"
        assert mock_import.await_args.args[1] == "ttwid=abc; x=1"

    def test_import_cookie_missing_ttwid_maps_400(self, admin_client) -> None:
        client, _mock_session = admin_client
        with patch(
            "app.services.social.collection_service.import_cookie",
            AsyncMock(side_effect=BadRequestError("Cookie 缺少 ttwid")),
        ):
            response = client.post(
                "/api/v1/admin/social/cookies", json={"cookie": "sessionid=xyz"}
            )
        assert response.status_code == 400
        assert "ttwid" in response.json()["detail"]


@pytest.mark.unit
class TestAdminAsrConfigEndpoints:
    def _asr_config_response(self) -> AsrConfigResponse:
        return AsrConfigResponse(
            provider="minimax",
            base_url="https://api.minimaxi.com",
            model="asr-1.0",
            api_key_masked="sk-1****abcd",
            api_key_configured=True,
            max_audio_seconds=600,
            hotwords=["美联储"],
            enabled=True,
            updated_at=_NOW,
        )

    def test_get_asr_config_masked(self, admin_client) -> None:
        client, mock_session = admin_client
        config = SimpleNamespace(
            provider="minimax",
            base_url="https://api.minimaxi.com",
            model="asr-1.0",
            api_key_encrypted="enc",
            api_key_masked="sk-1****abcd",
            max_audio_seconds=600,
            hotwords=["美联储"],
            enabled=True,
            updated_at=_NOW,
        )
        with patch(
            "app.services.social.asr_config_service.get_or_create_config",
            AsyncMock(return_value=config),
        ):
            response = client.get("/api/v1/admin/social/asr-config")
        assert response.status_code == 200
        data = response.json()
        assert data["apiKeyConfigured"] is True
        assert data["apiKeyMasked"] == "sk-1****abcd"
        assert "apiKey" not in data

    def test_update_asr_config_passes_actor(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_update = AsyncMock(return_value=self._asr_config_response())
        with patch(
            "app.services.social.asr_config_service.update_config", mock_update
        ):
            response = client.put(
                "/api/v1/admin/social/asr-config",
                json={"model": "asr-1.0", "apiKey": "sk-new", "enabled": True},
            )
        assert response.status_code == 200
        payload = mock_update.await_args.args[1]
        assert payload.api_key == "sk-new"
        assert mock_update.await_args.kwargs["actor_id"] == 1

    def test_test_asr_config_passes_actor(self, admin_client) -> None:
        client, mock_session = admin_client
        mock_test = AsyncMock(
            return_value=AsrConfigTestResponse(
                ok=True, latency_ms=123, text="样例", error=None
            )
        )
        with patch(
            "app.services.social.asr_config_service.test_connection", mock_test
        ):
            response = client.post("/api/v1/admin/social/asr-config/test")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert mock_test.await_args.kwargs["actor_id"] == 1
