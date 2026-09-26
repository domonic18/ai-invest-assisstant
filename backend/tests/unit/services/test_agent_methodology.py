"""方法论基座装配契约测试（方案 A：KB 直读双层注入——纪律全量 + 总纲 + RRF 检索）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.trading import agent_methodology


def _source(**overrides):
    base = {
        "id": 1,
        "name": "温程《趋势理论》",
        "enabled": True,
        "chapter_tree": {
            "published": [
                {"title": "第1章 趋势", "children": [{"title": "1.1 三元", "children": []}]},
                {"title": "第2章 买卖点", "children": []},
            ]
        },
    }
    base.update(overrides)
    return MagicMock(**base)


@pytest.mark.unit
class TestBuildRetrievalQuery:
    def test_collects_strings_from_nested_input(self) -> None:
        review = {"sections": {"overall": "主线高位分歧", "bias": 3}, "themes": ["固态电池"]}
        attribution = {"groups": [{"theme": "机器人", "reason": "订单催化"}]}
        anomalies = [{"attribution_summary": "尾盘拉升"}]

        query = agent_methodology.build_retrieval_query(review, attribution, anomalies)

        assert "主线高位分歧" in query
        assert "固态电池" in query
        assert "订单催化" in query
        assert "尾盘拉升" in query

    def test_truncates_to_limit(self) -> None:
        query = agent_methodology.build_retrieval_query("甲" * 5000, None, None)
        assert query is not None
        assert len(query) == agent_methodology._QUERY_MAX_CHARS

    def test_empty_inputs_return_none(self) -> None:
        assert agent_methodology.build_retrieval_query(None, None, None) is None
        assert agent_methodology.build_retrieval_query("", "  ", []) is None


@pytest.mark.unit
class TestFlattenOutline:
    def test_flattens_tree_with_indent(self) -> None:
        tree = [{"title": "第1章", "children": [{"title": "1.1 节", "children": []}]}]
        assert agent_methodology._flatten_outline(tree) == "- 第1章\n  - 1.1 节"

    def test_empty_tree_returns_empty_string(self) -> None:
        assert agent_methodology._flatten_outline(None) == ""


@pytest.mark.unit
class TestBuildMethodologyInput:
    @pytest.mark.asyncio
    async def test_none_when_not_configured(self) -> None:
        """methodology_source_id 未配置 → None（计划照常生成，仅无基座）。"""
        assert (
            await agent_methodology.build_methodology_input(
                AsyncMock(), source_id=None, query_text="盘面"
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_none_when_source_missing(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        assert (
            await agent_methodology.build_methodology_input(
                session, source_id=1, query_text="盘面"
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_none_when_source_disabled(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=_source(enabled=False))
        assert (
            await agent_methodology.build_methodology_input(
                session, source_id=1, query_text="盘面"
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_builds_full_input(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=_source())
        executed = MagicMock()
        executed.all.return_value = [
            MagicMock(id=2086, title="选板块", body="板块效应成立才参与")
        ]
        session.execute = AsyncMock(return_value=executed)
        search_resp = MagicMock(
            points=[MagicMock(id=1953, point_type="method", title="M60 定位", body="回踩企稳")]
        )

        with patch(
            "app.services.kb.search_service.search",
            AsyncMock(return_value=search_resp),
        ) as search_mock:
            result = await agent_methodology.build_methodology_input(
                session, source_id=1, query_text="当日盘面"
            )

        assert result is not None
        assert result["source_id"] == 1
        assert result["outline"] == "- 第1章 趋势\n  - 1.1 三元\n- 第2章 买卖点"
        assert result["disciplines"] == [
            {"id": 2086, "title": "选板块", "body": "板块效应成立才参与"}
        ]
        assert result["relevant"] == [
            {"id": 1953, "point_type": "method", "title": "M60 定位", "body": "回踩企稳"}
        ]
        # method/theorem/concept/case 四类各检索一次
        assert search_mock.await_count == 4
        assert search_mock.await_args_list[0].kwargs["point_type"] == "method"
        assert search_mock.await_args_list[3].kwargs["point_type"] == "case"

    @pytest.mark.asyncio
    async def test_relevant_skipped_when_query_empty(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=_source())
        executed = MagicMock()
        executed.all.return_value = []
        session.execute = AsyncMock(return_value=executed)

        with patch(
            "app.services.kb.search_service.search", AsyncMock()
        ) as search_mock:
            result = await agent_methodology.build_methodology_input(
                session, source_id=1, query_text=None
            )

        assert result is not None
        assert result["relevant"] == []
        search_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_relevant_dedupes_across_types_and_caps(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=_source())
        executed = MagicMock()
        executed.all.return_value = []
        session.execute = AsyncMock(return_value=executed)
        # 四类各返回 15 条不重叠命中 → 合并 60 条，截断到上限 40
        responses = [
            MagicMock(
                points=[
                    MagicMock(id=i, point_type="method", title=f"t{i}", body="b")
                    for i in range(base, base + 15)
                ]
            )
            for base in (0, 15, 30, 45)
        ]

        with patch(
            "app.services.kb.search_service.search",
            AsyncMock(side_effect=responses),
        ):
            result = await agent_methodology.build_methodology_input(
                session, source_id=1, query_text="盘面"
            )

        assert result is not None
        assert len(result["relevant"]) == agent_methodology._RELEVANT_TOP_N
        assert {item["id"] for item in result["relevant"]} == set(range(40))
