"""跟踪指数配置服务：CRUD + 启用校验 + 最新行情联查。"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import GLOBAL_INDEX_CODES, INDEX_CODES
from app.models.tracked_index import TrackedIndexConfig
from app.repositories.admin.tracked_index_repository import TrackedIndexRepository
from app.schemas.tracked_index import (
    TrackedIndexCreate,
    TrackedIndexResponse,
    TrackedIndexUpdate,
)

logger = structlog.get_logger()

_A_SHARE_SOURCE = "sina"
_MARKET_CATEGORIES = ("A股", "全球")


class TrackedIndexService:
    """面向管理后台的跟踪指数配置服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TrackedIndexRepository(session)

    async def list_indexes(self) -> list[TrackedIndexResponse]:
        """列出全部配置，附各指数最新收盘。"""
        rows = await self.repo.list_ordered()
        quotes = await self.repo.latest_quotes(
            a_share_codes=[r.index_code for r in rows if r.market_category == "A股"],
            global_codes=[r.index_code for r in rows if r.market_category == "全球"],
        )
        return [self._to_response(row, quotes.get(row.index_code)) for row in rows]

    async def get_index(self, config_id: int) -> TrackedIndexResponse | None:
        """按 ID 查询单条配置。"""
        row = await self.repo.get(config_id)
        if not row:
            return None
        quotes = await self.repo.latest_quotes([row.index_code], [row.index_code])
        return self._to_response(row, quotes.get(row.index_code))

    async def create_index(self, data: TrackedIndexCreate) -> TrackedIndexResponse:
        """创建配置；启用态必须能对应到已支持的数据源。"""
        if data.market_category not in _MARKET_CATEGORIES:
            raise ValueError("market_category 仅支持 A股/全球")
        if await self.repo.get_by_code(data.index_code):
            raise ValueError(f"指数代码 {data.index_code} 已存在")
        if data.is_enabled:
            self._validate_enable(
                data.index_code, data.market_category, data.data_source
            )
        row = TrackedIndexConfig(
            index_code=data.index_code,
            index_name=data.index_name,
            market_category=data.market_category,
            data_source=data.data_source,
            sort_order=data.sort_order,
            is_enabled=data.is_enabled,
        )
        self.repo.add(row)
        await self.session.commit()
        await self.repo.refresh(row)
        logger.info(
            "tracked_index_created",
            id=row.id,
            index_code=row.index_code,
            is_enabled=row.is_enabled,
        )
        return self._to_response(row)

    async def update_index(
        self, config_id: int, data: TrackedIndexUpdate
    ) -> TrackedIndexResponse | None:
        """更新配置；index_code 不可变（变更走删除重建），启用态需通过校验。"""
        row = await self.repo.get(config_id)
        if not row:
            return None

        if data.index_name is not None:
            row.index_name = data.index_name
        if data.market_category is not None:
            if data.market_category not in _MARKET_CATEGORIES:
                raise ValueError("market_category 仅支持 A股/全球")
            row.market_category = data.market_category
        if data.data_source is not None:
            row.data_source = data.data_source
        if data.sort_order is not None:
            row.sort_order = data.sort_order
        if data.is_enabled is not None:
            row.is_enabled = data.is_enabled

        if row.is_enabled:
            self._validate_enable(row.index_code, row.market_category, row.data_source)

        await self.session.commit()
        await self.repo.refresh(row)
        logger.info("tracked_index_updated", id=row.id, is_enabled=row.is_enabled)
        return self._to_response(row)

    async def toggle_index(self, config_id: int) -> TrackedIndexConfig | None:
        """切换启用状态；启用前校验数据源，停用态允许保留任意代码。"""
        row = await self.repo.get(config_id)
        if not row:
            return None
        if not row.is_enabled:
            self._validate_enable(row.index_code, row.market_category, row.data_source)
        row.is_enabled = not row.is_enabled
        await self.session.commit()
        await self.repo.refresh(row)
        logger.info("tracked_index_toggled", id=row.id, is_enabled=row.is_enabled)
        return row

    async def delete_index(self, config_id: int) -> None:
        """删除配置。"""
        row = await self.repo.get(config_id)
        if not row:
            raise ValueError("跟踪指数配置不存在")
        await self.repo.delete(row)
        await self.session.commit()
        logger.info("tracked_index_deleted", id=config_id, index_code=row.index_code)

    @staticmethod
    def _validate_enable(
        index_code: str, market_category: str, data_source: str
    ) -> None:
        """启用校验：启用态必须能对应到真实数据源，违者 400。"""
        if market_category == "全球":
            meta = GLOBAL_INDEX_CODES.get(index_code)
            supported = meta is not None and meta["data_source"] == data_source
        elif market_category == "A股":
            supported = index_code in INDEX_CODES and data_source == _A_SHARE_SOURCE
        else:
            raise ValueError("market_category 仅支持 A股/全球")
        if not supported:
            raise ValueError("无数据源的指标不允许启用")

    def _to_response(
        self, row: TrackedIndexConfig, quote: dict | None = None
    ) -> TrackedIndexResponse:
        return TrackedIndexResponse(
            id=row.id,
            index_code=row.index_code,
            index_name=row.index_name,
            market_category=row.market_category,
            data_source=row.data_source,
            sort_order=row.sort_order,
            is_enabled=row.is_enabled,
            latest_close=float(quote["close"]) if quote and quote.get("close") is not None else None,
            latest_change_pct=(
                float(quote["change_pct"]) if quote and quote.get("change_pct") is not None else None
            ),
            latest_trade_date=quote.get("trade_date") if quote else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
