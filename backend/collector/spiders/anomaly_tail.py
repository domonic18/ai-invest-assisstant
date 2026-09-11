"""异动检测任务的 AI 归因尾部。

检测任务「规则检测 + top-N 归因」串行（docs/arch/08 §5）：检测成功后调用
``anomaly_attribution_service.run_top_n_attribution``；归因失败只记日志，
不改变检测结果（检测数据已落库，归因可由手动路径或次日重跑补齐）。
"""

from datetime import date

import structlog

from app.core.database import AsyncSessionLocal
from app.services.market import anomaly_attribution_service

logger = structlog.get_logger(__name__)


async def run_attribution_tail(domain: str, trade_date: date, top_n: int) -> int:
    """对强度榜 top-N 批量归因并回写，返回实际归因条数（失败返回 0）。"""
    try:
        async with AsyncSessionLocal() as session:
            stats = await anomaly_attribution_service.run_top_n_attribution(
                session, domain, trade_date, top_n=top_n
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "anomaly_attribution_tail_failed",
            domain=domain,
            trade_date=trade_date.isoformat(),
            error=str(exc),
        )
        return 0
    return stats["from_cache"] + stats["generated"]
