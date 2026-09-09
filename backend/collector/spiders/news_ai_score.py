"""资讯 AI 重要度分级定时采集器。

每 5 分钟触发（news-score 任务），调用 ``news_score_service.score_pending``
对已注册评分源的未分级资讯批量评分写入 ``news_ai_score``。无待评 →
SKIPPED；LLM 失败在服务层按批吞掉记日志（下轮重试），仅基础设施异常
向上抛由 Celery 退避。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.news import news_score_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class NewsAiScoreCollector(BaseCollector):
    """资讯 AI 分级生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """批量评分所有注册源的未分级资讯。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                result = await news_score_service.score_pending(session)
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        scored = int(result["scored"])
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if scored else CollectStatus.SKIPPED,
            items_collected=scored,
            items_stored=scored,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={"by_source": result["by_source"]},
        )
