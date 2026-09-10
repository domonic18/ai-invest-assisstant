"""后台电报（财联社）查删管理服务。"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.market import telegraph_repository
from app.repositories.market.telegraph_repository import TelegraphRow


class AdminTelegraphService:
    """后台电报查询/删除服务（只读查询 + 删除，无新增编辑）。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_telegraph(
        self,
        q: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TelegraphRow], int]:
        """分页查询电报（publish_time 降序），左联 AI 分级。"""
        return await telegraph_repository.admin_list_telegraph(
            self.session,
            q=q,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )

    async def delete_telegraph(self, telegraph_id: int) -> None:
        """按主键删除单条电报，缺失时抛 NotFoundError。"""
        deleted = await telegraph_repository.delete_telegraph_by_ids(
            self.session, [telegraph_id]
        )
        if deleted == 0:
            raise NotFoundError(f"Telegraph {telegraph_id} not found")
        await self.session.commit()

    async def delete_telegraph_batch(self, ids: list[int]) -> int:
        """批量删除电报，返回删除条数。"""
        deleted = await telegraph_repository.delete_telegraph_by_ids(self.session, ids)
        await self.session.commit()
        return deleted
