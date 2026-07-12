"""Collector task routing and CLI entry points."""

import argparse
import asyncio
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine

from collector.base import CollectResult
from collector.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _save_log(result: CollectResult) -> None:
    """将采集结果写入 PostgreSQL collector_log 表。"""
    engine = create_async_engine(settings.database_url)
    from sqlalchemy import text

    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO collector_log (task_name, status, started_at, finished_at, records_count, error_msg, metadata)
                VALUES (:task_name, :status, :started_at, :finished_at, :records_count, :error_msg, :metadata)
                """
            ),
            {
                "task_name": f"{result.source}:{result.data_type}",
                "status": result.status.value,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "records_count": result.items_stored,
                "error_msg": "\n".join(result.errors) if result.errors else None,
                "metadata": json.dumps(result.metadata or {}),
            },
        )
        await conn.commit()
    await engine.dispose()


async def collect_kline(period: str = "daily", symbols: list[str] | None = None) -> CollectResult:
    """K 线采集任务入口。"""
    from collector.spiders.ths_kline import ThsKlineCollector

    config: dict[str, Any] = {
        "source": "ths",
        "data_type": f"kline_{period}",
        "period": period,
    }
    collector = ThsKlineCollector(config)
    return await collector.run(symbols=symbols)


async def collect_auction() -> CollectResult:
    """集合竞价采集任务入口。"""
    from collector.spiders.ths_auction import ThsAuctionCollector

    config: dict[str, Any] = {"source": "ths", "data_type": "auction"}
    collector = ThsAuctionCollector(config)
    return await collector.run()


async def collect_fund_flow() -> CollectResult:
    """资金流向采集任务入口。"""
    from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector

    config: dict[str, Any] = {"source": "eastmoney", "data_type": "fund_flow"}
    collector = EastMoneyFundFlowCollector(config)
    return await collector.run()


async def collect_news() -> CollectResult:
    """新闻采集任务入口。"""
    from collector.spiders.sina_news import SinaNewsCollector

    config: dict[str, Any] = {"source": "sina", "data_type": "news"}
    collector = SinaNewsCollector(config)
    return await collector.run()


TASK_MAP = {
    "kline": collect_kline,
    "auction": collect_auction,
    "fund-flow": collect_fund_flow,
    "news": collect_news,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Invest Assistant Collector")
    parser.add_argument("task", choices=TASK_MAP.keys(), help="采集任务名称")
    parser.add_argument("--period", default="daily", help="K 线周期")
    args = parser.parse_args()

    async def _run() -> CollectResult:
        if args.task == "kline":
            return await collect_kline(period=args.period)
        if args.task == "auction":
            return await collect_auction()
        if args.task == "fund-flow":
            return await collect_fund_flow()
        return await collect_news()

    result = asyncio.run(_run())
    asyncio.run(_save_log(result))
    logger.info(
        "Task %s finished: status=%s collected=%d stored=%d errors=%d",
        args.task,
        result.status.value,
        result.items_collected,
        result.items_stored,
        len(result.errors),
    )
    if result.status.value == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
