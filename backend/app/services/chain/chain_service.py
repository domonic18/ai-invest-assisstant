"""产业链版本管理业务服务：版本列表、详情与对比（chain 子域 facade）。

AI 分析执行与结果持久化见 ``chain_analysis_service``，此处 re-export 保持
``app.services.chain.chain_service.analyze_and_persist`` 等既有调用点不变。
"""

from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.industry_chain import ChainAnalysisVersion
from app.repositories.chain import (
    chain_alert_repository,
)
from app.repositories.chain import (
    industry_chain_repository as repository,
)
from app.schemas.chain import (
    ChainAlertResponse,
    ChainAlertType,
    ChainAnalysisResult,
    ChainCompareCompanyChange,
    ChainCompareMetricChange,
    ChainCompareResult,
    ChainVersionDetail,
    ChainVersionSummary,
)
from app.services.chain.chain_analysis_service import (
    ChainAnalysisFailedError,
    analyze_and_persist,
    persist_analysis_result,
)

__all__ = [
    "ChainAnalysisFailedError",
    "analyze_and_persist",
    "compare_versions",
    "get_latest_detail",
    "get_version_detail",
    "list_alerts",
    "list_industries",
    "list_versions",
    "persist_analysis_result",
]

_COMPARE_METRIC_FIELDS = (
    "avg_gross_margin",
    "revenue_growth",
    "rd_ratio",
    "bargaining_power",
    "localization_rate",
)


def _to_summary(version: ChainAnalysisVersion) -> ChainVersionSummary:
    """ORM 版本行转响应摘要。"""
    return ChainVersionSummary(
        id=version.id,
        industry=version.industry,
        version_no=version.version_number,
        label=version.label,
        status=version.status,
        model=version.model,
        node_count=version.node_count,
        company_count=version.company_count,
        created_by=version.created_by,
        created_at=version.created_at,
    )


async def list_versions(
    session: AsyncSession, industry: str, user_id: int
) -> list[ChainVersionSummary]:
    """列出指定用户、指定行业的全部版本（版本号降序）。"""
    versions = await repository.list_versions(session, industry, user_id)
    return [_to_summary(version) for version in versions]


async def list_industries(session: AsyncSession, user_id: int) -> list[str]:
    """列出该用户已有成功分析版本的所有行业名称（最近更新在前）。"""
    return await repository.list_industries(session, user_id)


async def list_alerts(
    session: AsyncSession, industry: str, days: int = 30
) -> list[ChainAlertResponse]:
    """查询指定行业近 N 天 AI 提醒（severity 降序，行业级全局数据）。"""
    alerts = await chain_alert_repository.list_alerts(session, industry, days)
    return [
        ChainAlertResponse(
            industry=alert.industry,
            alert_type=cast(ChainAlertType, alert.alert_type),
            severity=alert.severity,
            title=alert.title,
            description=alert.description,
            affected_segments=alert.affected_segments or [],
            related_stock_codes=alert.related_stock_codes or [],
            signal_date=alert.signal_date,
            created_at=alert.created_at,
        )
        for alert in alerts
    ]


def _parse_snapshot(version: ChainAnalysisVersion) -> ChainAnalysisResult | None:
    """解析版本快照为分析结果，失败版本返回 None。"""
    if version.status != "success":
        return None
    return ChainAnalysisResult.model_validate(version.snapshot)


async def get_version_detail(
    session: AsyncSession, version_id: int, user_id: int
) -> ChainVersionDetail | None:
    """查询版本详情，result 来自快照。"""
    version = await repository.get_version(session, version_id, user_id)
    if version is None:
        return None
    return ChainVersionDetail(
        version=_to_summary(version),
        result=_parse_snapshot(version),
        error_msg=version.error_message,
    )


async def get_latest_detail(
    session: AsyncSession, industry: str, user_id: int
) -> ChainVersionDetail | None:
    """查询指定用户、指定行业最新成功版本的详情。"""
    version = await repository.get_latest_success_version(session, industry, user_id)
    if version is None:
        return None
    return ChainVersionDetail(
        version=_to_summary(version),
        result=_parse_snapshot(version),
        error_msg=version.error_message,
    )


async def compare_versions(
    session: AsyncSession, base_id: int, target_id: int, user_id: int
) -> ChainCompareResult | None:
    """对比两个分析版本的快照差异。"""
    base = await repository.get_version(session, base_id, user_id)
    target = await repository.get_version(session, target_id, user_id)
    if base is None or target is None:
        return None
    base_result = _parse_snapshot(base)
    target_result = _parse_snapshot(target)
    if base_result is None or target_result is None:
        return None

    base_nodes = {node.name: node for node in base_result.nodes}
    target_nodes = {node.name: node for node in target_result.nodes}

    def _companies(
        nodes: dict[str, Any]
    ) -> dict[str, ChainCompareCompanyChange]:
        return {
            company.code: ChainCompareCompanyChange(
                code=company.code, name=company.name, node_name=node_name
            )
            for node_name, node in nodes.items()
            for company in node.companies
        }

    base_companies = _companies(base_nodes)
    target_companies = _companies(target_nodes)

    metric_changes = []
    for name in base_nodes.keys() & target_nodes.keys():
        for field in _COMPARE_METRIC_FIELDS:
            base_value = getattr(base_nodes[name], field)
            target_value = getattr(target_nodes[name], field)
            if base_value != target_value:
                metric_changes.append(
                    ChainCompareMetricChange(
                        node_name=name,
                        field=field,
                        base_value=base_value,
                        target_value=target_value,
                    )
                )

    return ChainCompareResult(
        base_version=_to_summary(base),
        target_version=_to_summary(target),
        added_nodes=sorted(target_nodes.keys() - base_nodes.keys()),
        removed_nodes=sorted(base_nodes.keys() - target_nodes.keys()),
        added_companies=[
            target_companies[code]
            for code in sorted(target_companies.keys() - base_companies.keys())
        ],
        removed_companies=[
            base_companies[code]
            for code in sorted(base_companies.keys() - target_companies.keys())
        ],
        metric_changes=metric_changes,
    )
