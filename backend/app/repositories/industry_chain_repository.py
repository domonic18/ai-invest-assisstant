"""产业链分析图谱与版本查询仓储。"""

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.industry_chain import (
    ChainAnalysisVersion,
    ChainCompanyMapping,
    ChainEdge,
    ChainNode,
)


async def next_version_no(session: AsyncSession, industry: str) -> int:
    """返回该行业下一个版本号（从 1 开始）。"""
    stmt = select(func.coalesce(func.max(ChainAnalysisVersion.version_no), 0)).where(
        ChainAnalysisVersion.industry_level_1 == industry
    )
    return int((await session.execute(stmt)).scalar_one()) + 1


async def create_version(
    session: AsyncSession,
    *,
    industry: str,
    version_no: int,
    status: str,
    snapshot: dict[str, Any],
    ai_result_id: int | None = None,
    model: str | None = None,
    node_count: int | None = None,
    company_count: int | None = None,
    error_msg: str | None = None,
    created_by: str = "manual",
) -> ChainAnalysisVersion:
    """创建版本记录并 flush（不 commit）。"""
    version = ChainAnalysisVersion(
        industry_level_1=industry,
        version_no=version_no,
        status=status,
        snapshot=snapshot,
        ai_result_id=ai_result_id,
        model=model,
        node_count=node_count,
        company_count=company_count,
        error_msg=error_msg,
        created_by=created_by,
    )
    session.add(version)
    await session.flush()
    return version


async def list_versions(
    session: AsyncSession, industry: str
) -> list[ChainAnalysisVersion]:
    """按版本号降序列出该行业全部版本。"""
    stmt = (
        select(ChainAnalysisVersion)
        .where(ChainAnalysisVersion.industry_level_1 == industry)
        .order_by(ChainAnalysisVersion.version_no.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_version(
    session: AsyncSession, version_id: int
) -> ChainAnalysisVersion | None:
    """按 id 查询版本。"""
    stmt = select(ChainAnalysisVersion).where(ChainAnalysisVersion.id == version_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_latest_success_version(
    session: AsyncSession, industry: str
) -> ChainAnalysisVersion | None:
    """查询该行业最新一个成功版本。"""
    stmt = (
        select(ChainAnalysisVersion)
        .where(
            ChainAnalysisVersion.industry_level_1 == industry,
            ChainAnalysisVersion.status == "success",
        )
        .order_by(ChainAnalysisVersion.version_no.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def replace_graph(
    session: AsyncSession,
    *,
    industry: str,
    version_id: int,
    nodes: list[ChainNode],
    edges: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
) -> None:
    """整体替换该行业的图谱关系行（节点删除后级联清理旧边与映射）。

    Args:
        nodes: 未持久化的 ChainNode 列表（version_id 已赋值）。
        edges: 以节点名引用两端的边 dict，键为 source/target/relation_type/
            relation_desc/strength/criticality，端点不在 nodes 中的边被丢弃。
        mappings: 公司映射 dict，键为 node_name/stock_code/chain_position/
            revenue_ratio/confidence。
    """
    await session.execute(
        delete(ChainNode).where(ChainNode.industry_level_1 == industry)
    )
    session.add_all(nodes)
    await session.flush()

    id_by_name = {node.node_name: node.id for node in nodes}

    edge_objs = []
    for edge in edges:
        source_id = id_by_name.get(edge["source"])
        target_id = id_by_name.get(edge["target"])
        if source_id is None or target_id is None:
            continue
        edge_objs.append(
            ChainEdge(
                source_node_id=source_id,
                target_node_id=target_id,
                relation_type=edge.get("relation_type"),
                relation_desc=edge.get("relation_desc"),
                strength=edge.get("strength"),
                criticality=edge.get("criticality"),
                data_source="agent",
                version_id=version_id,
            )
        )
    session.add_all(edge_objs)

    mapping_objs = []
    for mapping in mappings:
        node_id = id_by_name.get(mapping["node_name"])
        if node_id is None:
            continue
        mapping_objs.append(
            ChainCompanyMapping(
                stock_code=mapping["stock_code"],
                chain_node_id=node_id,
                chain_position=mapping.get("chain_position"),
                revenue_ratio=mapping.get("revenue_ratio"),
                confidence=mapping.get("confidence"),
                version_id=version_id,
            )
        )
    session.add_all(mapping_objs)
    await session.flush()


async def list_graph_nodes(
    session: AsyncSession, version_id: int
) -> list[ChainNode]:
    """查询指定版本的全部节点（含指标列）。"""
    stmt = (
        select(ChainNode)
        .where(ChainNode.version_id == version_id)
        .order_by(ChainNode.id)
    )
    return list((await session.execute(stmt)).scalars().all())
