"""采集服务单测：增量判新、续拉上限、ASR 降级、账号级失败记账。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.douyin import DouyinVideo
from app.adapters.douyin.exceptions import AccountInvalidError, RiskControlError
from app.services.social import collection_service
from app.services.social.asr_service import TranscribeOutcome
from app.services.social.collection_service import (
    collect_account,
    collect_all_accounts,
    load_cookie_jars,
)

_T = timezone.utc


def _account(account_id: int = 1, last_post_at: datetime | None = None) -> MagicMock:
    account = MagicMock()
    account.id = account_id
    account.platform = "douyin"
    account.sec_uid = "MS4wLjABAAAA" + "a" * 20
    account.last_post_at = last_post_at
    account.last_error = None
    account.last_error_at = None
    return account


def _video(video_id: str, published_at: datetime, play_url: str | None = "https://v.douyin.com/media.mp4") -> DouyinVideo:
    return DouyinVideo(
        video_id=video_id,
        caption=f"{video_id} 的口播描述",
        published_at=published_at,
        play_url=play_url,
    )


def _page(videos: list[DouyinVideo], has_more: bool, cursor: int = 0) -> MagicMock:
    page = MagicMock()
    page.videos = videos
    page.has_more = has_more
    page.max_cursor = cursor
    return page


def _patch_api(pages: list[MagicMock]) -> tuple[object, MagicMock]:
    """替换 collection_service 命名空间内的 DouyinWebApi 为按序回页的桩。"""
    patcher = patch.object(collection_service, "DouyinWebApi")
    mock = patcher.start()
    mock.return_value.get_user_posts = AsyncMock(side_effect=list(pages))
    return patcher, mock


def _patch_inventory(video_ids: list[str]) -> object:
    return patch.object(
        collection_service.post_repository,
        "list_video_ids",
        AsyncMock(return_value=video_ids),
    )


_ASR_OK = TranscribeOutcome("文本", {"provider": "minimax"}, None)
_ASR_DOWN = TranscribeOutcome(None, None, "asr_disabled")


@pytest.mark.unit
class TestLoadCookieJars:
    async def test_no_setting_returns_empty(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        assert await load_cookie_jars(session) == []

    async def test_decrypt_failure_returns_empty(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=MagicMock(value="broken-token"))
        with patch.object(
            collection_service,
            "decrypt_jar_payload",
            side_effect=ValueError("bad"),
        ):
            assert await load_cookie_jars(session) == []

    async def test_unusable_jars_filtered(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=MagicMock(value="token"))
        with patch.object(
            collection_service,
            "decrypt_jar_payload",
            return_value=["ttwid=good", "no-marker", "ttwid=also-good"],
        ):
            jars = await load_cookie_jars(session)
        assert jars == ["ttwid=good", "ttwid=also-good"]


@pytest.mark.unit
class TestCollectAccount:
    async def test_incremental_skip_and_floor(self) -> None:
        """库存 video_id 与 last_post_at 地板双保险跳过，只留新内容。"""
        session = MagicMock()
        session.commit = AsyncMock()
        account = _account(last_post_at=datetime(2026, 9, 10, 12, 0, tzinfo=_T))
        pages = [
            _page(
                [
                    _video("v_new", datetime(2026, 9, 11, 8, 0, tzinfo=_T)),
                    _video("v_old", datetime(2026, 9, 9, 8, 0, tzinfo=_T)),
                    _video("v_floor", datetime(2026, 9, 10, 6, 0, tzinfo=_T)),
                ],
                has_more=False,
            )
        ]
        api_patch, api_mock = _patch_api(pages)
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory(["v_old"]),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_OK),
                ),
            ):
                rows = await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        assert [row["video_id"] for row in rows] == ["v_new"]
        assert rows[0]["transcript_status"] == "ok"
        assert rows[0]["transcript_text"] == "文本"
        assert account.last_post_at == datetime(2026, 9, 11, 8, 0, tzinfo=_T)
        assert account.last_error is None

    async def test_max_pages_cap(self) -> None:
        """has_more 持续为真时最多续拉 SOCIAL_MAX_LIST_PAGES 页。"""
        session = MagicMock()
        session.commit = AsyncMock()
        account = _account()
        endless = _page(
            [_video("v9", datetime(2026, 9, 11, 8, 0, tzinfo=_T))], has_more=True, cursor=1
        )
        api_patch, api_mock = _patch_api([endless, endless, endless, endless])
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory([]),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_DOWN),
                ),
            ):
                rows = await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        assert (
            api_mock.return_value.get_user_posts.await_count
            == collection_service.SOCIAL_MAX_LIST_PAGES
        )
        assert rows and rows[0]["transcript_status"] == "missing"
        assert rows[0]["transcript_meta"] == {"reason": "asr_disabled"}

    async def test_missing_play_addr_skips_asr(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        account = _account()
        video = _video("v1", datetime(2026, 9, 11, 8, 0, tzinfo=_T), play_url=None)
        transcribe = AsyncMock()
        api_patch, _api_mock = _patch_api([_page([video], has_more=False)])
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory([]),
                patch.object(collection_service, "transcribe_from_url", transcribe),
            ):
                rows = await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        transcribe.assert_not_awaited()
        assert rows[0]["transcript_status"] == "missing"
        assert rows[0]["transcript_meta"] == {"reason": "play_addr_missing"}


@pytest.mark.unit
class TestCollectAllAccounts:
    async def test_account_invalid_recorded_and_continues(self) -> None:
        """账号失效记 last_error 不停用，其余账号继续采集。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.get = AsyncMock(return_value=None)
        bad = _account(account_id=1)
        good = _account(account_id=2)
        pages = [_page([_video("v2", datetime(2026, 9, 11, 8, 0, tzinfo=_T))], False)]

        api_patch = patch.object(collection_service, "DouyinWebApi")
        api_mock = api_patch.start()
        api_mock.return_value.get_user_posts = AsyncMock(
            side_effect=[AccountInvalidError("sec_uid 失效"), *pages]
        )
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                patch.object(
                    collection_service.account_repository,
                    "list_accounts",
                    AsyncMock(return_value=[bad, good]),
                ),
                _patch_inventory([]),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_DOWN),
                ),
            ):
                rows = await collect_all_accounts(session)
        finally:
            api_patch.stop()

        assert [row["account_id"] for row in rows] == [2]
        assert bad.last_error and "sec_uid" in bad.last_error
        assert bad.last_error_at is not None

    async def test_channel_failure_propagates(self) -> None:
        """风控/签名等通道级失败向上传播（任务置 FAILED，F-MON 告警）。"""
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        account = _account()
        api_patch = patch.object(collection_service, "DouyinWebApi")
        api_mock = api_patch.start()
        api_mock.return_value.get_user_posts = AsyncMock(
            side_effect=RiskControlError("HTTP 403: 验证码")
        )
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                patch.object(
                    collection_service.account_repository,
                    "list_accounts",
                    AsyncMock(return_value=[account]),
                ),
                _patch_inventory([]),
            ):
                with pytest.raises(RiskControlError):
                    await collect_all_accounts(session)
        finally:
            api_patch.stop()


@pytest.mark.unit
class TestTransportInjection:
    async def test_signer_built_from_settings_url(self) -> None:
        """douyin_signer_url 非空时注入 build_signer 产物；为空时 None（禁用回退）。"""
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        for url, expected in (("http://douyin-signer:8010", True), ("", False)):
            with (
                patch.object(collection_service, "DouyinTransport") as transport_mock,
                patch.object(collection_service, "DouyinWebApi"),
                patch.object(
                    collection_service.account_repository,
                    "list_accounts",
                    AsyncMock(return_value=[]),
                ),
                patch.object(
                    collection_service,
                    "get_settings",
                    lambda: SimpleNamespace(douyin_signer_url=url),
                ),
            ):
                await collect_all_accounts(session)
            assert (transport_mock.call_args.kwargs["signer"] is not None) is expected


@pytest.mark.unit
class TestSocialVideoCollector:
    def test_storage_declaration(self) -> None:
        from collector.spiders.social_video import SocialVideoCollector

        collector = SocialVideoCollector(
            config={"source": "douyin", "data_type": "social_video"}
        )
        assert collector.table == "social_post"
        assert collector.conflict_key == "platform, video_id"

    async def test_collect_delegates_to_service(self) -> None:
        from collector.spiders.social_video import SocialVideoCollector

        collector = SocialVideoCollector(
            config={"source": "douyin", "data_type": "social_video"}
        )
        with patch.object(
            collection_service,
            "collect_all_accounts",
            AsyncMock(return_value=[{"video_id": "v1"}]),
        ) as mock_collect:
            rows = await collector.collect(account_id=None)
        assert rows == [{"video_id": "v1"}]
        mock_collect.assert_awaited_once()


@pytest.mark.unit
class TestImportCookie:
    async def test_missing_ttwid_raises(self) -> None:
        from app.core.exceptions import BadRequestError

        session = MagicMock()
        with pytest.raises(BadRequestError):
            await collection_service.import_cookie(
                session, "sessionid=xyz", actor_id=1
            )

    async def test_thin_cookie_rejected(self) -> None:
        """ttwid+单键薄 jar 过不了作品接口风控（200 空响应），低于下限直接拒绝。"""
        from app.core.exceptions import BadRequestError

        session = MagicMock()
        with (
            patch.object(
                collection_service, "encrypt_jar_payload", AsyncMock()
            ) as mock_enc,
            patch.object(collection_service, "record_audit", AsyncMock()),
        ):
            with pytest.raises(BadRequestError, match="2 组键值"):
                await collection_service.import_cookie(
                    session, "ttwid=abc; sessionid=x", actor_id=1
                )
        mock_enc.assert_not_called()

    async def test_import_encrypts_and_audits(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=None)
        session.commit = AsyncMock()
        session.add = MagicMock()
        with (
            patch.object(
                collection_service, "encrypt_jar_payload", return_value="ENC"
            ) as mock_enc,
            patch.object(
                collection_service, "load_cookie_jars", AsyncMock(return_value=[])
            ),
            patch.object(
                collection_service, "record_audit", AsyncMock()
            ) as mock_audit,
        ):
            jars = await collection_service.import_cookie(
                session, "ttwid=abc; sessionid=x; uifid=y", actor_id=1, ip="1.2.3.4"
            )
        assert jars == 1
        setting = session.add.call_args.args[0]
        assert setting.key == collection_service.COOKIE_SETTING_KEY
        assert setting.value == "ENC"
        mock_enc.assert_called_once_with(["ttwid=abc; sessionid=x; uifid=y"])
        kwargs = mock_audit.await_args.kwargs
        assert kwargs["action"] == "social.cookie.import"
        assert kwargs["detail"] == {"cookieJars": 1}
        session.commit.assert_awaited_once()

    async def test_same_ttwid_replaces_existing_jar(self) -> None:
        session = MagicMock()
        session.get = AsyncMock(return_value=MagicMock(value="token"))
        session.commit = AsyncMock()
        with (
            patch.object(
                collection_service, "encrypt_jar_payload", return_value="ENC"
            ) as mock_enc,
            patch.object(
                collection_service,
                "load_cookie_jars",
                AsyncMock(return_value=["ttwid=old; x=1", "ttwid=other; y=2"]),
            ),
            patch.object(collection_service, "record_audit", AsyncMock()),
        ):
            jars = await collection_service.import_cookie(
                session, "Cookie: ttwid=old; z=3; w=4", actor_id=1
            )
        assert jars == 2
        mock_enc.assert_called_once_with(["ttwid=other; y=2", "ttwid=old; z=3; w=4"])
