"""产业链分析 skill 后校验契约测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.skills import industry_chain_analysis
from app.schemas.chain import (
    ChainAlertItem,
    ChainAnalysisResult,
    ChainCompany,
    ChainEdge,
    ChainNode,
    KeyCompanySummary,
)


def _node(name: str, codes: list[str]) -> ChainNode:
    return ChainNode(
        name=name,
        type="upstream",
        companies=[ChainCompany(code=code, name=f"公司{code}") for code in codes],
    )


@pytest.mark.unit
class TestValidate:
    @pytest.mark.asyncio
    async def test_caps_nodes_at_40_and_companies_at_5(self) -> None:
        nodes = [_node(f"环节{i}", [f"60{i:04d}"]) for i in range(45)]
        nodes[0].companies.extend(
            ChainCompany(code=f"70000{i}", name=f"额外{i}") for i in range(5)
        )
        valid_codes = {company.code for node in nodes for company in node.companies}
        valid_codes.add("688981")

        scalars = MagicMock()
        scalars.all.return_value = list(valid_codes)
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        session = AsyncMock()
        session.execute.return_value = execute_result

        result = ChainAnalysisResult(
            nodes=nodes,
            edges=[
                ChainEdge(source="环节0", target="环节1", relation="供应", strength=150),
                ChainEdge(source="环节0", target="环节44", relation="供应", strength=50),
            ],
            summary="s",
            key_companies_summary=[
                KeyCompanySummary(code="688981", name="中芯国际"),
                KeyCompanySummary(code="999999", name="幻觉公司"),
            ],
        )

        validated = await industry_chain_analysis._validate(session, result)

        assert len(validated.nodes) == industry_chain_analysis._MAX_NODES == 40
        assert len(validated.nodes[0].companies) == 5
        # 强度截断到 100；指向被截断节点（环节44）的边被剔除
        assert [(e.target, e.strength) for e in validated.edges] == [("环节1", 100.0)]
        # 幻觉代码被剔除，合法代码保留
        assert [item.code for item in validated.key_companies_summary] == ["688981"]

    @pytest.mark.asyncio
    async def test_filters_hallucinated_company_codes(self) -> None:
        scalars = MagicMock()
        scalars.all.return_value = ["600703"]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        session = AsyncMock()
        session.execute.return_value = execute_result

        result = ChainAnalysisResult(
            nodes=[_node("硅材料", ["600703", "999999"])],
            edges=[],
            summary="s",
        )

        validated = await industry_chain_analysis._validate(session, result)

        assert [company.code for company in validated.nodes[0].companies] == ["600703"]

    @pytest.mark.asyncio
    async def test_cleans_alerts(self) -> None:
        scalars = MagicMock()
        scalars.all.return_value = ["600703"]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        session = AsyncMock()
        session.execute.return_value = execute_result

        result = ChainAnalysisResult(
            nodes=[_node("硅材料", ["600703"])],
            edges=[],
            summary="s",
            alerts=[
                ChainAlertItem(
                    alert_type="技术突破",
                    severity=9,
                    title="突破",
                    description="d",
                    affected_segments=["硅材料", "不存在的环节"],
                    related_stock_codes=["600703", "999999"],
                ),
                ChainAlertItem(
                    alert_type="格局变化", severity=1, title="", description="无标题"
                ),
            ],
        )

        validated = await industry_chain_analysis._validate(session, result)

        assert len(validated.alerts) == 1
        alert = validated.alerts[0]
        assert alert.severity == 3
        assert alert.affected_segments == ["硅材料"]
        assert alert.related_stock_codes == ["600703"]

    @pytest.mark.asyncio
    async def test_truncates_alerts_to_max(self) -> None:
        session = AsyncMock()
        session.execute.return_value = MagicMock(
            scalars=MagicMock(all=MagicMock(return_value=[]))
        )
        alerts = [
            ChainAlertItem(alert_type="政策催化", severity=2, title=f"t{i}")
            for i in range(15)
        ]

        validated = await industry_chain_analysis._validate(
            session,
            ChainAnalysisResult(nodes=[], edges=[], summary="s", alerts=alerts),
        )

        assert len(validated.alerts) == industry_chain_analysis._MAX_ALERTS == 10


@pytest.mark.unit
class TestAlertSchemaCoerce:
    def test_old_snapshot_without_alerts_defaults_empty(self) -> None:
        result = ChainAnalysisResult(
            nodes=[_node("硅材料", ["600703"])], edges=[], summary="s"
        )
        assert result.alerts == []

    def test_string_alerts_coerced_with_defaults(self) -> None:
        result = ChainAnalysisResult.model_validate(
            {"nodes": [], "edges": [], "summary": "s", "alerts": ["纯字符串提醒"]}
        )
        assert result.alerts == [
            ChainAlertItem(
                alert_type="格局变化", severity=2, title="纯字符串提醒"
            )
        ]

    def test_invalid_alert_type_rejected(self) -> None:
        with pytest.raises(ValueError):
            ChainAlertItem(alert_type="异动", severity=2, title="t")


@pytest.mark.unit
class TestAnalyzeIndustryChain:
    @pytest.mark.asyncio
    async def test_runs_agent_loop_validates_and_returns(self) -> None:
        """执行器路径：agent 循环输出合法 JSON → 后置校验剔除幻觉代码。"""

        class _FakeAgent:
            async def ainvoke(self, payload: dict) -> dict:
                return {
                    "messages": [
                        SimpleNamespace(
                            content=(
                                '{"nodes": [{"name": "光刻胶", "type": "upstream", '
                                '"description": "d", "companies": ['
                                '{"code": "600703", "name": "A"}, '
                                '{"code": "999999", "name": "幻觉"}]}], '
                                '"edges": [], "summary": "s", '
                                '"key_companies_summary": ['
                                '{"code": "600703", "name": "A"}]}'
                            )
                        )
                    ]
                }

        scalars = MagicMock()
        scalars.all.return_value = ["600703"]
        session = AsyncMock()
        session.execute.return_value = MagicMock(scalars=MagicMock(return_value=scalars))
        cfg = SimpleNamespace(
            provider="openai", model_name="gpt-4o", api_key="k", base_url=None
        )
        with (
            patch(
                "app.agent.skills.industry_chain_analysis.resolve_default_llm",
                AsyncMock(return_value=cfg),
            ),
            patch(
                "app.agent.skills.industry_chain_analysis.build_langchain_model",
                lambda _cfg: object(),
            ),
            patch("deepagents.create_deep_agent", return_value=_FakeAgent()),
        ):
            result = await industry_chain_analysis.analyze_industry_chain(
                session, "半导体"
            )

        assert result.nodes[0].companies[0].code == "600703"
        assert len(result.nodes[0].companies) == 1
        assert result.key_companies_summary[0].code == "600703"
