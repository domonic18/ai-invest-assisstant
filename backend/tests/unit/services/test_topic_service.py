"""热点主题服务单测：session 判定、缓存跳过、热度归一、T-1 标注、幻觉过滤。"""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.news import (
    TopicBatch,
    TopicChainStep,
    TopicDraft,
    TopicVotes,
)
from app.services.news import topic_service

_PUBLISH = datetime(2026, 9, 8, 3, 0, tzinfo=timezone.utc)
_TRADE_DATE = date(2026, 9, 8)


def _cand(msg_id: int, title: str = "标题", content: str = "内容") -> Any:
    tg = MagicMock()
    tg.cls_msg_id = msg_id
    tg.title = title
    tg.content = content
    tg.category = "重点"
    tg.stock_codes = []
    tg.publish_time = _PUBLISH
    return (tg, 85)


def _patch_lock(acquired: bool):
    @asynccontextmanager
    async def fake_lock(*args: Any, **kwargs: Any):
        yield acquired

    return patch(
        "app.services.news.topic_service.redis_lock",
        side_effect=fake_lock,
    )


def _topic(item_ids: list[str], sector_names: list[str] | None = None) -> TopicDraft:
    return TopicDraft(
        title="存储芯片涨价",
        sentiment="利好",
        votes=TopicVotes(bullish=5, bearish=0, neutral=1),
        sector_names=sector_names if sector_names is not None else ["半导体"],
        item_ids=item_ids,
        chain=[
            TopicChainStep(event="海外大厂减产", link="供给收缩", stocks=["688012"])
        ],
    )


def _factor(
    change_pct: float = 5.0, flow: float = 5e8, trade_date: date = date(2026, 9, 7)
) -> dict[str, Any]:
    return {
        "trade_date": trade_date,
        "change_pct": change_pct,
        "main_net_inflow": flow,
    }


def _repo_patches(
    candidates: list[Any],
    *,
    snapshot: Any = None,
    factors: dict[str, dict[str, Any]] | None = None,
    titles: list[str | None] | None = None,
):
    """仓储函数统一打桩（snapshot 为 None 时 get_snapshot 返回 None）。"""
    return (
        patch.object(
            topic_service.topic_repository,
            "list_recent_candidates",
            AsyncMock(return_value=candidates),
        ),
        patch.object(
            topic_service.topic_repository,
            "get_snapshot",
            AsyncMock(return_value=snapshot),
        ),
        patch.object(
            topic_service.topic_repository,
            "sector_factors",
            AsyncMock(return_value=factors or {}),
        ),
        patch.object(
            topic_service.topic_repository,
            "list_recent_titles",
            AsyncMock(return_value=titles if titles is not None else []),
        ),
        patch.object(
            topic_service.topic_repository,
            "upsert_snapshot",
            AsyncMock(),
        ),
    )


def _patch_clock(hour: int = 10):
    now = datetime(2026, 9, 8, hour, 0, tzinfo=timezone.utc)
    return (
        patch(
            "app.services.news.topic_service.now_cn",
            MagicMock(return_value=now),
        ),
        patch(
            "app.services.news.topic_service.today_cn",
            MagicMock(return_value=_TRADE_DATE),
        ),
    )


@pytest.mark.unit
class TestResolveSession:
    def test_explicit_value_passthrough(self) -> None:
        assert topic_service._resolve_session("post") == "post"
        assert topic_service._resolve_session("intraday") == "intraday"

    def test_auto_by_beijing_hour(self) -> None:
        with _patch_clock(hour=10)[0]:
            assert topic_service._resolve_session(None) == "intraday"
        with _patch_clock(hour=16)[0]:
            assert topic_service._resolve_session(None) == "post"


@pytest.mark.unit
class TestBuildTopics:
    async def test_lock_busy_skipped(self) -> None:
        with _patch_lock(False):
            result = await topic_service.build_topics(MagicMock(), session_key="post")
        assert result["skipped"] is True
        assert result["session"] == "post"

    async def test_no_candidates_skipped(self) -> None:
        patches = _repo_patches([])
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            clock = _patch_clock(16)
            with _patch_lock(True), clock[0], clock[1]:
                result = await topic_service.build_topics(MagicMock())
        assert result["skipped"] is True
        assert result["session"] == "post"

    async def test_input_hash_match_skips_llm(self) -> None:
        candidates = [_cand(i) for i in range(1, 7)]
        input_hash = topic_service.topic_repository.compute_input_hash(
            [str(i) for i in range(1, 7)]
        )
        snapshot = MagicMock(input_hash=input_hash)
        patches = _repo_patches(candidates, snapshot=snapshot)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            with (
                _patch_lock(True),
                _patch_clock(16)[1],
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(),
                ) as mock_llm,
            ):
                result = await topic_service.build_topics(MagicMock(), session_key="post")
        assert result["skipped"] is True
        mock_llm.assert_not_awaited()

    async def test_input_hash_mismatch_regenerates(self) -> None:
        candidates = [_cand(i) for i in range(1, 7)]
        snapshot = MagicMock(input_hash="stale-hash")
        output = TopicBatch(topics=[_topic([str(i) for i in range(1, 7)])])
        patches = _repo_patches(candidates, snapshot=snapshot, factors={"半导体": _factor()})
        session = MagicMock()
        session.commit = AsyncMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_upsert:
            with (
                _patch_lock(True),
                _patch_clock(16)[1],
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                result = await topic_service.build_topics(session, session_key="post")
        assert result["skipped"] is False
        assert result["topics"] == 1
        mock_upsert.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_assembles_topic_with_heat_and_t1_marker(self) -> None:
        candidates = [_cand(i) for i in range(1, 7)]
        output = TopicBatch(topics=[_topic([str(i) for i in range(1, 7)])])
        patches = _repo_patches(
            candidates, factors={"半导体": _factor()}, titles=["存储芯片涨价潮"]
        )
        session = MagicMock()
        session.commit = AsyncMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_upsert:
            with (
                _patch_lock(True),
                _patch_clock(16)[1],
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                await topic_service.build_topics(session, session_key="post")

        kwargs = mock_upsert.await_args.kwargs
        assert kwargs["trade_date"] == _TRADE_DATE
        assert kwargs["session_key"] == "post"
        topic = kwargs["topics"][0]
        # 情绪票数透传
        assert topic["votes"] == {"bullish": 5, "bearish": 0, "neutral": 1}
        assert topic["news_count"] == 6
        # 热度 = 0.4×100(资讯量满) + 0.3×50(涨幅5%) + 0.3×50(净流入5亿) = 70.0
        assert topic["heat"] == 70.0
        assert topic["factors"]["sector_change_pct"] == 5.0
        assert topic["factors"]["fund_flow_net"] == 5e8
        # 板块数据口径 T-1（收盘快照）
        assert topic["factors"]["as_of_trade_date"] == "2026-09-07"
        assert topic["sectors"] == [
            {"name": "半导体", "change_pct": 5.0, "fund_flow": 5e8}
        ]
        assert topic["item_ids"] == [str(i) for i in range(1, 7)]
        # 词云真分词：jieba 将「存储芯片」切为整词
        assert kwargs["wordcloud"][0]["word"] == "存储芯片"

    async def test_decimal_sector_factors_converted_to_float(self) -> None:
        """Numeric 列回传 Decimal，payload 必须收敛 float 否则 JSONB 序列化失败。"""
        from decimal import Decimal

        candidates = [_cand(i) for i in range(1, 7)]
        output = TopicBatch(topics=[_topic([str(i) for i in range(1, 7)])])
        patches = _repo_patches(
            candidates,
            factors={
                "半导体": _factor(
                    change_pct=Decimal("5.00"), flow=Decimal("500000000.00")
                )
            },
            titles=[],
        )
        session = MagicMock()
        session.commit = AsyncMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_upsert:
            with (
                _patch_lock(True),
                _patch_clock(16)[1],
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                await topic_service.build_topics(session, session_key="post")

        topic = mock_upsert.await_args.kwargs["topics"][0]
        assert topic["sectors"] == [
            {"name": "半导体", "change_pct": 5.0, "fund_flow": 5e8}
        ]
        assert topic["heat"] == 70.0

    async def test_missing_sector_factor_degrades_to_null(self) -> None:
        candidates = [_cand(i) for i in range(1, 7)]
        output = TopicBatch(
            topics=[_topic([str(i) for i in range(1, 7)], sector_names=["未知板块"])]
        )
        patches = _repo_patches(candidates, factors={})
        session = MagicMock()
        session.commit = AsyncMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_upsert:
            with (
                _patch_lock(True),
                _patch_clock(16)[1],
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                await topic_service.build_topics(session, session_key="post")

        topic = mock_upsert.await_args.kwargs["topics"][0]
        assert topic["sectors"] == [
            {"name": "未知板块", "change_pct": None, "fund_flow": None}
        ]
        assert topic["factors"]["sector_change_pct"] is None
        assert topic["factors"]["fund_flow_net"] is None
        assert topic["factors"]["as_of_trade_date"] is None
        # 无板块数据时热度只剩资讯量分 0.4×100
        assert topic["heat"] == 40.0

    async def test_hallucinated_items_filtered_below_threshold(self) -> None:
        candidates = [_cand(i) for i in range(1, 4)]
        output = TopicBatch(
            topics=[
                # 3 条真实 + 2 条幻觉 → 过滤后 3 篇保留
                _topic(["1", "2", "3", "999", "888"]),
                # 全幻觉 → 剔除
                _topic(["777", "666", "555"]),
            ]
        )
        patches = _repo_patches(candidates, factors={"半导体": _factor()})
        session = MagicMock()
        session.commit = AsyncMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_upsert:
            with (
                _patch_lock(True),
                _patch_clock(16)[1],
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                result = await topic_service.build_topics(session, session_key="post")

        assert result["topics"] == 1
        topics = mock_upsert.await_args.kwargs["topics"]
        assert topics[0]["item_ids"] == ["1", "2", "3"]

    async def test_topics_sorted_by_heat_desc(self) -> None:
        candidates = [_cand(i) for i in range(1, 7)]
        big = _topic([str(i) for i in range(1, 7)], sector_names=["半导体"])
        small = _topic(["1", "2", "3"], sector_names=["银行"])
        output = TopicBatch(topics=[small, big])
        factors = {"半导体": _factor(), "银行": _factor()}
        patches = _repo_patches(candidates, factors=factors)
        session = MagicMock()
        session.commit = AsyncMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_upsert:
            with (
                _patch_lock(True),
                _patch_clock(16)[1],
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(return_value=output),
                ),
            ):
                await topic_service.build_topics(session, session_key="post")

        topics = mock_upsert.await_args.kwargs["topics"]
        assert topics[0]["title"] == "存储芯片涨价"
        assert topics[0]["heat"] >= topics[1]["heat"]

    async def test_llm_failure_skipped(self) -> None:
        candidates = [_cand(i) for i in range(1, 7)]
        patches = _repo_patches(candidates)
        session = MagicMock()
        session.commit = AsyncMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_upsert:
            with (
                _patch_lock(True),
                _patch_clock(16)[1],
                patch(
                    "app.agent.runtime.structured.run_structured",
                    AsyncMock(side_effect=ValueError("LLM 输出不符 schema")),
                ),
            ):
                result = await topic_service.build_topics(session, session_key="post")
        assert result["skipped"] is True
        mock_upsert.assert_not_awaited()
        session.commit.assert_not_awaited()


@pytest.mark.unit
class TestWordcloud:
    def test_segmented_counts_and_stopword_filter(self) -> None:
        titles = [
            "存储芯片涨价潮来袭",
            "存储芯片产能扩张",
            "某公司发布公告称数据超预期",
        ]
        cloud = topic_service._build_wordcloud(titles)
        words = {item["word"]: item["count"] for item in cloud}
        # 真分词后领域词计数成立（jieba 将「存储芯片」切为整词）
        assert words.get("存储芯片") == 2
        # 停用词与虚词不进词云
        assert "公司" not in words
        assert "公告" not in words
        assert "数据" not in words
        # 全部词长 ≥2 且按频次降序
        assert all(len(w) >= 2 for w in words)
        counts = [item["count"] for item in cloud]
        assert counts == sorted(counts, reverse=True)

    def test_empty_titles(self) -> None:
        assert topic_service._build_wordcloud([None, ""]) == []


@pytest.mark.unit
class TestHeatScore:
    def test_full_parts_capped_at_100(self) -> None:
        heat = topic_service._heat_score(
            news_count=6,
            max_news_count=6,
            sector_change_pct=50.0,
            fund_flow_net=5e10,
        )
        assert heat == 100.0

    def test_all_null_returns_news_part_only(self) -> None:
        heat = topic_service._heat_score(
            news_count=3, max_news_count=6, sector_change_pct=None, fund_flow_net=None
        )
        assert heat == 20.0


@pytest.mark.unit
class TestGetTopics:
    async def test_snapshot_passthrough(self) -> None:
        snapshot = MagicMock(
            topics=[{"title": "存储芯片涨价", "heat": 70.0}],
            wordcloud=[{"word": "存储", "count": 3}],
            generated_at=datetime(2026, 9, 8, 8, 35, tzinfo=timezone.utc),
        )
        with patch.object(
            topic_service.topic_repository,
            "get_snapshot",
            AsyncMock(return_value=snapshot),
        ), _patch_clock(16)[1]:
            payload = await topic_service.get_topics(MagicMock(), session_key="post")

        assert payload["trade_date"] == "2026-09-08"
        assert payload["session"] == "post"
        assert payload["topics"][0]["title"] == "存储芯片涨价"
        assert payload["wordcloud"] == [{"word": "存储", "count": 3}]
        assert payload["generated_at"] is not None

    async def test_no_snapshot_returns_empty(self) -> None:
        with patch.object(
            topic_service.topic_repository,
            "get_snapshot",
            AsyncMock(return_value=None),
        ), _patch_clock(16)[1]:
            payload = await topic_service.get_topics(MagicMock(), session_key="post")

        assert payload["topics"] == []
        assert payload["wordcloud"] == []
        assert payload["generated_at"] is None

    async def test_chain_stocks_enriched_on_read(self) -> None:
        """传导链标的读取时富化：代码直连/名称解析/无法解析三档。"""
        snapshot = MagicMock(
            topics=[
                {
                    "title": "存储芯片涨价",
                    "heat": 70.0,
                    "chain": [
                        {
                            "event": "海外大厂减产",
                            "link": "供给收缩",
                            "stocks": ["sh688012", "中微公司", "无法解析"],
                        }
                    ],
                }
            ],
            wordcloud=[],
            generated_at=None,
        )
        with (
            patch.object(
                topic_service.topic_repository,
                "get_snapshot",
                AsyncMock(return_value=snapshot),
            ),
            patch.object(
                topic_service.StockRepository,
                "get_codes_by_names",
                AsyncMock(return_value={"中微公司": "688021"}),
            ),
            patch.object(
                topic_service.stock_service,
                "batch_quote_snapshot",
                AsyncMock(
                    return_value={
                        "688012": {"name": "中微半导", "change_pct": 3.2},
                        "688021": {"name": "中微公司", "change_pct": -1.5},
                    }
                ),
            ),
            _patch_clock(16)[1],
        ):
            payload = await topic_service.get_topics(MagicMock(), session_key="post")

        stocks = payload["topics"][0]["chain"][0]["stocks"]
        assert stocks == [
            {"name": "中微半导", "code": "688012", "change_pct": 3.2},
            {"name": "中微公司", "code": "688021", "change_pct": -1.5},
            {"name": "无法解析", "code": None, "change_pct": None},
        ]


@pytest.mark.unit
class TestNewsTopicCollector:
    async def test_run_success_and_skipped(self) -> None:
        from collector.spiders.news_topic import NewsTopicCollector

        collector = NewsTopicCollector(config={})
        done = {
            "session": "post",
            "trade_date": "2026-09-08",
            "topics": 5,
            "skipped": False,
        }
        with patch(
            "app.services.news.topic_service.build_topics",
            AsyncMock(return_value=done),
        ):
            result = await collector.run()
        assert result.status.value == "success"
        assert result.items_stored == 5
        assert result.metadata["session"] == "post"

        skipped = {
            "session": "post",
            "trade_date": "2026-09-08",
            "topics": 0,
            "skipped": True,
        }
        with patch(
            "app.services.news.topic_service.build_topics",
            AsyncMock(return_value=skipped),
        ):
            result = await collector.run()
        assert result.status.value == "skipped"

    async def test_run_failure(self) -> None:
        from collector.spiders.news_topic import NewsTopicCollector

        collector = NewsTopicCollector(config={})
        with patch(
            "app.services.news.topic_service.build_topics",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            result = await collector.run()
        assert result.status.value == "failed"
