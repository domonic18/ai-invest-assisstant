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


async def next_version_number(
    session: AsyncSession, industry: str, user_id: int
) -> int:
    """返回该用户、该行业下一个版本号(从 1 开始)。"""
    stmt = select(func.coalesce(func.max(ChainAnalysisVersion.version_number), 0)).where(
        ChainAnalysisVersion.industry == industry,
        ChainAnalysisVersion.user_id == user_id,
    )
    return int((await session.execute(stmt)).scalar_one()) + 1


async def create_version(
    session: AsyncSession,
    *,
    industry: str,
    user_id: int,
    version_number: int,
    status: str,
    snapshot: dict[str, Any],
    ai_result_id: int | None = None,
    model: str | None = None,
    node_count: int | None = None,
    company_count: int | None = None,
    error_message: str | None = None,
    created_by: str = "manual",
) -> ChainAnalysisVersion:
    """创建版本记录并 flush(不 commit)。"""
    version = ChainAnalysisVersion(
        industry=industry,
        user_id=user_id,
        version_number=version_number,
        status=status,
        snapshot=snapshot,
        ai_result_id=ai_result_id,
        model=model,
        node_count=node_count,
        company_count=company_count,
        error_message=error_message,
        created_by=created_by,
    )
    session.add(version)
    await session.flush()
    return version


async def list_industries(session: AsyncSession, user_id: int) -> list[str]:
    """列出该用户已存在成功分析版本的所有行业名称（按最近创建时间倒序）。"""
    stmt = (
        select(ChainAnalysisVersion.industry)
        .where(
            ChainAnalysisVersion.user_id == user_id,
            ChainAnalysisVersion.status == "success",
        )
        .group_by(ChainAnalysisVersion.industry)
        .order_by(func.max(ChainAnalysisVersion.created_at).desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_versions(
    session: AsyncSession, industry: str, user_id: int
) -> list[ChainAnalysisVersion]:
    """按版本号降序列出该用户、该行业全部版本。"""
    stmt = (
        select(ChainAnalysisVersion)
        .where(
            ChainAnalysisVersion.industry == industry,
            ChainAnalysisVersion.user_id == user_id,
        )
        .order_by(ChainAnalysisVersion.version_number.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_version(
    session: AsyncSession, version_id: int, user_id: int
) -> ChainAnalysisVersion | None:
    """按 id 查询版本,并校验归属用户。"""
    stmt = select(ChainAnalysisVersion).where(
        ChainAnalysisVersion.id == version_id,
        ChainAnalysisVersion.user_id == user_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_latest_success_version(
    session: AsyncSession, industry: str, user_id: int
) -> ChainAnalysisVersion | None:
    """查询该用户、该行业最新一个成功版本。"""
    stmt = (
        select(ChainAnalysisVersion)
        .where(
            ChainAnalysisVersion.industry == industry,
            ChainAnalysisVersion.user_id == user_id,
            ChainAnalysisVersion.status == "success",
        )
        .order_by(ChainAnalysisVersion.version_number.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def replace_graph(
    session: AsyncSession,
    *,
    industry: str,
    user_id: int,
    version_id: int,
    nodes: list[ChainNode],
    edges: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
) -> None:
    """整体替换该用户、该行业的图谱关系行(节点删除后级联清理旧边与映射)。

    Args:
        nodes: 未持久化的 ChainNode 列表(version_id 已赋值)。
        edges: 以节点名引用两端的边 dict,键为 source/target/relation_type/
            relation_description/strength/criticality,端点不在 nodes 中的边被丢弃。
        mappings: 公司映射 dict,键为 node_name/stock_code/chain_position/
            revenue_ratio/confidence。
    """
    old_version_ids = (
        select(ChainAnalysisVersion.id)
        .where(
            ChainAnalysisVersion.industry == industry,
            ChainAnalysisVersion.user_id == user_id,
        )
        .scalar_subquery()
    )
    await session.execute(
        delete(ChainNode).where(
            ChainNode.industry == industry,
            ChainNode.version_id.in_(old_version_ids),
        )
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
                relation_description=edge.get("relation_description"),
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
    """查询指定版本的全部节点(含指标列)。"""
    stmt = (
        select(ChainNode)
        .where(ChainNode.version_id == version_id)
        .order_by(ChainNode.id)
    )
    return list((await session.execute(stmt)).scalars().all())
