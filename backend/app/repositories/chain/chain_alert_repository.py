"""产业链提醒仓储：批量写入（幂等）与按行业查询。"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.models.chain_alert import ChainAlert
from app.schemas.chain import ChainAlertItem


async def insert_alerts(
    session: AsyncSession,
    *,
    industry: str,
    alerts: list[ChainAlertItem],
    signal_date: date,
    version_id: int | None,
) -> int:
    """批量写入提醒行，同 (industry, alert_type, signal_date) 首见即止。

    返回实际插入行数（重复条目被唯一约束 DO NOTHING 吸收，按用户复制的
    多次落库与手动/定时同日双产都由此幂等）。不 commit。
    """
    if not alerts:
        return 0
    stmt = (
        insert(ChainAlert).values(
            [
                {
                    "industry": industry,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "title": alert.title,
                    "description": alert.description,
                    "affected_segments": alert.affected_segments or None,
                    "related_stock_codes": alert.related_stock_codes or None,
                    "signal_date": signal_date,
                    "version_id": version_id,
                }
                for alert in alerts
            ]
        )
        # 重复条目（按用户复制/同日双产）由唯一约束吸收
        .on_conflict_do_nothing(
            index_elements=["industry", "alert_type", "signal_date"]
        )
    )
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


async def list_alerts(
    session: AsyncSession, industry: str, days: int = 30
) -> list[ChainAlert]:
    """查询行业近 N 天提醒：severity 降序 → signal_date 降序 → created_at 降序。"""
    stmt = (
        select(ChainAlert)
        .where(
            ChainAlert.industry == industry,
            ChainAlert.signal_date >= today_cn() - timedelta(days=days),
        )
        .order_by(
            ChainAlert.severity.desc(),
            ChainAlert.signal_date.desc(),
            ChainAlert.created_at.desc(),
        )
    )
    return list((await session.execute(stmt)).scalars().all())
