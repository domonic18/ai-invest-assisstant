"""Collector 基类与共享数据库引擎。

BaseCollector 定义采集流程模板；PostgresCollector 在其上提供声明式的
pipeline 组装与 PostgreSQL upsert 存储——子类只需声明表配置类属性并实现
collect/transform，新增一个 DB 类采集器通常不超过 30 行。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from collector.core.config import database_url
from collector.core.exporters import PostgresExporter
from collector.core.pipelines import (
    DataPipeline,
    DeduplicateStep,
    NormalizeStep,
    PipelineStep,
    ValidateStep,
)

logger = logging.getLogger(__name__)


class CollectStatus(Enum):
    """采集任务执行状态。"""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CollectResult:
    """单次采集任务结果。"""

    source: str
    data_type: str
    status: CollectStatus
    items_collected: int = 0
    items_stored: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCollector(ABC):
    """所有数据采集器的抽象基类。"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.source = config.get("source", "unknown")
        self.data_type = config.get("data_type", "unknown")

    @abstractmethod
    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """执行数据采集，返回原始数据列表。"""

    @abstractmethod
    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        """将原始数据转换为标准化条目。"""

    @abstractmethod
    async def validate(self, item: dict[str, Any]) -> bool:
        """校验标准化后的单条数据。"""

    async def store(self, items: list[dict[str, Any]]) -> int:
        """批量入库，返回实际入库条数。

        子类可重写此方法来对接具体存储后端。
        """
        return len(items)

    async def run(self, **kwargs: Any) -> CollectResult:
        """执行完整采集流程（模板方法）。"""
        started_at = datetime.utcnow()
        errors: list[str] = []

        try:
            raw_data = await self.collect(**kwargs)
            transformed: list[dict[str, Any]] = []

            for idx, item in enumerate(raw_data):
                try:
                    standardized = await self.transform(item)
                    if await self.validate(standardized):
                        transformed.append(standardized)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"item {idx}: {exc}")
                    logger.warning(
                        "collector_item_failed source=%s data_type=%s index=%d",
                        self.source,
                        self.data_type,
                        idx,
                        exc_info=True,
                    )

            stored_count = await self.store(transformed)
            status = CollectStatus.SUCCESS if not errors else CollectStatus.PARTIAL

            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=status,
                items_collected=len(raw_data),
                items_stored=stored_count,
                errors=errors,
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "collector_run_failed source=%s data_type=%s",
                self.source,
                self.data_type,
            )
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                items_collected=0,
                items_stored=0,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )


_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """进程级共享异步引擎（惰性创建）。"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(database_url)
    return _engine


async def dispose_engine() -> None:
    """释放共享引擎，进程退出前调用。"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


class PostgresCollector(BaseCollector):
    """声明式 PostgreSQL 采集器基类。

    子类通过类属性声明存储与清洗配置，基类自动组装 DataPipeline 并提供
    标准 upsert store：

    - table / conflict_key: upsert 目标表与冲突键（必填）
    - update_columns: 冲突时更新的列；None 表示 DO NOTHING
    - update_skip_null: 更新时跳过 NULL 值（COALESCE 保留原值）
    - normalize / key_fields / required_fields: pipeline 步骤配置

    子类仍可按需重写 store/validate（如多表写入、自定义校验）。
    """

    table: str = ""
    conflict_key: str = ""
    update_skip_null: bool = False
    normalize: bool = True
    update_columns: ClassVar[list[str] | None] = None
    key_fields: ClassVar[list[str] | None] = None
    required_fields: ClassVar[list[str] | None] = None

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        steps: list[PipelineStep] = []
        if self.normalize:
            steps.append(NormalizeStep())
        if self.key_fields:
            steps.append(DeduplicateStep(key_fields=list(self.key_fields)))
        if self.required_fields:
            steps.append(ValidateStep(required_fields=list(self.required_fields)))
        self.pipeline = DataPipeline(steps=steps)

    async def validate(self, item: dict[str, Any]) -> bool:
        """默认按 required_fields 校验必填字段非空。"""
        if not self.required_fields:
            return True
        return all(item.get(field) is not None for field in self.required_fields)

    async def store(self, items: list[dict[str, Any]]) -> int:
        """pipeline 清洗后 upsert 到声明的目标表。"""
        cleaned = await self.pipeline.process(items)
        if not cleaned:
            return 0

        kwargs: dict[str, Any] = {"conflict_key": self.conflict_key}
        if self.update_columns:
            kwargs["update_columns"] = self.update_columns
        if self.update_skip_null:
            kwargs["update_skip_null"] = True

        session_maker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
        async with session_maker() as session:
            exporter = PostgresExporter(session)
            return await exporter.insert_many(self.table, cleaned, **kwargs)
