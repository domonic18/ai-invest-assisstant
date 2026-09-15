"""大 V 情绪判断触发式采集器（internal）。

每 10 分钟触发，调用 ``sentiment_service.judge_pending`` 批量判断待判内容；
LLM 不可用抛 ``SocialJudgmentNotReadyError`` 不吞——交由 Celery 任务按
10 分钟退避重试（与收盘批 NotReady 同一退避分支）。空批（无待判内容）→
SKIPPED，属良性终态。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.social.sentiment_service import (
    SocialJudgmentNotReadyError,
    judge_pending,
)
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class SocialSentimentCollector(BaseCollector):
    """大 V 情绪判断生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际判断逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """批量判断待判内容；NotReady 向上传播给 Celery 退避。"""
        started_at = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                result = await judge_pending(session)
        except SocialJudgmentNotReadyError:
            raise
        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        judged = int(result["judged"])
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if judged else CollectStatus.SKIPPED,
            items_collected=judged,
            items_stored=judged,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={"cleaned": int(result["cleaned"])},
        )
