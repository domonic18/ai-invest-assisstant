"""产业链分析 skill 后校验契约测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.skills import industry_chain_analysis
from app.schemas.chain import (
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
