"""产业链相关助手工具。"""

from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool

from app.agent.tools import db_tools
from app.agent.tools.page_event import page_event
from app.core.database import AsyncSessionLocal
from app.services.common.industry import normalize_industry

INDUSTRY_COMPANIES_MAX_LIMIT = 200


@tool
async def query_industry_companies(
    industry: str, limit: int = 150
) -> list[dict[str, Any]]:
    """按行业名称查询上市公司清单，返回股票代码、名称、二级/三级行业、经营范围。

    Args:
        industry: 行业名称，如 "半导体"。
        limit: 返回公司数上限，默认 150，最大 200。
    """
    limit = max(1, min(limit, INDUSTRY_COMPANIES_MAX_LIMIT))
    async with AsyncSessionLocal() as session:
        return await db_tools.query_industry_companies(session, industry, limit)


@tool
async def persist_chain_analysis(
    industry: str,
    result: dict[str, Any],
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> dict[str, Any]:
    """将产业链分析结果持久化到数据库，生成新版本并在产业链页面展示。

    Args:
        industry: 行业名称。
        result: 符合 ChainAnalysisResult schema 的结构化 JSON 对象。
        config: LangGraph 运行时配置，自动注入当前用户 ID。
    """
    from app.schemas.chain import ChainAnalysisResult
    from app.services.chain import chain_service

    normalized = normalize_industry(industry)
    user_id = int(config.get("configurable", {}).get("user_id", 0))
    async with AsyncSessionLocal() as session:
        parsed = ChainAnalysisResult.model_validate(result)
        response = await chain_service.persist_analysis_result(
            session, normalized, parsed, user_id=user_id
        )
        payload = {
            "industry": normalized,
            "version_id": response.version_id,
            "version_no": response.version_no,
            "status": response.status,
            "__event__": page_event(
                "industry_chain.analysis_complete",
                industry=normalized,
                version_id=response.version_id,
                version_no=response.version_no,
            ),
        }
        return payload
