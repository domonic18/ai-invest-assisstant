"""事件故事线建线/续接定时采集器。

盘中每 30 分钟触发（news-storyline 任务），调用
``storyline_service.build_stories`` 对近 48h 高分未入线电报聚类：
≥5 篇建新线、既有线续接。无建线/续接 → SKIPPED；LLM 失败在服务层
吞掉记日志（下轮重试），仅基础设施异常向上抛由 Celery 退避。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.news import storyline_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class NewsStorylineCollector(BaseCollector):
    """事件故事线生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """本轮建线/续接（created/continued 任一大于 0 即 SUCCESS）。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                result = await storyline_service.build_stories(session)
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        created = int(result["created"])
        continued = int(result["continued"])
        attached = int(result["attached"])
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if (created or continued) else CollectStatus.SKIPPED,
            items_collected=attached,
            items_stored=attached,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "created": created,
                "continued": continued,
                "attached": attached,
            },
        )
