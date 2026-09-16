"""采集服务单测：两阶段落库、增量判新、续拉上限、ASR 降级、断点续传。"""

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


def _video(
    video_id: str,
    published_at: datetime,
    play_url: str | None = "https://v.douyin.com/media.mp4",
) -> DouyinVideo:
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


def _patch_pending(video_ids: list[str]) -> object:
    return patch.object(
        collection_service.post_repository,
        "list_pending_video_ids",
        AsyncMock(return_value=video_ids),
    )


def _patch_insert(rowcount: int = 1) -> AsyncMock:
    return AsyncMock(return_value=rowcount)


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
    async def test_two_phase_listing_then_transcribe(self) -> None:
        """阶段一 shell 行（pending）即落库并推进水位；阶段二逐条回写转写结果。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        account = _account(last_post_at=datetime(2026, 9, 10, 12, 0, tzinfo=_T))
        published = datetime(2026, 9, 11, 8, 0, tzinfo=_T)
        pages = [
            _page(
                [
                    _video("v_new", published),
                    _video("v_old", datetime(2026, 9, 9, 8, 0, tzinfo=_T)),
                    _video("v_floor", datetime(2026, 9, 10, 6, 0, tzinfo=_T)),
                ],
                has_more=False,
            )
        ]
        insert = _patch_insert()
        update = AsyncMock()
        api_patch, _api_mock = _patch_api(pages)
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory(["v_old"]),
                _patch_pending([]),
                patch.object(
                    collection_service.post_repository, "insert_posts", insert
                ),
                patch.object(
                    collection_service.post_repository, "update_transcript", update
                ),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_OK),
                ),
            ):
                stats = await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        # 阶段一：新视频 shell 行落库，pending 无文稿，水位推进
        rows = insert.await_args.args[1]
        assert [row["video_id"] for row in rows] == ["v_new"]
        assert rows[0]["transcript_status"] == "pending"
        assert rows[0]["transcript_text"] is None
        assert rows[0]["transcript_meta"] == {"reason": "pending"}
        assert account.last_post_at == published
        assert account.last_error is None
        # 阶段二：转写结果按 (platform, video_id) 回写
        assert stats == {"listed": 1, "resumed": 0, "ok": 1, "degraded": 0}
        kwargs = update.await_args.kwargs
        assert update.await_args.args[1:] == ("douyin", "v_new")
        assert kwargs["status"] == "ok"
        assert kwargs["text"] == "文本"
        session.commit.assert_awaited()

    async def test_max_pages_cap(self) -> None:
        """has_more 持续为真时最多续拉 SOCIAL_MAX_LIST_PAGES 页；ASR 降级记账。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        account = _account()
        endless = _page(
            [_video("v9", datetime(2026, 9, 11, 8, 0, tzinfo=_T))], has_more=True, cursor=1
        )
        update = AsyncMock()
        api_patch, api_mock = _patch_api([endless, endless, endless, endless])
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory([]),
                _patch_pending([]),
                patch.object(
                    collection_service.post_repository,
                    "insert_posts",
                    _patch_insert(),
                ),
                patch.object(
                    collection_service.post_repository, "update_transcript", update
                ),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_DOWN),
                ),
            ):
                stats = await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        assert (
            api_mock.return_value.get_user_posts.await_count
            == collection_service.SOCIAL_MAX_LIST_PAGES
        )
        assert stats["degraded"] == 1
        kwargs = update.await_args.kwargs
        assert kwargs["status"] == "missing"
        assert kwargs["text"] is None
        assert kwargs["meta"] == {"reason": "asr_disabled"}

    async def test_missing_play_addr_skips_asr(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        account = _account()
        video = _video("v1", datetime(2026, 9, 11, 8, 0, tzinfo=_T), play_url=None)
        transcribe = AsyncMock()
        update = AsyncMock()
        api_patch, _api_mock = _patch_api([_page([video], has_more=False)])
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory([]),
                _patch_pending([]),
                patch.object(
                    collection_service.post_repository,
                    "insert_posts",
                    _patch_insert(),
                ),
                patch.object(
                    collection_service.post_repository, "update_transcript", update
                ),
                patch.object(collection_service, "transcribe_from_url", transcribe),
            ):
                await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        transcribe.assert_not_awaited()
        assert update.await_args.kwargs["meta"] == {"reason": "play_addr_missing"}

    async def test_write_failure_continues_and_rolls_back(self) -> None:
        """单条回写失败 rollback 后继续本轮（下轮续传兜底），不阻塞其余条目。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        account = _account()
        published = datetime(2026, 9, 11, 8, 0, tzinfo=_T)
        videos = [_video("v1", published), _video("v2", published)]
        update = AsyncMock(side_effect=[RuntimeError("db down"), None])
        api_patch, _api_mock = _patch_api([_page(videos, has_more=False)])
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory([]),
                _patch_pending([]),
                patch.object(
                    collection_service.post_repository,
                    "insert_posts",
                    _patch_insert(),
                ),
                patch.object(
                    collection_service.post_repository, "update_transcript", update
                ),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_OK),
                ),
            ):
                stats = await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        assert stats == {"listed": 2, "resumed": 0, "ok": 1, "degraded": 1}
        session.rollback.assert_awaited_once()

    async def test_resume_pending_rows_from_listing_window(self) -> None:
        """断点续传：库内 pending 行在本次 listing 窗口内恢复 play_url 被转写。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        account = _account()
        published = datetime(2026, 9, 11, 8, 0, tzinfo=_T)
        resumed_video = _video("v_pending", published)
        insert = _patch_insert()
        update = AsyncMock()
        api_patch, _api_mock = _patch_api([_page([resumed_video], has_more=False)])
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory(["v_pending"]),  # 已入库（shell 行），不再是新内容
                _patch_pending(["v_pending"]),  # 但转写仍 pending
                patch.object(
                    collection_service.post_repository, "insert_posts", insert
                ),
                patch.object(
                    collection_service.post_repository, "update_transcript", update
                ),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_OK),
                ),
            ):
                stats = await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        insert.assert_not_awaited()  # 无新内容，不重复落库
        assert stats == {"listed": 0, "resumed": 1, "ok": 1, "degraded": 0}
        assert update.await_args.args[1:] == ("douyin", "v_pending")


@pytest.mark.unit
class TestBackfill:
    async def test_backfill_ignores_floor(self) -> None:
        """backfill=True 忽略 last_post_at 地板，早于地板的历史视频也采集。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        account = _account(last_post_at=datetime(2026, 9, 10, 12, 0, tzinfo=_T))
        pages = [
            _page(
                [
                    _video("v_old", datetime(2026, 9, 9, 8, 0, tzinfo=_T)),
                    _video("v_older", datetime(2026, 8, 1, 8, 0, tzinfo=_T)),
                ],
                has_more=False,
            )
        ]
        insert = _patch_insert()
        api_patch, _api_mock = _patch_api(pages)
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory([]),
                _patch_pending([]),
                patch.object(
                    collection_service.post_repository, "insert_posts", insert
                ),
                patch.object(
                    collection_service.post_repository,
                    "update_transcript",
                    AsyncMock(),
                ),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_DOWN),
                ),
            ):
                stats = await collect_account(
                    session, MagicMock(), account, backfill=True
                )
        finally:
            api_patch.stop()

        rows = insert.await_args.args[1]
        assert [row["video_id"] for row in rows] == ["v_old", "v_older"]
        assert account.last_post_at == datetime(2026, 9, 9, 8, 0, tzinfo=_T)
        assert stats["listed"] == 2

    async def test_incremental_floor_regression(self) -> None:
        """backfill=False 回归：同一批历史视频仍被地板过滤，不落库。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        account = _account(last_post_at=datetime(2026, 9, 10, 12, 0, tzinfo=_T))
        pages = [
            _page(
                [
                    _video("v_old", datetime(2026, 9, 9, 8, 0, tzinfo=_T)),
                    _video("v_older", datetime(2026, 8, 1, 8, 0, tzinfo=_T)),
                ],
                has_more=False,
            )
        ]
        insert = _patch_insert()
        api_patch, _api_mock = _patch_api(pages)
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory([]),
                _patch_pending([]),
                patch.object(
                    collection_service.post_repository, "insert_posts", insert
                ),
                patch.object(
                    collection_service.post_repository,
                    "update_transcript",
                    AsyncMock(),
                ),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_DOWN),
                ),
            ):
                stats = await collect_account(session, MagicMock(), account)
        finally:
            api_patch.stop()

        insert.assert_not_awaited()
        assert stats == {"listed": 0, "resumed": 0, "ok": 0, "degraded": 0}

    async def test_backfill_deep_page_cap(self) -> None:
        """has_more 持续为真时，回填模式放宽到 SOCIAL_BACKFILL_MAX_LIST_PAGES 页。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        account = _account()
        endless = _page(
            [_video("v9", datetime(2026, 9, 11, 8, 0, tzinfo=_T))], has_more=True, cursor=1
        )
        api_patch, api_mock = _patch_api([endless] * 12)
        try:
            with (
                patch.object(collection_service, "DouyinTransport", MagicMock()),
                _patch_inventory([]),
                _patch_pending([]),
                patch.object(
                    collection_service.post_repository,
                    "insert_posts",
                    _patch_insert(),
                ),
                patch.object(
                    collection_service.post_repository,
                    "update_transcript",
                    AsyncMock(),
                ),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_DOWN),
                ),
            ):
                await collect_account(session, MagicMock(), account, backfill=True)
        finally:
            api_patch.stop()

        assert (
            api_mock.return_value.get_user_posts.await_count
            == collection_service.SOCIAL_BACKFILL_MAX_LIST_PAGES
        )


@pytest.mark.unit
class TestCollectAllAccounts:
    async def test_account_invalid_recorded_and_continues(self) -> None:
        """账号失效记 last_error 不停用，其余账号继续采集并汇总统计。"""
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
                _patch_pending([]),
                patch.object(
                    collection_service.post_repository,
                    "insert_posts",
                    _patch_insert(),
                ),
                patch.object(
                    collection_service.post_repository,
                    "update_transcript",
                    AsyncMock(),
                ),
                patch.object(
                    collection_service,
                    "transcribe_from_url",
                    AsyncMock(return_value=_ASR_DOWN),
                ),
            ):
                stats = await collect_all_accounts(session)
        finally:
            api_patch.stop()

        assert stats == {"listed": 1, "resumed": 0, "ok": 0, "degraded": 1}
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
    async def test_run_maps_stats_to_result(self) -> None:
        from collector.spiders.social_video import SocialVideoCollector

        collector = SocialVideoCollector(
            config={"source": "douyin", "data_type": "social_video"}
        )
        stats = {"listed": 2, "resumed": 1, "ok": 2, "degraded": 1}
        with patch.object(
            collection_service,
            "collect_all_accounts",
            AsyncMock(return_value=stats),
        ) as mock_collect:
            result = await collector.run(account_id=3, backfill=True)
        assert mock_collect.await_args.kwargs["account_id"] == 3
        assert mock_collect.await_args.kwargs["backfill"] is True
        assert result.status.value == "success"
        assert result.items_collected == 3
        assert result.items_stored == 3
        assert result.metadata == stats

    async def test_run_channel_failure_failed(self) -> None:
        from collector.spiders.social_video import SocialVideoCollector

        collector = SocialVideoCollector(
            config={"source": "douyin", "data_type": "social_video"}
        )
        with patch.object(
            collection_service,
            "collect_all_accounts",
            AsyncMock(side_effect=RiskControlError("HTTP 403")),
        ):
            result = await collector.run()
        assert result.status.value == "failed"
        assert "403" in result.errors[0]


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
