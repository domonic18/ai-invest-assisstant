"""Unit tests for industry chain analysis service."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.industry_chain import ChainAnalysisVersion
from app.schemas.chain import (
    ChainAnalysisResult,
    ChainCompany,
    ChainEdge,
    ChainNode,
    ChainOpportunity,
    ChainRisk,
    KeyCompanySummary,
)
from app.services import chain_service
from app.services.chain_service import ChainAnalysisFailedError
from app.services.llm_config_service import ResolvedLLMConfig


def _resolved() -> ResolvedLLMConfig:
    return ResolvedLLMConfig(
        config_id=1,
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model_name="gpt-4o",
        extra={},
    )


def _result() -> ChainAnalysisResult:
    return ChainAnalysisResult(
        nodes=[
            ChainNode(
                name="硅材料",
                type="upstream",
                companies=[ChainCompany(code="600703", name="三安光电")],
                avg_gross_margin=25.3,
                revenue_growth=15.2,
                bargaining_power=65.0,
                localization_rate=40.0,
            ),
            ChainNode(
                name="晶圆制造",
                type="midstream",
                companies=[ChainCompany(code="688981", name="中芯国际")],
                avg_gross_margin=30.0,
            ),
        ],
        edges=[
            ChainEdge(source="硅材料", target="晶圆制造", relation="供应", strength=95)
        ],
        summary="summary",
        opportunities=[ChainOpportunity(title="国产替代")],
        risks=[ChainRisk(title="技术封锁")],
        key_companies_summary=[
            KeyCompanySummary(code="688981", name="中芯国际", score=85)
        ],
    )


def _version(
    version_id: int,
    version_no: int,
    status: str = "success",
    snapshot: dict | None = None,
) -> ChainAnalysisVersion:
    return ChainAnalysisVersion(
        id=version_id,
        industry_level_1="半导体",
        version_no=version_no,
        status=status,
        snapshot=snapshot if snapshot is not None else _result().model_dump(mode="json"),
        created_by="manual",
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


@pytest.mark.unit
class TestAnalyzeAndPersist:
    @pytest.mark.asyncio
    async def test_success_persists_version_and_graph(self) -> None:
        version = _version(7, 1)
        with (
            patch.object(
                chain_service.repository,
                "next_version_no",
                new=AsyncMock(return_value=1),
            ),
            patch.object(
                chain_service, "resolve_default_llm", new=AsyncMock(return_value=_resolved())
            ),
            patch.object(
                chain_service.industry_chain_analysis,
                "run_skill",
                new=AsyncMock(return_value=_result()),
            ),
            patch.object(
                chain_service, "_insert_ai_result", new=AsyncMock(return_value=42)
            ) as mock_ai,
            patch.object(
                chain_service.repository,
                "create_version",
                new=AsyncMock(return_value=version),
            ) as mock_create,
            patch.object(
                chain_service.repository,
                "replace_graph",
                new=AsyncMock(),
            ) as mock_replace,
        ):
            session = AsyncMock()
            response = await chain_service.analyze_and_persist(session, "半导体")

        assert response.version_id == 7
        assert response.version_no == 1
        assert response.status == "success"
        assert response.result is not None

        create_kwargs = mock_create.await_args.kwargs
        assert create_kwargs["status"] == "success"
        assert create_kwargs["ai_result_id"] == 42
        assert create_kwargs["node_count"] == 2
        assert create_kwargs["company_count"] == 2
        assert create_kwargs["model"] == "gpt-4o"
        assert create_kwargs["snapshot"]["summary"] == "summary"

        replace_kwargs = mock_replace.await_args.kwargs
        assert replace_kwargs["version_id"] == 7
        assert len(replace_kwargs["nodes"]) == 2
        assert replace_kwargs["nodes"][0].node_name == "硅材料"
        assert replace_kwargs["nodes"][0].localization_rate == Decimal("40.0")
        assert replace_kwargs["edges"] == [
            {
                "source": "硅材料",
                "target": "晶圆制造",
                "relation_type": "供应",
                "relation_desc": "",
                "strength": 95.0,
                "criticality": None,
            }
        ]
        # 中芯国际在 key_companies_summary 中 score=85，写入 confidence
        confidences = {m["stock_code"]: m["confidence"] for m in replace_kwargs["mappings"]}
        assert confidences == {"600703": None, "688981": 85}

        session.commit.assert_awaited_once()
        mock_ai.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failure_persists_failed_version_and_raises(self) -> None:
        with (
            patch.object(
                chain_service.repository,
                "next_version_no",
                new=AsyncMock(return_value=2),
            ),
            patch.object(
                chain_service, "resolve_default_llm", new=AsyncMock(return_value=_resolved())
            ),
            patch.object(
                chain_service.industry_chain_analysis,
                "run_skill",
                new=AsyncMock(side_effect=RuntimeError("llm timeout")),
            ),
            patch.object(
                chain_service, "_insert_ai_result", new=AsyncMock(return_value=43)
            ),
            patch.object(
                chain_service.repository,
                "create_version",
                new=AsyncMock(return_value=_version(8, 2, status="failed")),
            ) as mock_create,
            patch.object(
                chain_service.repository,
                "replace_graph",
                new=AsyncMock(),
            ) as mock_replace,
        ):
            session = AsyncMock()
            with pytest.raises(ChainAnalysisFailedError, match="llm timeout"):
                await chain_service.analyze_and_persist(session, "半导体")

        create_kwargs = mock_create.await_args.kwargs
        assert create_kwargs["status"] == "failed"
        assert create_kwargs["error_msg"] == "llm timeout"
        mock_replace.assert_not_awaited()
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestCompareVersions:
    @pytest.mark.asyncio
    async def test_compare_diffs_nodes_companies_and_metrics(self) -> None:
        base_result = _result()
        target_result = _result().model_copy(deep=True)
        # 目标版本：移除硅材料、新增封装测试、中芯国际毛利率变化
        target_result.nodes = [
            node for node in target_result.nodes if node.name != "硅材料"
        ]
        target_result.nodes.append(
            ChainNode(
                name="封装测试",
                type="downstream",
                companies=[ChainCompany(code="600584", name="长电科技")],
            )
        )
        target_result.nodes[0].avg_gross_margin = 35.0

        versions = {
            1: _version(1, 1, snapshot=base_result.model_dump(mode="json")),
            2: _version(2, 2, snapshot=target_result.model_dump(mode="json")),
        }

        async def _get_version(session, version_id):  # noqa: ANN001, ANN202
            return versions.get(version_id)

        with patch.object(
            chain_service.repository, "get_version", new=_get_version
        ):
            result = await chain_service.compare_versions(AsyncMock(), 1, 2)

        assert result is not None
        assert result.added_nodes == ["封装测试"]
        assert result.removed_nodes == ["硅材料"]
        assert [c.code for c in result.added_companies] == ["600584"]
        assert [c.code for c in result.removed_companies] == ["600703"]
        assert result.metric_changes == [
            chain_service.ChainCompareMetricChange(
                node_name="晶圆制造",
                field="avg_gross_margin",
                base_value=30.0,
                target_value=35.0,
            )
        ]

    @pytest.mark.asyncio
    async def test_compare_returns_none_for_missing_or_failed(self) -> None:
        versions = {1: _version(1, 1, status="failed", snapshot={"error": "x"})}

        async def _get_version(session, version_id):  # noqa: ANN001, ANN202
            return versions.get(version_id)

        with patch.object(
            chain_service.repository, "get_version", new=_get_version
        ):
            assert await chain_service.compare_versions(AsyncMock(), 1, 99) is None
            assert await chain_service.compare_versions(AsyncMock(), 1, 1) is None
