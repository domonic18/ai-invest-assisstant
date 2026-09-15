"""情绪判断服务单测：锁、双保险幂等、幻觉过滤、判后清稿、退避传播。"""

from contextlib import ExitStack, asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.social import (
    SocialJudgmentBatch,
    SocialJudgmentBatchItem,
    SocialTarget,
)
from app.services.social import sentiment_service
from app.services.social.sentiment_service import (
    SocialJudgmentNotReadyError,
    judge_pending,
)

_TEMPLATE = "判 {count} 条：{items_json} 热词：{hotwords}"


def _post(post_id: int, transcript: str = "口播内容") -> MagicMock:
    post = MagicMock()
    post.id = post_id
    post.title = f"标题{post_id}"
    post.caption = "文案"
    post.topic_tags = ["财经"]
    post.transcript_text = transcript
    return post


def _item(post_id: int, **overrides: Any) -> SocialJudgmentBatchItem:
    fields: dict[str, Any] = {
        "relevance": True,
        "stance": "bearish",
        "confidence": 0.9,
        "core_arguments": ["论点"],
        "targets": [],
        "summary": "摘要",
    }
    fields.update(overrides)
    return SocialJudgmentBatchItem(post_id=post_id, **fields)


def _patch_lock(acquired: bool):
    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield acquired

    return patch(
        "app.services.social.sentiment_service.redis_lock",
        side_effect=fake_lock,
    )


def _patch_pipeline(
    posts: list[MagicMock],
    output: SocialJudgmentBatch | Exception,
    stock_codes: set[str] = frozenset({"600519"}),
    stale_ids: list[int] | None = None,
):
    """打桩判断主链：待判扫描 / LLM 输出 / 幻觉基准 / 滞留清理。"""
    run_mock = (
        AsyncMock(return_value=output)
        if not isinstance(output, Exception)
        else AsyncMock(side_effect=output)
    )
    return (
        patch.object(
            sentiment_service.post_repository,
            "list_pending_posts",
            AsyncMock(return_value=posts),
        ),
        patch("app.skills.prompt.load_skill_prompt", return_value=MagicMock(
            user_prompt_template=_TEMPLATE
        )),
        patch.object(
            sentiment_service, "_load_hotwords", AsyncMock(return_value=["北向资金"])
        ),
        patch("app.agent.runtime.structured.run_structured", run_mock),
        patch.object(
            sentiment_service, "_valid_stock_codes", AsyncMock(return_value=stock_codes)
        ),
        patch(
            "app.services.quota.user_llm_service.resolve_llm",
            AsyncMock(return_value=(SimpleNamespace(model_name="test-model"), "system")),
        ),
        patch.object(
            sentiment_service.post_repository,
            "list_stale_transcript_ids",
            AsyncMock(return_value=stale_ids or []),
        ),
        patch.object(
            sentiment_service.post_repository, "clear_transcripts", AsyncMock()
        ),
    )


@pytest.mark.unit
class TestJudgePending:
    async def test_lock_busy_returns_zero(self) -> None:
        with _patch_lock(False):
            result = await judge_pending(MagicMock())
        assert result == {"judged": 0, "cleaned": 0}

    async def test_empty_batch_cleans_stale_only(self) -> None:
        session = MagicMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        patches = _patch_pipeline([], SocialJudgmentBatch(items=[]), stale_ids=[7, 8])
        with ExitStack() as stack:
            stack.enter_context(_patch_lock(True))
            for p in patches:
                stack.enter_context(p)
            with patch.object(
                sentiment_service.post_repository,
                "upsert_sentiments",
                AsyncMock(),
            ) as mock_upsert:
                result = await judge_pending(session)

        assert result == {"judged": 0, "cleaned": 2}
        mock_upsert.assert_not_awaited()

    async def test_judges_writes_and_purges_transcripts(self) -> None:
        """主链：写判断 → 标已判（判后清稿）→ 清滞留。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        posts = [_post(1), _post(2)]
        output = SocialJudgmentBatch(
            items=[
                _item(1, targets=[SocialTarget(
                    target_type="stock", name="贵州茅台", code="600519"
                )]),
                _item(2, stance="neutral", confidence=0.4),
            ]
        )
        patches = _patch_pipeline(posts, output, stale_ids=[9])
        with ExitStack() as stack:
            stack.enter_context(_patch_lock(True))
            for p in patches:
                stack.enter_context(p)
            with (
                patch.object(
                    sentiment_service.post_repository,
                    "upsert_sentiments",
                    AsyncMock(return_value=2),
                ) as mock_upsert,
                patch.object(
                    sentiment_service.post_repository,
                    "mark_judged",
                    AsyncMock(),
                ) as mock_mark,
            ):
                result = await judge_pending(session)

        assert result == {"judged": 2, "cleaned": 1}
        rows = mock_upsert.await_args.args[1]
        assert all(row["model_name"] == "test-model" for row in rows)
        assert rows[0]["targets"] == [
            {"target_type": "stock", "name": "贵州茅台", "code": "600519"}
        ]
        assert mock_mark.await_args.args[1] == [1, 2]

    async def test_unknown_post_id_ignored_stays_pending(self) -> None:
        """LLM 编造的 post_id 忽略（条目保持待判），只写真实条目。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        posts = [_post(1)]
        output = SocialJudgmentBatch(
            items=[_item(1), _item(999, stance="bullish", confidence=0.5)]
        )
        patches = _patch_pipeline(posts, output)
        with ExitStack() as stack:
            stack.enter_context(_patch_lock(True))
            for p in patches:
                stack.enter_context(p)
            with (
                patch.object(
                    sentiment_service.post_repository,
                    "upsert_sentiments",
                    AsyncMock(),
                ) as mock_upsert,
                patch.object(
                    sentiment_service.post_repository, "mark_judged", AsyncMock()
                ) as mock_mark,
            ):
                result = await judge_pending(session)

        assert result["judged"] == 1
        rows = mock_upsert.await_args.args[1]
        assert [row["post_id"] for row in rows] == [1]
        assert mock_mark.await_args.args[1] == [1]

    async def test_non_basic_stock_target_filtered(self) -> None:
        """幻觉个股标的（不在基本表）剔除，指数类无代码标的保留。"""
        session = MagicMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        posts = [_post(1)]
        output = SocialJudgmentBatch(
            items=[
                _item(
                    1,
                    targets=[
                        SocialTarget(target_type="stock", name="幻觉股", code="999999"),
                        SocialTarget(target_type="index", name="上证指数", code=None),
                    ],
                )
            ]
        )
        patches = _patch_pipeline(posts, output)
        with ExitStack() as stack:
            stack.enter_context(_patch_lock(True))
            for p in patches:
                stack.enter_context(p)
            with patch.object(
                sentiment_service.post_repository,
                "upsert_sentiments",
                AsyncMock(),
            ) as mock_upsert:
                await judge_pending(session)

        rows = mock_upsert.await_args.args[1]
        assert rows[0]["targets"] == [
            {"target_type": "index", "name": "上证指数", "code": None}
        ]

    async def test_llm_failure_raises_not_ready(self) -> None:
        """LLM 失败包装为 NotReady 向上传播（celery 退避重试）。"""
        session = MagicMock()
        patches = _patch_pipeline(
            [_post(1)], ValueError("LLM 输出不符 schema")
        )
        with ExitStack() as stack:
            stack.enter_context(_patch_lock(True))
            for p in patches:
                stack.enter_context(p)
            with pytest.raises(SocialJudgmentNotReadyError):
                await judge_pending(session)


@pytest.mark.unit
class TestPayload:
    def test_transcript_truncated_and_missing_flag(self) -> None:
        long_post = _post(1, transcript="长" * 1000)
        payload = sentiment_service._post_payload(long_post)
        assert len(payload["transcript"]) == sentiment_service._TRANSCRIPT_CHARS
        assert payload["transcript_missing"] is False

        empty_post = _post(2, transcript="")
        payload = sentiment_service._post_payload(empty_post)
        assert payload["transcript_missing"] is True


@pytest.mark.unit
class TestSocialSentimentCollector:
    async def test_run_success_and_skipped(self) -> None:
        from collector.spiders.social_sentiment import SocialSentimentCollector

        collector = SocialSentimentCollector(config={})
        with patch(
            "collector.spiders.social_sentiment.judge_pending",
            AsyncMock(return_value={"judged": 3, "cleaned": 1}),
        ):
            result = await collector.run()
        assert result.status.value == "success"
        assert result.items_stored == 3
        assert result.metadata == {"cleaned": 1}

        with patch(
            "collector.spiders.social_sentiment.judge_pending",
            AsyncMock(return_value={"judged": 0, "cleaned": 0}),
        ):
            result = await collector.run()
        assert result.status.value == "skipped"

    async def test_run_other_failure_is_failed(self) -> None:
        from collector.spiders.social_sentiment import SocialSentimentCollector

        collector = SocialSentimentCollector(config={})
        with patch(
            "collector.spiders.social_sentiment.judge_pending",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            result = await collector.run()
        assert result.status.value == "failed"

    async def test_not_ready_reraises_for_celery_retry(self) -> None:
        from collector.spiders.social_sentiment import SocialSentimentCollector

        collector = SocialSentimentCollector(config={})
        with patch(
            "collector.spiders.social_sentiment.judge_pending",
            AsyncMock(side_effect=SocialJudgmentNotReadyError("LLM 不可用")),
        ):
            with pytest.raises(SocialJudgmentNotReadyError):
                await collector.run()
