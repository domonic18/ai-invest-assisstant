"""产业链定时刷新服务：按用户复制落新版本（chain 子域）。

刷新范围 = 拥有成功版本的全部 (industry, user_id) 组合——每链 AI 只生成一次，
对拥有该链的用户分别落版本（读路径保持 user 维度隔离，零改动）；新用户手动
分析一次后自动进入刷新范围。
"""

from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills import industry_chain_analysis
from app.core.locking import redis_lock
from app.models.industry_chain import ChainAnalysisVersion
from app.schemas.chain import ChainAnalysisResult
from app.services.admin.llm_config_service import resolve_default_llm
from app.services.chain.chain_analysis_service import persist_analysis_result

logger = structlog.get_logger(__name__)

# 全链分析含 150 家公司上下文，单链耗时分钟级；锁覆盖生成+逐用户落库全程
_LOCK_TTL_SECONDS = 1800


async def list_refresh_targets(
    session: AsyncSession,
) -> list[tuple[str, list[int]]]:
    """列出刷新目标：status=success 的 (industry, user_id 去重列表)，最近更新在前。"""
    stmt = (
        select(
            ChainAnalysisVersion.industry,
            func.array_agg(
                func.distinct(ChainAnalysisVersion.user_id)
            ).label("user_ids"),
        )
        .where(ChainAnalysisVersion.status == "success")
        .group_by(ChainAnalysisVersion.industry)
        .order_by(func.max(ChainAnalysisVersion.created_at).desc())
    )
    rows = (await session.execute(stmt)).all()
    return [(row.industry, sorted(int(uid) for uid in row.user_ids)) for row in rows]


async def refresh_industry(
    session: AsyncSession,
    industry: str,
    user_ids: list[int],
    *,
    signal_date: date | None = None,
) -> int:
    """重新分析单条产业链并为每个用户落新版本，返回版本写入的用户数。

    与手动分析并发时（如 POST /analyze 正在生成同链）非阻塞跳过，避免
    ``next_version_number`` 的 max+1 竞争。失败异常向上抛，由调用方隔离。
    """
    async with redis_lock(
        f"chain-refresh:{industry}", ttl=_LOCK_TTL_SECONDS, blocking=False
    ) as acquired:
        if not acquired:
            logger.info("chain_refresh_skipped_locked", industry=industry)
            return 0

        resolved = await resolve_default_llm(session)
        result: ChainAnalysisResult = await industry_chain_analysis.run_skill(
            session, {"industry": industry, "focus": None}
        )
        persisted = 0
        for user_id in user_ids:
            await persist_analysis_result(
                session,
                industry,
                result,
                model=resolved.model_name,
                user_id=user_id,
                created_by="scheduled",
                signal_date=signal_date,
            )
            persisted += 1
        return persisted
