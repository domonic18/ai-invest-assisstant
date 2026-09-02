"""跟踪指数配置仓储。"""

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kline import KlineDaily
from app.models.quote_global_index import GlobalIndexDaily
from app.models.tracked_index import TrackedIndexConfig
from app.repositories.base import BaseRepository


class TrackedIndexRepository(BaseRepository[TrackedIndexConfig]):
    """跟踪指数配置的数据访问。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TrackedIndexConfig)

    async def list_ordered(self) -> list[TrackedIndexConfig]:
        """返回全部配置：A 股在前（UTF-8 序 'A股' < '全球'），组内按 sort_order、id。"""
        stmt = select(TrackedIndexConfig).order_by(
            TrackedIndexConfig.market_category,
            TrackedIndexConfig.sort_order,
            TrackedIndexConfig.id,
        )
        result = await self.execute(stmt)
        return list(result.scalars().all())

    async def get_by_code(self, index_code: str) -> TrackedIndexConfig | None:
        """按指数代码查询（唯一）。"""
        stmt = select(TrackedIndexConfig).where(
            TrackedIndexConfig.index_code == index_code
        )
        result = await self.execute(stmt)
        return cast(TrackedIndexConfig | None, result.scalar_one_or_none())

    async def latest_quotes(
        self, a_share_codes: list[str], global_codes: list[str]
    ) -> dict[str, dict[str, Any]]:
        """联查各指数最新收盘（A 股走个股日 K，全球走全球指标日 K）。

        返回 ``{index_code: {close, change_pct, trade_date}}``，无数据的代码不在
        结果中。
        """
        quotes: dict[str, dict[str, Any]] = {}
        if a_share_codes:
            stmt = (
                select(
                    KlineDaily.stock_code,
                    KlineDaily.close,
                    KlineDaily.change_pct,
                    KlineDaily.trade_date,
                )
                .where(KlineDaily.stock_code.in_(a_share_codes))
                .distinct(KlineDaily.stock_code)
                .order_by(KlineDaily.stock_code, KlineDaily.trade_date.desc())
            )
            quotes.update(await self._collect_quote_rows(stmt))
        if global_codes:
            stmt = (
                select(
                    GlobalIndexDaily.index_code,
                    GlobalIndexDaily.close,
                    GlobalIndexDaily.change_pct,
                    GlobalIndexDaily.trade_date,
                )
                .where(GlobalIndexDaily.index_code.in_(global_codes))
                .distinct(GlobalIndexDaily.index_code)
                .order_by(GlobalIndexDaily.index_code, GlobalIndexDaily.trade_date.desc())
            )
            quotes.update(await self._collect_quote_rows(stmt))
        return quotes

    async def _collect_quote_rows(self, stmt: Any) -> dict[str, dict[str, Any]]:
        result = await self.session.execute(stmt)
        rows = result.all()
        return {
            row[0]: {"close": row[1], "change_pct": row[2], "trade_date": row[3]}
            for row in rows
        }
