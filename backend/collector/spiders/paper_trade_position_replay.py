"""模拟盘历史持仓快照重放采集器（internal 渠道，按需手动触发，不设定时）。

只处理交易 Agent 专属账户（``agent_key IS NOT NULL``）：人工测试账户不做 AI
复盘，无需仓位底座。逐账户隔离错误，单账户失败不影响其他账户。
"""

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.paper_trade import PaperTradeAccount
from app.services.trading import position_replay
from collector.core.base import BaseCollector, CollectResult, CollectStatus


class PaperTradePositionReplayCollector(BaseCollector):
    """历史持仓重放（不直接写表，由 service 持久化）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际重放逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        started_at = datetime.now(timezone.utc)
        start_date: date | None = kwargs.get("start_date")
        end_date: date | None = kwargs.get("end_date")

        async with AsyncSessionLocal() as session:
            account_rows = await session.execute(
                select(PaperTradeAccount.id, PaperTradeAccount.agent_key)
                .where(
                    PaperTradeAccount.is_enabled.is_(True),
                    PaperTradeAccount.agent_key.is_not(None),
                )
                .order_by(PaperTradeAccount.id)
            )
            accounts = list(account_rows.all())

        if not accounts:
            return CollectResult(
                source=self.source,
                data_type=self.data_type,
                status=CollectStatus.SKIPPED,
                message="没有启用中的交易 Agent 账户，无需重放",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )

        details: list[dict[str, Any]] = []
        errors: list[str] = []
        rows_written = 0
        for account in accounts:
            try:
                async with AsyncSessionLocal() as session:
                    summary = await position_replay.rebuild_position_snapshots(
                        session,
                        account_id=account.id,
                        start_date=start_date,
                        end_date=end_date,
                    )
            except Exception as exc:  # noqa: BLE001 —— 账户间错误隔离
                errors.append(f"{account.agent_key}: {exc}")
                details.append(
                    {"account_id": account.id, "agent_key": account.agent_key, "error": str(exc)}
                )
                continue
            rows_written += int(summary.get("rows_written") or 0)
            details.append(summary)

        if errors:
            status = CollectStatus.PARTIAL
        else:
            status = CollectStatus.SUCCESS
        return CollectResult(
            source=self.source,
            data_type=self.data_type,
            status=status,
            items_collected=rows_written,
            items_stored=rows_written,
            errors=errors,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            metadata={"accounts": len(accounts), "details": details},
        )
