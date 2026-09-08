"""我的订阅服务单测：命中扫描、水位推进、渠道过滤与 CRUD 归属。"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.services.news import subscription_service

_NOW = datetime(2026, 9, 8, 6, 0, tzinfo=timezone.utc)


def _sub(sub_id: int = 1, keyword: str = "降准", channels: list[str] | None = None):
    return MagicMock(
        id=sub_id,
        keyword=keyword,
        channels=channels,
        push_enabled=False,
        enabled=True,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _tg(msg_id: int, title: str, content: str = ""):
    tg = MagicMock()
    tg.cls_msg_id = msg_id
    tg.title = title
    tg.content = content
    return tg


def _redis(get_value: Any = None):
    client = MagicMock()
    client.get = AsyncMock(return_value=get_value)
    client.set = AsyncMock()
    return patch(
        "app.services.news.subscription_service.get_redis",
        MagicMock(return_value=client),
    ), client


@pytest.mark.unit
class TestMatchPending:
    async def test_no_subscriptions_returns_zero(self) -> None:
        with patch.object(
            subscription_service.subscription_repository,
            "list_enabled",
            AsyncMock(return_value=[]),
        ):
            result = await subscription_service.match_pending(MagicMock())
        assert result == {"matched": 0, "scanned": 0}

    async def test_matches_keyword_and_advances_watermark(self) -> None:
        rows = [
            _tg(101, "央行宣布降准 50bp", "释放长期资金"),
            _tg(102, "盘中播报", "指数微涨"),
            _tg(103, "美联储降息预期升温", "Fed official dovish"),
        ]
        redis_patch, client = _redis(get_value=None)
        with (
            redis_patch,
            patch.object(
                subscription_service.subscription_repository,
                "list_enabled",
                AsyncMock(return_value=[_sub(1, "降准"), _sub(2, "不存在的词")]),
            ),
            patch.object(
                subscription_service.subscription_repository,
                "list_telegraph_after",
                AsyncMock(return_value=rows),
            ) as mock_scan,
            patch.object(
                subscription_service.subscription_repository,
                "insert_hits",
                AsyncMock(return_value=1),
            ) as mock_insert,
        ):
            session = MagicMock()
            session.commit = AsyncMock()
            result = await subscription_service.match_pending(session)

        assert result == {"matched": 1, "scanned": 3}
        # 首跑无水位 → 最新批扫描；水位推进到最大 cls_msg_id
        mock_scan.assert_awaited_once()
        assert mock_scan.await_args.kwargs["after_id"] == 0
        client.set.assert_awaited_once_with("news:subscription:watermark", 103)
        hit_rows = mock_insert.await_args.args[1]
        assert hit_rows == [
            {"subscription_id": 1, "source": "cls_telegraph", "item_id": "101"}
        ]

    async def test_case_insensitive_match(self) -> None:
        rows = [_tg(201, "美股夜盘", "Fed officials signal a cut")]
        redis_patch, _client = _redis(get_value=200)
        with (
            redis_patch,
            patch.object(
                subscription_service.subscription_repository,
                "list_enabled",
                AsyncMock(return_value=[_sub(1, "fed")]),
            ),
            patch.object(
                subscription_service.subscription_repository,
                "list_telegraph_after",
                AsyncMock(return_value=rows),
            ),
            patch.object(
                subscription_service.subscription_repository,
                "insert_hits",
                AsyncMock(return_value=1),
            ) as mock_insert,
        ):
            session = MagicMock()
            session.commit = AsyncMock()
            await subscription_service.match_pending(session)

        assert mock_insert.await_args.args[1][0]["item_id"] == "201"

    async def test_channel_filter_skips_telegraph(self) -> None:
        """订阅渠道不含 cls_telegraph 时不参与电报命中。"""
        rows = [_tg(301, "降准落地")]
        redis_patch, _client = _redis(get_value=300)
        with (
            redis_patch,
            patch.object(
                subscription_service.subscription_repository,
                "list_enabled",
                AsyncMock(return_value=[_sub(1, "降准", channels=["sina_news"])]),
            ),
            patch.object(
                subscription_service.subscription_repository,
                "list_telegraph_after",
                AsyncMock(return_value=rows),
            ),
            patch.object(
                subscription_service.subscription_repository,
                "insert_hits",
                AsyncMock(return_value=0),
            ) as mock_insert,
        ):
            session = MagicMock()
            session.commit = AsyncMock()
            result = await subscription_service.match_pending(session)

        assert result["matched"] == 0
        assert mock_insert.await_args.args[1] == []

    async def test_no_new_items_keeps_watermark(self) -> None:
        redis_patch, client = _redis(get_value=103)
        with (
            redis_patch,
            patch.object(
                subscription_service.subscription_repository,
                "list_enabled",
                AsyncMock(return_value=[_sub(1, "降准")]),
            ),
            patch.object(
                subscription_service.subscription_repository,
                "list_telegraph_after",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await subscription_service.match_pending(MagicMock())
        assert result == {"matched": 0, "scanned": 0}
        client.set.assert_not_awaited()


def _session_returning(value: Any) -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=value)))
        )
    )
    return session


@pytest.mark.unit
class TestCrud:
    async def test_create_duplicate_keyword_conflict(self) -> None:
        with pytest.raises(ConflictError):
            await subscription_service.create(
                _session_returning(_sub(1, "降准")),
                user_id=1,
                keyword="降准",
                channels=None,
            )

    async def test_create_strips_and_persists(self) -> None:
        session = _session_returning(None)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        created = await subscription_service.create(
            session, user_id=1, keyword=" 降准 ", channels=None
        )
        assert created.keyword == "降准"
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    async def test_update_not_owned_raises_404(self) -> None:
        with pytest.raises(NotFoundError):
            await subscription_service.update(
                _session_returning(None),
                user_id=2,
                subscription_id=1,
                enabled=False,
            )

    async def test_delete_owned_succeeds(self) -> None:
        session = _session_returning(_sub(1))
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        await subscription_service.delete(session, user_id=1, subscription_id=1)
        session.delete.assert_awaited_once()

    async def test_list_for_user_backfills_hit_stats(self) -> None:
        subs = [_sub(1, "降准"), _sub(2, "加息")]
        session = _session_returning(None)
        # list 查询与 _get_owned 共用 execute 形状：scalars().all() 返回列表
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=subs)))
            )
        )
        with patch.object(
            subscription_service.subscription_repository,
            "hit_stats",
            AsyncMock(return_value={1: (3, _NOW)}),
        ):
            items = await subscription_service.list_for_user(session, user_id=1)
        assert len(items) == 2
        assert items[0]["hit_count"] == 3
        assert items[0]["last_hit_at"] == _NOW
        assert items[1]["hit_count"] == 0
        assert items[1]["last_hit_at"] is None


@pytest.mark.unit
class TestNewsSubscriptionMatchCollector:
    async def test_run_success_and_skipped(self) -> None:
        from collector.spiders.news_subscription_match import NewsSubscriptionMatchCollector

        collector = NewsSubscriptionMatchCollector(config={})
        with patch(
            "app.services.news.subscription_service.match_pending",
            AsyncMock(return_value={"matched": 2, "scanned": 10}),
        ):
            result = await collector.run()
        assert result.status.value == "success"
        assert result.items_stored == 2

        with patch(
            "app.services.news.subscription_service.match_pending",
            AsyncMock(return_value={"matched": 0, "scanned": 0}),
        ):
            result = await collector.run()
        assert result.status.value == "skipped"

    async def test_run_zero_hits_with_scan_is_success(self) -> None:
        from collector.spiders.news_subscription_match import NewsSubscriptionMatchCollector

        collector = NewsSubscriptionMatchCollector(config={})
        with patch(
            "app.services.news.subscription_service.match_pending",
            AsyncMock(return_value={"matched": 0, "scanned": 5}),
        ):
            result = await collector.run()
        assert result.status.value == "success"
        assert result.items_stored == 0

    async def test_run_failure(self) -> None:
        from collector.spiders.news_subscription_match import NewsSubscriptionMatchCollector

        collector = NewsSubscriptionMatchCollector(config={})
        with patch(
            "app.services.news.subscription_service.match_pending",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            result = await collector.run()
        assert result.status.value == "failed"
