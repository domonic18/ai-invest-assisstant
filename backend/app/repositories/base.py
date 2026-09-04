"""提供通用异步 CRUD 操作的基础仓储。

仓储层只负责数据访问，不管理事务；
事务边界由调用方（通常是服务层）负责，按需执行 commit/rollback。
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """SQLAlchemy 模型的通用仓储。"""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def get(self, obj_id: int) -> T | None:
        """按主键获取单个对象。"""
        return await self.session.get(self.model, obj_id)

    async def get_all(
        self,
        *,
        order_by: Any | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[T]:
        """获取全部对象，可选排序与分页。"""
        stmt = select(self.model)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """返回对象总数。"""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        return (await self.session.scalar(stmt)) or 0

    def add(self, obj: T) -> None:
        """将对象加入 session。"""
        self.session.add(obj)

    async def delete(self, obj: T) -> None:
        """标记对象待删除。"""
        await self.session.delete(obj)

    async def refresh(self, obj: T) -> None:
        """从数据库刷新对象。"""
        await self.session.refresh(obj)

    async def execute(self, stmt: Any) -> Any:
        """执行原始 SQLAlchemy 语句。"""
        return await self.session.execute(stmt)

    async def scalar(self, stmt: Any) -> Any:
        """执行语句并返回标量结果。"""
        return await self.session.scalar(stmt)
