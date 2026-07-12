"""Collector base classes and result models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


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
