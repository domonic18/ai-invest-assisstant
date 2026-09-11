"""异动日表查询与检测字段 upsert 仓储。

事务边界在服务层：本模块只做查询构造与执行，绝不 commit。
upsert 仅覆盖检测产出字段（行情值 / 维度 / 强度），保留归因字段，
使检测重跑不丢已生成的 AI 归因摘要。
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_anomaly import SectorAnomaly, StockAnomaly

_SECTOR_DETECT_FIELDS = (
    "sector_name",
    "change_pct",
    "amount",
    "amount_ratio",
    "up_count",
    "down_count",
    "anomaly_types",
    "strength",
)
_STOCK_DETECT_FIELDS = (
    "stock_name",
    "close",
    "change_pct",
    "turnover_rate",
    "volume_ratio",
    "ma60",
    "is_above_ma60",
    "ma60_breakout",
    "anomaly_types",
    "strength",
)


async def list_sector_anomalies(
    session: AsyncSession,
    trade_date: date,
    sector_type: str | None = None,
) -> list[SectorAnomaly]:
    """指定交易日的板块异动行，强度降序（可按行业/概念过滤）。"""
    conditions = [SectorAnomaly.trade_date == trade_date]
    if sector_type is not None:
        conditions.append(SectorAnomaly.sector_type == sector_type)
    stmt = (
        select(SectorAnomaly)
        .where(*conditions)
        .order_by(SectorAnomaly.strength.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def delete_sector_rows_outside_pool(
    session: AsyncSession, trade_date: date, eligible: set[tuple[str, str]]
) -> int:
    """删除该交易日检测池外的板块异动行（池收敛后同日重跑的残留清理）。

    只按 (sector_type, sector_code) 池内资格判断，不动池内行的检测/归因字段。
    """
    existing = (
        (await session.execute(select(SectorAnomaly).where(SectorAnomaly.trade_date == trade_date)))
        .scalars()
        .all()
    )
    stale = [
        row for row in existing if (row.sector_type, row.sector_code) not in eligible
    ]
    for row in stale:
        await session.delete(row)
    return len(stale)


async def latest_sector_trade_date(session: AsyncSession) -> date | None:
    """最新有检测数据的交易日。"""
    stmt = select(func.max(SectorAnomaly.trade_date))
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_sector_rows(
    session: AsyncSession, trade_date: date, rows: list[dict]
) -> list[SectorAnomaly]:
    """按 (trade_date, sector_type, sector_code) 覆盖检测字段，新行 insert。"""
    existing = {
        (row.sector_type, row.sector_code): row
        for row in (
            await session.execute(
                select(SectorAnomaly).where(SectorAnomaly.trade_date == trade_date)
            )
        ).scalars()
    }
    result: list[SectorAnomaly] = []
    for values in rows:
        key = (values["sector_type"], values["sector_code"])
        row = existing.get(key)
        if row is None:
            row = SectorAnomaly(trade_date=trade_date, **values)
            session.add(row)
        else:
            for field in _SECTOR_DETECT_FIELDS:
                setattr(row, field, values[field])
        result.append(row)
    return result


async def latest_stock_trade_date(session: AsyncSession) -> date | None:
    """最新有检测数据的交易日。"""
    stmt = select(func.max(StockAnomaly.trade_date))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_stock_anomalies(
    session: AsyncSession, trade_date: date
) -> list[StockAnomaly]:
    """指定交易日的个股异动行，强度降序。"""
    stmt = (
        select(StockAnomaly)
        .where(StockAnomaly.trade_date == trade_date)
        .order_by(StockAnomaly.strength.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def upsert_stock_rows(
    session: AsyncSession, trade_date: date, rows: list[dict]
) -> list[StockAnomaly]:
    """按 (trade_date, stock_code) 覆盖检测字段，新行 insert。"""
    existing = {
        row.stock_code: row
        for row in (
            await session.execute(
                select(StockAnomaly).where(StockAnomaly.trade_date == trade_date)
            )
        ).scalars()
    }
    result: list[StockAnomaly] = []
    for values in rows:
        row = existing.get(values["stock_code"])
        if row is None:
            row = StockAnomaly(trade_date=trade_date, **values)
            session.add(row)
        else:
            for field in _STOCK_DETECT_FIELDS:
                setattr(row, field, values[field])
        result.append(row)
    return result


async def list_sector_anomalies_by_code(
    session: AsyncSession, sector_type: str, sector_code: str, limit: int = 30
) -> list[SectorAnomaly]:
    """单板块最近 N 条异动记录降序（板块详情页异动标注）。"""
    stmt = (
        select(SectorAnomaly)
        .where(
            SectorAnomaly.sector_type == sector_type,
            SectorAnomaly.sector_code == sector_code,
        )
        .order_by(SectorAnomaly.trade_date.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
