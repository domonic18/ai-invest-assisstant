"""产业链定时刷新采集器。

每周六 06:00（北京时间）由 scheduler 触发，遍历拥有成功版本的产业链逐条
调用 ``chain_refresh_service`` 重新 AI 分析并按用户落新版本。产业链结构非
交易日敏感，运行日（周六）非交易日属预期，**不做交易日门控**；signal_date
取最近交易日（周五）。

单链失败隔离：回滚污染后继续下一条；全部失败才算整体 FAILED。
"""

from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.chain import chain_refresh_service
from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.core.calendar import latest_trading_day


class ChainRefreshCollector(BaseCollector):
    """产业链定时刷新生成器（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """逐链重新生成或跳过（并发持锁时）。"""
        started_at = datetime.now(timezone.utc)
        signal_date = kwargs.get("trade_date") or latest_trading_day()

        per_industry: dict[str, str] = {}
        try:
            async with AsyncSessionLocal() as session:
                targets = await chain_refresh_service.list_refresh_targets(session)
                if not targets:
                    return CollectResult(
                        source=self.source,
                        data_type=self.data_type,
                        status=CollectStatus.SKIPPED,
                        errors=["没有可刷新的产业链（尚无成功分析版本）"],
                        started_at=started_at,
                        finished_at=datetime.now(timezone.utc),
                    )

                for industry, user_ids in targets:
                    try:
                        persisted = await chain_refresh_service.refresh_industry(
                            session,
                            industry,
                            user_ids,
                            signal_date=signal_date,
                        )
                        per_industry[industry] = (
                            "skipped_locked" if persisted == 0 else f"generated:{persisted}"
                        )
                    except Exception as exc:  # noqa: BLE001
                        # 单链失败隔离：回滚污染后继续下一条
                        await session.rollback()
                        per_industry[industry] = f"failed: {exc}"

        except Exception as exc:  # noqa: BLE001
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.FAILED,
                errors=[str(exc)],
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        generated = sum(1 for v in per_industry.values() if v.startswith("generated"))
        skipped = sum(1 for v in per_industry.values() if v == "skipped_locked")
        failed = sum(1 for v in per_industry.values() if v.startswith("failed"))

        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=CollectStatus.SUCCESS if generated >= 1 else CollectStatus.FAILED,
            items_collected=len(per_industry),
            items_stored=generated,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={
                "signal_date": signal_date.isoformat(),
                "industries": per_industry,
                "generated": generated,
                "skipped_locked": skipped,
                "failed": failed,
            },
        )
