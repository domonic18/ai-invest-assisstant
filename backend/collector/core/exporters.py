"""PostgreSQL 数据导出器。"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PostgresExporter:
    """异步写入 PostgreSQL 的导出器。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_many(
        self,
        table: str,
        items: list[dict[str, Any]],
        conflict_key: str | None = None,
        update_columns: list[str] | None = None,
        update_skip_null: bool = False,
    ) -> int:
        if not items:
            return 0

        columns = sorted({key for item in items for key in item.keys()})
        placeholders = ", ".join(f":{col}" for col in columns)
        column_list = ", ".join(columns)

        sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
        if conflict_key:
            if update_columns:
                if update_skip_null:
                    updates = ", ".join(
                        f"{col}=COALESCE(EXCLUDED.{col}, {table}.{col})"
                        for col in update_columns
                    )
                else:
                    updates = ", ".join(f"{col}=EXCLUDED.{col}" for col in update_columns)
                sql += f" ON CONFLICT ({conflict_key}) DO UPDATE SET {updates}"
            else:
                sql += f" ON CONFLICT ({conflict_key}) DO NOTHING"

        count = 0
        for item in items:
            normalized = {col: item.get(col) for col in columns}
            await self.session.execute(text(sql), normalized)
            count += 1
        await self.session.commit()
        return count
