"""事件故事线服务单测：建线阈值、续接幂等、幻觉过滤、锁与裁剪。"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.news import (
    StorylineAttachment,
    StorylineBatch,
    StorylineDraft,
    StorylineItemRef,
)
from app.services.news import storyline_service

_PUBLISH = datetime(2026, 9, 8, 3, 0, tzinfo=timezone.utc)


def _cand(msg_id: int, title: str = "标题", content: str = "内容") -> Any:
    tg = MagicMock()
    tg.cls_msg_id = msg_id
    tg.title = title
    tg.content = content
    tg.category = "重点"
    tg.stock_codes = []
    tg.publish_time = _PUBLISH
    return (tg, 85)


def _line(line_id: int = 12) -> Any:
    return MagicMock(
        id=line_id,
        title="既有线",
        summary="摘要",
        status="tracking",
        nodes=[{"time": _PUBLISH.isoformat(), "brief": "旧进展"}],
        last_seen_at=_PUBLISH,
    )


def _patch_lock(acquired: bool):
    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield acquired

    return patch(
        "app.services.news.storyline_service.redis_lock",
        side_effect=fake_lock,
    )


def _ref(msg_id: int) -> StorylineItemRef:
    return StorylineItemRef(source="cls_telegraph", item_id=str(msg_id))


def _repo_patches(
    candidates: list[Any],
    lines: list[Any],
    attach_counts: list[int] | None = None,
):
    """仓储函数统一打桩（attach_counts 供幂等轮次模拟，缺省透传任意调用）。"""
    attach = (
        AsyncMock(side_effect=attach_counts)
        if attach_counts is not None
        else AsyncMock()
    )
    return (
        patch.object(
            storyline_service.storyline_repository,
            "list_telegraph_candidates",
            AsyncMock(return_value=candidates),
        ),
        patch.object(
            storyline_service.storyline_repository,
            "list_open_lines",
            AsyncMock(return_value=lines),
        ),
        patch.object(
            storyline_service.storyline_repository,
            "insert_storyline",
            AsyncMock(return_value=99),
        ),
        patch.object(storyline_service.storyline_repository, "attach_items", attach),
        patch.object(
            storyline_service.storyline_repository,
            "refresh_progress",
            AsyncMock(),
        ),
    )


@pytest.mark.unit
class TestBuildStories:
    async def test_lock_busy_returns_zero(self) -> None:
        with _patch_lock(False):
            result = await storyline_service.build_stories(MagicMock())
        assert result == {"created": 0, "continued": 0, "attached": 0}

    async def test_no_candidates_returns_zero(self) -> None:
        with (
            _patch_lock(True),
            patch.object(
                storyline_service.storyline_repository,
                "list_telegraph_candidates",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await storyline_service.build_stories(MagicMock())
        assert result == {"created": 0, "continued": 0, "attached": 0}

    async def test_creates_line_when_five_reports(self) -> None:
        candidates = [_cand(i) for i in range(1, 6)]
        output = StorylineBatch(
            new_storylines=[
                StorylineDraft(
                    title="央行降准",
                    summary="降准落地",
                    status="tracking",
                    latest_brief="官宣降准",
                    item_refs=[_ref(i) for i in range(1, 6)],
                )
            ],
            attachments=[],
        )
        session = MagicMock()
        session.commit = AsyncMock()
        patches = _repo_patches(candidates, [], attach_counts=[5])
        with patches[0], patches[1], patches[2] as mock_insert, patches[3] as mock_attach, patches[4]:
            with (
                _patch_lock(True),
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                result = await storyline_service.build_stories(session)

        assert result == {"created": 1, "continued": 0, "attached": 5}
        mock_insert.assert_awaited_once()
        assert len(mock_attach.await_args.kwargs["refs"]) == 5
        session.commit.assert_awaited_once()

    async def test_draft_below_threshold_skipped(self) -> None:
        candidates = [_cand(i) for i in range(1, 4)]
        output = StorylineBatch(
            new_storylines=[
                StorylineDraft(
                    title="小事件",
                    summary="不足5篇",
                    status="tracking",
                    latest_brief="进展",
                    item_refs=[_ref(i) for i in range(1, 4)],
                )
            ],
            attachments=[],
        )
        session = MagicMock()
        session.commit = AsyncMock()
        patches = _repo_patches(candidates, [])
        with patches[0], patches[1], patches[2] as mock_insert, patches[3], patches[4]:
            with (
                _patch_lock(True),
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                result = await storyline_service.build_stories(session)

        assert result == {"created": 0, "continued": 0, "attached": 0}
        mock_insert.assert_not_awaited()

    async def test_hallucinated_refs_filtered(self) -> None:
        candidates = [_cand(i) for i in range(1, 6)]
        output = StorylineBatch(
            new_storylines=[
                StorylineDraft(
                    title="混合引用",
                    summary="含幻觉",
                    status="tracking",
                    latest_brief="进展",
                    item_refs=[_ref(i) for i in range(1, 6)]
                    + [_ref(999), _ref(888)],
                )
            ],
            attachments=[],
        )
        session = MagicMock()
        session.commit = AsyncMock()
        patches = _repo_patches(candidates, [], attach_counts=[5])
        with patches[0], patches[1], patches[2], patches[3] as mock_attach, patches[4]:
            with (
                _patch_lock(True),
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                result = await storyline_service.build_stories(session)

        assert result["created"] == 1
        assert len(mock_attach.await_args.kwargs["refs"]) == 5

    async def test_attachment_unknown_line_skipped(self) -> None:
        candidates = [_cand(1)]
        output = StorylineBatch(
            new_storylines=[],
            attachments=[
                StorylineAttachment(
                    storyline_id=404,
                    status="tracking",
                    latest_brief="幻觉线",
                    item_refs=[_ref(1)],
                )
            ],
        )
        session = MagicMock()
        session.commit = AsyncMock()
        patches = _repo_patches(candidates, [_line(12)])
        with patches[0], patches[1], patches[2], patches[3] as mock_attach, patches[4]:
            with (
                _patch_lock(True),
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                result = await storyline_service.build_stories(session)

        mock_attach.assert_not_awaited()
        assert result == {"created": 0, "continued": 0, "attached": 0}

    async def test_attachment_idempotent_no_progress_update(self) -> None:
        """attach 全量冲突（返回 0）时不刷新进度、不计续接——重复输出幂等。"""
        candidates = [_cand(1)]
        output = StorylineBatch(
            new_storylines=[],
            attachments=[
                StorylineAttachment(
                    storyline_id=12,
                    status="tracking",
                    latest_brief="续接",
                    item_refs=[_ref(1)],
                )
            ],
        )
        session = MagicMock()
        session.commit = AsyncMock()
        patches = _repo_patches(candidates, [_line(12)], attach_counts=[0])
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_refresh:
            with (
                _patch_lock(True),
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                result = await storyline_service.build_stories(session)

        assert result == {"created": 0, "continued": 0, "attached": 0}
        mock_refresh.assert_not_awaited()

    async def test_attachment_continues_line_appends_node(self) -> None:
        candidates = [_cand(1)]
        output = StorylineBatch(
            new_storylines=[],
            attachments=[
                StorylineAttachment(
                    storyline_id=12,
                    status="near_end",
                    latest_brief="接近尾声",
                    item_refs=[_ref(1)],
                )
            ],
        )
        session = MagicMock()
        session.commit = AsyncMock()
        patches = _repo_patches(candidates, [_line(12)], attach_counts=[1])
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_refresh:
            with (
                _patch_lock(True),
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                result = await storyline_service.build_stories(session)

        assert result == {"created": 0, "continued": 1, "attached": 1}
        kwargs = mock_refresh.await_args.kwargs
        assert kwargs["status"] == "near_end"
        # 旧节点 + 本轮新节点
        assert len(kwargs["nodes"]) == 2
        assert kwargs["nodes"][-1]["brief"] == "接近尾声"

    async def test_llm_failure_returns_zero(self) -> None:
        candidates = [_cand(i) for i in range(1, 6)]
        session = MagicMock()
        session.commit = AsyncMock()
        patches = _repo_patches(candidates, [])
        with patches[0], patches[1], patches[2] as mock_insert, patches[3], patches[4]:
            with (
                _patch_lock(True),
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(side_effect=ValueError("LLM 输出不符 schema")),
                ),
            ):
                result = await storyline_service.build_stories(session)

        assert result == {"created": 0, "continued": 0, "attached": 0}
        mock_insert.assert_not_awaited()
        session.commit.assert_not_awaited()


@pytest.mark.unit
class TestTrimToCap:
    def test_trims_oldest_beyond_cap(self) -> None:
        payload = [
            {"source": "cls_telegraph", "item_id": str(i), "content": "长" * 4000}
            for i in range(5)
        ]
        trimmed = storyline_service._trim_to_cap(list(payload))
        assert len(trimmed) < 5
        assert len(trimmed) >= 1
        # 自尾部（最旧）裁剪：保留的是前面的新条目
        assert trimmed[0]["item_id"] == "0"

    def test_keeps_small_batch(self) -> None:
        payload = [{"source": "cls_telegraph", "item_id": "1", "content": "短"}]
        assert storyline_service._trim_to_cap(list(payload)) == payload


@pytest.mark.unit
class TestUserOps:
    async def test_create_manual_conflict_when_item_in_line(self) -> None:
        with patch.object(
            storyline_service.storyline_repository,
            "find_item_line",
            AsyncMock(return_value=MagicMock(title="既有线")),
        ):
            with pytest.raises(ConflictError):
                await storyline_service.create_manual(
                    MagicMock(), user_id=1, source="cls_telegraph", item_id="1"
                )

    async def test_set_user_action_upserts(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        ai_line = MagicMock(origin="ai", user_id=None)
        with (
            patch.object(
                storyline_service.storyline_repository,
                "get_storyline",
                AsyncMock(return_value=ai_line),
            ),
            patch.object(
                storyline_service.storyline_repository,
                "upsert_user_action",
                AsyncMock(),
            ) as mock_upsert,
        ):
            await storyline_service.set_user_action(
                session, user_id=1, storyline_id=12, action="stopped"
            )
        mock_upsert.assert_awaited_once()
        assert mock_upsert.await_args.kwargs == {
            "user_id": 1,
            "storyline_id": 12,
            "action": "stopped",
        }
        session.commit.assert_awaited_once()

    async def test_set_user_action_foreign_manual_line_not_found(self) -> None:
        foreign_line = MagicMock(origin="manual", user_id=999)
        with patch.object(
            storyline_service.storyline_repository,
            "get_storyline",
            AsyncMock(return_value=foreign_line),
        ):
            with pytest.raises(NotFoundError):
                await storyline_service.set_user_action(
                    MagicMock(), user_id=1, storyline_id=12, action="active"
                )


@pytest.mark.unit
class TestFocusQueries:
    def _tg(self, msg_id: int = 1) -> Any:
        return MagicMock(
            cls_msg_id=msg_id,
            title="央行降准",
            content="<p>降准落地</p>",
            publish_time=_PUBLISH,
        )

    def _line_row(
        self, line_id: int = 12, origin: str = "ai", user_id: int | None = None
    ) -> Any:
        # SimpleNamespace：model_validate(from_attributes) 下 MagicMock 会自动
        # 造出 userAction 等幽灵属性导致 Literal 校验失败
        return SimpleNamespace(
            id=line_id,
            title="降准故事线",
            summary="摘要",
            status="tracking",
            origin=origin,
            user_id=user_id,
            report_count=6,
            first_seen_at=_PUBLISH,
            last_seen_at=_PUBLISH,
            latest_brief="官宣降准",
            nodes=[{"time": _PUBLISH.isoformat(), "brief": "官宣降准"}],
            user_action=None,
        )

    async def test_get_focus_assembles_factors_and_lines(self) -> None:
        detail = {
            "reason": "重磅",
            "factors": {"impact_scope": 90, "certainty": 80, "related_count": 30},
        }
        with (
            patch.object(
                storyline_service.storyline_repository,
                "list_today_highlights",
                AsyncMock(return_value=[(self._tg(), 85, detail)]),
            ),
            patch.object(
                storyline_service.storyline_repository,
                "list_focus_storylines",
                AsyncMock(return_value=[(self._line_row(), "active")]),
            ),
        ):
            focus = await storyline_service.get_focus(MagicMock(), user_id=1)

        assert len(focus.highlights) == 1
        item = focus.highlights[0]
        assert item.item_id == "1"
        assert item.score == 85
        assert item.factors is not None
        assert item.factors.impact_scope == 90
        assert item.reason == "重磅"
        line = focus.storylines[0]
        assert line.id == 12
        assert line.origin == "ai"
        assert line.user_action == "active"
        assert line.nodes[0].brief == "官宣降准"

    async def test_get_focus_legacy_score_without_factors(self) -> None:
        """存量评分行无 factors 构成：factors=None 透传（前端显示 —）。"""
        with (
            patch.object(
                storyline_service.storyline_repository,
                "list_today_highlights",
                AsyncMock(return_value=[(self._tg(), 85, {"reason": "旧版"})]),
            ),
            patch.object(
                storyline_service.storyline_repository,
                "list_focus_storylines",
                AsyncMock(return_value=[]),
            ),
        ):
            focus = await storyline_service.get_focus(MagicMock(), user_id=1)

        assert focus.highlights[0].factors is None
        assert focus.storylines == []

    async def test_get_story_detail_items_backfilled(self) -> None:
        ref = MagicMock(source="cls_telegraph", item_id="1")
        telegraph = MagicMock(
            title="快讯", content="<p>正文</p>", publish_time=_PUBLISH
        )
        with (
            patch.object(
                storyline_service.storyline_repository,
                "get_storyline",
                AsyncMock(return_value=self._line_row()),
            ),
            patch.object(
                storyline_service.storyline_repository,
                "get_user_action",
                AsyncMock(return_value=None),
            ),
            patch.object(
                storyline_service.storyline_repository,
                "list_storyline_items",
                AsyncMock(return_value=[(ref, telegraph, 85)]),
            ),
        ):
            detail = await storyline_service.get_story(
                MagicMock(), user_id=1, storyline_id=12
            )

        assert detail.items[0].item_id == "1"
        assert detail.items[0].title == "快讯"
        assert detail.items[0].score == 85
        assert detail.user_action is None

    async def test_get_story_foreign_manual_line_not_found(self) -> None:
        with patch.object(
            storyline_service.storyline_repository,
            "get_storyline",
            AsyncMock(return_value=self._line_row(origin="manual", user_id=999)),
        ):
            with pytest.raises(NotFoundError):
                await storyline_service.get_story(
                    MagicMock(), user_id=1, storyline_id=12
                )

    async def test_get_story_own_manual_line_visible(self) -> None:
        ref = MagicMock(source="cls_telegraph", item_id="1")
        with (
            patch.object(
                storyline_service.storyline_repository,
                "get_storyline",
                AsyncMock(return_value=self._line_row(origin="manual", user_id=1)),
            ),
            patch.object(
                storyline_service.storyline_repository,
                "get_user_action",
                AsyncMock(return_value="stopped"),
            ),
            patch.object(
                storyline_service.storyline_repository,
                "list_storyline_items",
                AsyncMock(return_value=[(ref, None, None)]),
            ),
        ):
            detail = await storyline_service.get_story(
                MagicMock(), user_id=1, storyline_id=12
            )

        assert detail.origin == "manual"
        assert detail.user_action == "stopped"
        # 电报已不存在：条目保留引用、回显字段为空
        assert detail.items[0].title is None
        assert detail.items[0].publish_time is None


@pytest.mark.unit
class TestNewsStorylineCollector:
    async def test_run_success_and_skipped(self) -> None:
        from collector.spiders.news_storyline import NewsStorylineCollector

        collector = NewsStorylineCollector(config={})
        with patch(
            "app.services.news.storyline_service.build_stories",
            AsyncMock(
                return_value={"created": 1, "continued": 1, "attached": 6}
            ),
        ):
            result = await collector.run()
        assert result.status.value == "success"
        assert result.items_stored == 6

        with patch(
            "app.services.news.storyline_service.build_stories",
            AsyncMock(return_value={"created": 0, "continued": 0, "attached": 0}),
        ):
            result = await collector.run()
        assert result.status.value == "skipped"

    async def test_run_failure(self) -> None:
        from collector.spiders.news_storyline import NewsStorylineCollector

        collector = NewsStorylineCollector(config={})
        with patch(
            "app.services.news.storyline_service.build_stories",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            result = await collector.run()
        assert result.status.value == "failed"
