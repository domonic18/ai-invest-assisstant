"""产业链 AI 分析执行与结果持久化（chain 子域）。

版本管理、详情与对比见 ``chain_service``。
"""

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InternalError
from app.models.industry_chain import ChainNode
from app.repositories.chain import industry_chain_repository as repository
from app.repositories.review import ai_analysis_repository
from app.schemas.chain import ChainAnalysisResult, ChainAnalyzeResponse
from app.services.admin.llm_config_service import resolve_default_llm

SKILL_ID = "industry-chain-analysis"


class ChainAnalysisFailedError(InternalError):
    """AI 产业链分析执行失败。"""


async def _insert_ai_result(
    session: AsyncSession,
    *,
    input_hash: str,
    model: str | None,
    structured: dict[str, Any],
    latency_ms: int,
    status: str,
    error_message: str | None = None,
) -> int:
    """写入 ai_analysis_result 原始记录并返回 id。"""
    return await ai_analysis_repository.insert_result(
        session,
        skill_id=SKILL_ID,
        input_hash=input_hash,
        prompt_id=SKILL_ID,
        model=model,
        structured=structured,
        latency_ms=latency_ms,
        status=status,
        error_msg=error_message,
    )


def _to_graph_rows(
    industry: str, version_id: int, result: ChainAnalysisResult
) -> tuple[list[ChainNode], list[dict[str, Any]], list[dict[str, Any]]]:
    """将分析结果转换为节点 ORM 列表与边/映射 dict 列表。"""
    score_by_code = {
        item.code: item.score for item in result.key_companies_summary
    }
    nodes = [
        ChainNode(
            node_name=node.name,
            industry=industry,
            node_type=node.type,
            description=node.description,
            version_id=version_id,
            avg_gross_margin=node.avg_gross_margin,
            revenue_growth=node.revenue_growth,
            research_and_development_ratio=node.rd_ratio,
            bargaining_power=node.bargaining_power,
            localization_rate=node.localization_rate,
            technology_barrier=node.tech_barrier,
            bottleneck_indicators=node.bottleneck_indicators,
            recent_breakthroughs=node.recent_breakthroughs,
        )
        for node in result.nodes
    ]
    edges = [
        {
            "source": edge.source,
            "target": edge.target,
            "relation_type": edge.relation,
            "relation_description": edge.description,
            "strength": edge.strength,
            "criticality": edge.criticality,
        }
        for edge in result.edges
    ]
    mappings = [
        {
            "node_name": node.name,
            "stock_code": company.code,
            "chain_position": node.name,
            "confidence": score_by_code.get(company.code),
        }
        for node in result.nodes
        for company in node.companies
    ]
    return nodes, edges, mappings


async def persist_analysis_result(
    session: AsyncSession,
    industry: str,
    result: ChainAnalysisResult,
    *,
    model: str | None = None,
    user_id: int = 0,
) -> ChainAnalyzeResponse:
    """将已生成的产业链分析结果持久化为新版本。

    Args:
        industry: 行业名称。
        result: 已校验的 ChainAnalysisResult。
        model: 可选的生成模型名称，用于 ai_analysis_result 记录。
        user_id: 触发分析的用户 ID，默认 0（系统/全局）。

    Returns:
        包含 version_id / version_no / status 的响应。
    """
    started = time.perf_counter()
    version_number = await repository.next_version_number(session, industry, user_id)
    input_hash = f"{user_id}:{industry}:v{version_number}"

    latency_ms = int((time.perf_counter() - started) * 1000)
    structured = result.model_dump(mode="json")
    ai_result_id = await _insert_ai_result(
        session,
        input_hash=input_hash,
        model=model,
        structured=structured,
        latency_ms=latency_ms,
        status="success",
    )
    version = await repository.create_version(
        session,
        industry=industry,
        user_id=user_id,
        version_number=version_number,
        status="success",
        snapshot=structured,
        ai_result_id=ai_result_id,
        model=model,
        node_count=len(result.nodes),
        company_count=sum(len(node.companies) for node in result.nodes),
    )
    nodes, edges, mappings = _to_graph_rows(industry, version.id, result)
    await repository.replace_graph(
        session,
        industry=industry,
        user_id=user_id,
        version_id=version.id,
        nodes=nodes,
        edges=edges,
        mappings=mappings,
    )
    await session.commit()

    return ChainAnalyzeResponse(
        version_id=version.id,
        version_no=version_number,
        status="success",
        result=result,
    )


async def analyze_and_persist(
    session: AsyncSession,
    industry: str,
    focus: str | None = None,
    *,
    user_id: int = 0,
) -> ChainAnalyzeResponse:
    """执行 AI 产业链分析并将结果持久化为新版本（旧版 PydanticAI 执行器入口，逐步废弃）。

    Raises:
        ChainAnalysisFailedError: LLM 调用或结果校验失败（失败版本已落库）。
    """
    started = time.perf_counter()
    version_number = await repository.next_version_number(session, industry, user_id)
    input_hash = f"{user_id}:{industry}:v{version_number}"

    # 延迟导入：skills 执行器顶层依赖 agent.runtime/agent.tools，后者又依赖 services
    from app.agent.skills import industry_chain_analysis

    resolved = await resolve_default_llm(session)
    try:
        result = await industry_chain_analysis.run_skill(
            session, {"industry": industry, "focus": focus}
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        ai_result_id = await _insert_ai_result(
            session,
            input_hash=input_hash,
            model=resolved.model_name,
            structured={"error": str(exc)},
            latency_ms=latency_ms,
            status="failed",
            error_message=str(exc),
        )
        await repository.create_version(
            session,
            industry=industry,
            user_id=user_id,
            version_number=version_number,
            status="failed",
            snapshot={"error": str(exc)},
            ai_result_id=ai_result_id,
            model=resolved.model_name,
            error_message=str(exc),
        )
        await session.commit()
        raise ChainAnalysisFailedError(str(exc)) from exc

    return await persist_analysis_result(
        session, industry, result, model=resolved.model_name, user_id=user_id
    )
