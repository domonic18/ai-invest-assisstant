"""playback_service 单测：凭证签发（含预签名直链）、校验矩阵、VTT、书页渲染与原图签发。"""

from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.models.kb import KbImageAsset, KbSource
from app.models.user import User
from app.services.kb import book_render, playback_service, subtitles


class _FakeRedis:
    """凭证读写假件（滑动窗口计数在用例内单独 patch）。"""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)


def _media(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": 11,
        "source_id": 3,
        "media_kind": "video",
        "episode_no": 2,
        "file_name": "ep02.mp4",
        "cos_key": "kb/3/ep02.mp4",
        "process_status": "done",
        "deleted_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _session(source: SimpleNamespace | None = None) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=source or _source())
    return session


def _source(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {"id": 3, "enabled": True, "deleted_at": None}
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
class TestIssuePlaybackToken:
    """凭证签发：视频/音频附同时效预签名直链，书素材 streamUrl 为 None。"""

    async def test_video_media_signed_with_presigned_url(self) -> None:
        redis = _FakeRedis()
        siblings = [
            _media(id=10, episode_no=1),
            _media(id=11, episode_no=2),
            _media(id=12, episode_no=3),
        ]
        minio = MagicMock()
        minio.get_presigned_url = AsyncMock(return_value="https://cos/signed")
        with (
            patch(
                "app.services.kb.playback_service.get_redis", return_value=redis
            ),
            patch(
                "app.services.kb.playback_service.get_minio_service",
                return_value=minio,
            ),
            patch(
                "app.services.kb.playback_service.media_repository.get",
                new=AsyncMock(return_value=_media()),
            ),
            patch(
                "app.services.kb.playback_service.media_repository.list_by_source",
                new=AsyncMock(return_value=siblings),
            ),
        ):
            result = await playback_service.issue_playback_token(
                _session(), user_id=7, media_id=11
            )
        assert result.prev_media_id == 10
        assert result.next_media_id == 12
        assert result.expires_in == 1800
        assert result.stream_url == "https://cos/signed"
        assert result.page_count is None
        [stored] = redis.store.values()
        assert '"userId": 7' in stored and '"mediaId": 11' in stored
        minio.get_presigned_url.assert_awaited_once_with(
            "kb/3/ep02.mp4", expires=timedelta(seconds=1800)
        )

    async def test_book_media_has_no_neighbors_and_no_stream_url(self) -> None:
        redis = _FakeRedis()
        minio = MagicMock()
        minio.get_presigned_url = AsyncMock(return_value="https://cos/signed")
        with (
            patch(
                "app.services.kb.playback_service.get_redis", return_value=redis
            ),
            patch(
                "app.services.kb.playback_service.get_minio_service",
                return_value=minio,
            ),
            patch(
                "app.services.kb.playback_service.media_repository.get",
                new=AsyncMock(
                    return_value=_media(
                        media_kind="book",
                        episode_no=None,
                        file_name="book.pdf",
                        page_count=120,
                    )
                ),
            ),
        ):
            result = await playback_service.issue_playback_token(
                _session(), user_id=7, media_id=11
            )
        assert result.prev_media_id is None
        assert result.next_media_id is None
        assert result.page_count == 120
        # 书页仍走 token 代理渲染水印，不签发直链
        assert result.stream_url is None
        minio.get_presigned_url.assert_not_awaited()


@pytest.mark.unit
class TestIssueImageUrl:
    """原图短时效预签名：按需签发 15min URL；资产/素材不可见按 404 隐藏。"""

    def _asset(self) -> SimpleNamespace:
        return SimpleNamespace(id=5, media_id=11, cos_key="kb/3/img-raw.png")

    def _dual_session(
        self, asset: SimpleNamespace | None, source: SimpleNamespace | None
    ) -> AsyncMock:
        session = AsyncMock()

        async def _get(model: type, _pk: int) -> object | None:
            if model is KbImageAsset:
                return asset
            if model is KbSource:
                return source
            return None

        session.get = AsyncMock(side_effect=_get)
        return session

    async def test_issues_short_lived_presigned_url(self) -> None:
        minio = MagicMock()
        minio.get_presigned_url = AsyncMock(return_value="https://cos/signed")
        with (
            patch(
                "app.services.kb.playback_service.get_minio_service",
                return_value=minio,
            ),
            patch(
                "app.services.kb.playback_service.media_repository.get",
                new=AsyncMock(return_value=_media()),
            ),
        ):
            result = await playback_service.issue_image_url(
                self._dual_session(self._asset(), _source()), image_id=5
            )
        assert result.url == "https://cos/signed"
        assert result.expires_in == 900
        minio.get_presigned_url.assert_awaited_once_with(
            "kb/3/img-raw.png", expires=timedelta(seconds=900)
        )

    async def test_missing_asset_404(self) -> None:
        with pytest.raises(NotFoundError):
            await playback_service.issue_image_url(
                self._dual_session(None, _source()), image_id=5
            )

    async def test_disabled_source_hides_media(self) -> None:
        with (
            patch(
                "app.services.kb.playback_service.media_repository.get",
                new=AsyncMock(return_value=_media()),
            ),
            pytest.raises(NotFoundError),
        ):
            await playback_service.issue_image_url(
                self._dual_session(self._asset(), _source(enabled=False)),
                image_id=5,
            )


@pytest.mark.unit
class TestTokenValidationMatrix:
    """凭证矩阵（经书页端点，token 校验的现存消费者）：
    未知/畸形/素材错配 → 401 + kb.security.denied 审计。

    审计归属依赖凭证 ``{userId}.`` 前缀或载荷；无前缀凭证无法归属账号
    （审计表 actor_id 非空约束）→ 仅结构化日志，不落审计表。
    """

    async def _assert_denied(
        self, redis: _FakeRedis, token: str, *, expected_actor: int | None
    ) -> None:
        session = _session()
        audit = AsyncMock()
        with (
            patch(
                "app.services.kb.playback_service.get_redis", return_value=redis
            ),
            patch(
                "app.services.kb.playback_service.record_audit", new=audit
            ),
            patch(
                "app.services.kb.playback_service._bump_denial_count",
                new=AsyncMock(return_value=1),
            ),
        ):
            with pytest.raises(UnauthorizedError):
                await book_render.render_book_page(
                    session, media_id=11, page_no=1, token=token
                )
        if expected_actor is None:
            assert audit.await_count == 0
            return
        assert audit.await_count == 1
        assert audit.await_args.kwargs["action"] == "kb.security.denied"
        assert audit.await_args.kwargs["actor_id"] == expected_actor
        session.commit.assert_awaited()

    async def test_unknown_token_attributed_by_prefix(self) -> None:
        await self._assert_denied(
            _FakeRedis(), "7." + "x" * 41, expected_actor=7
        )

    async def test_forged_prefix_at_missing_user_no_audit(self) -> None:
        """伪造前缀指向不存在账号：401 拒绝但不触发审计表 FK 违约。"""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        audit = AsyncMock()
        with (
            patch(
                "app.services.kb.playback_service.get_redis",
                return_value=_FakeRedis(),
            ),
            patch(
                "app.services.kb.playback_service.record_audit", new=audit
            ),
        ):
            with pytest.raises(UnauthorizedError):
                await book_render.render_book_page(
                    session, media_id=11, page_no=1, token="42." + "x" * 41
                )
        assert audit.await_count == 0

    async def test_unprefixed_token_denied_without_audit(self) -> None:
        await self._assert_denied(_FakeRedis(), "x" * 43, expected_actor=None)

    async def test_missing_token_denied_without_audit(self) -> None:
        await self._assert_denied(_FakeRedis(), "", expected_actor=None)

    async def test_malformed_token_denied(self) -> None:
        redis = _FakeRedis()
        redis.store["kb:playback:7.t"] = "not-json"
        await self._assert_denied(redis, "7.t", expected_actor=7)

    async def test_media_mismatch_denied(self) -> None:
        redis = _FakeRedis()
        redis.store["kb:playback:t"] = '{"userId": 7, "mediaId": 99}'
        await self._assert_denied(redis, "t", expected_actor=7)


@pytest.mark.unit
class TestBuildSubtitleVtt:
    async def test_segments_rendered_as_cues(self) -> None:
        segments = [
            SimpleNamespace(
                seq_no=1, text="支撑位的判断", start_ms=0, end_ms=3500
            ),
            SimpleNamespace(seq_no=2, text="趋势线画法", start_ms=3500, end_ms=9000),
            SimpleNamespace(seq_no=3, text="无时间轴句", start_ms=None, end_ms=None),
            SimpleNamespace(
                seq_no=4, text="含箭头 --> 分隔", start_ms=9000, end_ms=12000
            ),
            SimpleNamespace(
                seq_no=5, text="倒序时间", start_ms=12000, end_ms=11000
            ),
        ]
        with (
            patch(
                "app.services.kb.playback_service.media_repository.get",
                new=AsyncMock(return_value=_media()),
            ),
            patch(
                "app.services.kb.playback_service.media_repository.list_segments",
                new=AsyncMock(return_value=segments),
            ),
        ):
            vtt = await subtitles.build_subtitle_vtt(
                _session(), media_id=11
            )
        lines = vtt.splitlines()
        assert lines[0] == "WEBVTT"
        assert "00:00:00.000 --> 00:00:03.500" in lines
        assert "00:00:03.500 --> 00:00:09.000" in lines
        assert "含箭头 → 分隔" in lines
        assert "无时间轴句" not in vtt
        assert "倒序时间" not in vtt


def _blank_pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.unit
class TestBookPageRender:
    def test_clean_page_render_png(self) -> None:
        png = book_render._render_clean_page(_blank_pdf_bytes(), 1)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_page_out_of_range_404(self) -> None:
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            book_render._render_clean_page(_blank_pdf_bytes(), 2)

    def test_watermark_modifies_image(self) -> None:
        buffer = BytesIO()
        Image.new("RGB", (400, 600), "white").save(buffer, format="PNG")
        clean = buffer.getvalue()
        marked = book_render._composite_watermark(
            clean, "测试用户 2026-09-21"
        )
        assert marked[:8] == b"\x89PNG\r\n\x1a\n"
        assert marked != clean

    async def test_render_book_page_caches_clean_png(self) -> None:
        redis = _FakeRedis()
        redis.store["kb:playback:t"] = '{"userId": 7, "mediaId": 11}'
        pdf_bytes = _blank_pdf_bytes()
        minio = MagicMock()
        minio.download_file = AsyncMock(return_value=pdf_bytes)
        book_render._PDF_CACHE.clear()
        book_render._PAGE_CACHE.clear()
        media = _media(
            media_kind="book", episode_no=None, file_name="book.pdf"
        )
        user = SimpleNamespace(id=7, username="张三", is_active=True)

        async def _get(model: type, _pk: int) -> object:
            if model is User:
                return user
            return _source()

        session = AsyncMock()
        session.get = AsyncMock(side_effect=_get)
        with (
            patch(
                "app.services.kb.playback_service.get_redis", return_value=redis
            ),
            patch(
                "app.services.kb.book_render.get_minio_service",
                return_value=minio,
            ),
            patch(
                "app.services.kb.playback_service.media_repository.get",
                new=AsyncMock(return_value=media),
            ),
        ):
            first = await book_render.render_book_page(
                session, media_id=11, page_no=1, token="t"
            )
            second = await book_render.render_book_page(
                session, media_id=11, page_no=1, token="t"
            )
        assert first[:8] == b"\x89PNG\r\n\x1a\n"
        # 第二次命中干净页缓存，MinIO 不再下载
        minio.download_file.assert_awaited_once()
        assert second != book_render._PAGE_CACHE.get((11, 1))

    async def test_render_book_page_user_gone_denied(self) -> None:
        redis = _FakeRedis()
        redis.store["kb:playback:t"] = '{"userId": 7, "mediaId": 11}'
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        with (
            patch(
                "app.services.kb.playback_service.get_redis", return_value=redis
            ),
            pytest.raises(UnauthorizedError),
        ):
            await book_render.render_book_page(
                session, media_id=11, page_no=1, token="t"
            )
