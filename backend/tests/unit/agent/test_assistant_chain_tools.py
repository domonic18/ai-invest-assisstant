"""agent 产业链工具单测（mock service，不触网不连库）。"""


from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools import (
    chain_tools as ct,
)
from app.agent.tools import (
    db_tools,
    persist_chain_analysis,
    query_industry_companies,
)
from app.schemas.chain import ChainAnalyzeResponse


@pytest.mark.unit
class TestIndustryChainTools:
    @pytest.mark.asyncio
    async def test_query_industry_companies_limit_clamped(self) -> None:
        payload = [{"code": "000001", "name": "平安银行"}]
        with patch.object(
            db_tools, "query_industry_companies", AsyncMock(return_value=payload)
        ) as m:
            result = await query_industry_companies.ainvoke(
                {"industry": "银行", "limit": 500}
            )
        assert m.call_args.args[2] == ct.INDUSTRY_COMPANIES_MAX_LIMIT
        assert result == payload

    @pytest.mark.asyncio
    async def test_persist_chain_analysis_emits_event(self) -> None:
        result_payload = {
            "nodes": [
                {
                    "name": "设计",
                    "type": "upstream",
                    "companies": [{"code": "000001", "name": "A"}],
                }
            ],
            "edges": [
                {
                    "source": "设计",
                    "target": "制造",
                    "relation": "供应",
                    "strength": 0.8,
                }
            ],
            "summary": "测试",
        }
        version = ChainAnalyzeResponse(
            version_id=123, version_no=5, status="success"
        )
        with patch(
            "app.services.chain.chain_service.persist_analysis_result",
            AsyncMock(return_value=version),
        ) as m:
            result = await persist_chain_analysis.ainvoke(
                {"industry": "半导体", "result": result_payload},
                {"configurable": {"user_id": 7}},
            )
        m.assert_awaited_once()
        assert m.await_args.kwargs["user_id"] == 7
        assert result["version_id"] == 123
        assert result["version_no"] == 5
        assert result["__event__"]["type"] == "industry_chain.analysis.complete"
