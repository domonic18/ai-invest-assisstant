"""Collector task routing and CLI entry points."""

import argparse
import asyncio
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine

from collector.base import BaseCollector, CollectResult, CollectStatus
from collector.resolver import resolve_channel_for_task
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
                INSERT INTO collector_log (task_name, source, status, started_at, finished_at, records_count, error_msg, metadata)
                VALUES (:task_name, :source, :status, :started_at, :finished_at, :records_count, :error_msg, :metadata)
                """
            ),
            {
                "task_name": f"{result.source}:{result.data_type}",
                "source": result.source,
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


def _skipped_result(task_name: str, source: str, data_type: str) -> CollectResult:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return CollectResult(
        source=source,
        data_type=data_type,
        status=CollectStatus.SKIPPED,
        items_collected=0,
        items_stored=0,
        errors=["没有启用任何可用的采集渠道"],
        started_at=now,
        finished_at=now,
    )


async def _resolve_task_channel(
    task_name: str,
    preferred_source: str | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Resolve a channel configuration for ``task_name``.

    Returns ``(source, channel_config)`` or ``None`` if no enabled channel supports
    the task.
    """
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        channel = await resolve_channel_for_task(session, task_name, preferred_source)
        if channel is None:
            return None
        config: dict[str, Any] = {
            "base_url": channel.base_url,
            "api_key": channel.api_key,
        }
        config.update(channel.extra)
        return channel.source, config


async def collect_kline(
    period: str = "daily",
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """K 线采集任务入口。"""
    resolved = await _resolve_task_channel("kline", preferred_source)
    if resolved is None:
        return _skipped_result("kline", "unknown", f"kline_{period}")

    source, channel_config = resolved
    config: dict[str, Any] = {
        "source": source,
        "data_type": f"kline_{period}",
        "period": period,
        **channel_config,
    }

    if source == "sina":
        from collector.spiders.sina_kline import SinaKlineCollector

        collector: BaseCollector = SinaKlineCollector(config)
    else:
        from collector.spiders.ths_kline import ThsKlineCollector

        collector = ThsKlineCollector(config)

    return await collector.run(symbols=symbols)


async def collect_auction(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """集合竞价采集任务入口。"""
    resolved = await _resolve_task_channel("auction", preferred_source)
    if resolved is None:
        return _skipped_result("auction", "unknown", "auction")

    source, channel_config = resolved
    config: dict[str, Any] = {
        "source": source,
        "data_type": "auction",
        **channel_config,
    }

    if source == "sina":
        from collector.spiders.sina_auction import SinaAuctionCollector

        collector: BaseCollector = SinaAuctionCollector(config)
    else:
        from collector.spiders.ths_auction import ThsAuctionCollector

        collector = ThsAuctionCollector(config)

    return await collector.run(symbols=symbols)


async def collect_fund_flow(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """资金流向采集任务入口。"""
    resolved = await _resolve_task_channel("fund-flow", preferred_source)
    if resolved is None:
        return _skipped_result("fund-flow", "unknown", "fund_flow")

    _source, channel_config = resolved
    config: dict[str, Any] = {
        "source": "eastmoney",
        "data_type": "fund_flow",
        **channel_config,
    }
    from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector

    collector = EastMoneyFundFlowCollector(config)
    return await collector.run(symbols=symbols)


async def collect_news(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """新闻采集任务入口。"""
    resolved = await _resolve_task_channel("news", preferred_source)
    if resolved is None:
        return _skipped_result("news", "unknown", "news")

    _source, channel_config = resolved
    config: dict[str, Any] = {
        "source": "sina",
        "data_type": "news",
        **channel_config,
    }
    from collector.spiders.sina_news import SinaNewsCollector

    collector = SinaNewsCollector(config)
    return await collector.run(symbols=symbols)


async def collect_company_profile(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """公司概况采集任务入口。"""
    resolved = await _resolve_task_channel("company-profile", preferred_source)
    if resolved is None:
        return _skipped_result("company-profile", "unknown", "company_profile")

    source, channel_config = resolved
    config: dict[str, Any] = {
        "source": source,
        "data_type": "company_profile",
        **channel_config,
    }
    from collector.spiders.cninfo_profile import CninfoProfileCollector

    collector: BaseCollector = CninfoProfileCollector(config)
    return await collector.run(symbols=symbols)


async def collect_disclosure(
    symbols: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """公告披露采集任务入口。"""
    resolved = await _resolve_task_channel("disclosure", preferred_source)
    if resolved is None:
        return _skipped_result("disclosure", "unknown", "disclosure")

    source, channel_config = resolved
    config: dict[str, Any] = {
        "source": source,
        "data_type": "disclosure",
        **channel_config,
    }
    from collector.spiders.cninfo_disclosure import CninfoDisclosureCollector

    collector: BaseCollector = CninfoDisclosureCollector(config)
    return await collector.run(
        symbols=symbols, start_date=start_date, end_date=end_date
    )


async def collect_sector_fund_flow(
    sector_type: str = "industry",
    preferred_source: str | None = None,
) -> CollectResult:
    """板块资金流向采集任务入口。"""
    resolved = await _resolve_task_channel("sector-fund-flow", preferred_source)
    if resolved is None:
        return _skipped_result("sector-fund-flow", "unknown", "sector_fund_flow")

    _source, channel_config = resolved
    config: dict[str, Any] = {
        "source": "eastmoney",
        "data_type": "sector_fund_flow",
        "sector_type": sector_type,
        **channel_config,
    }
    from collector.spiders.eastmoney_sector_fund_flow import (
        EastMoneySectorFundFlowCollector,
    )

    collector = EastMoneySectorFundFlowCollector(config)
    return await collector.run(sector_type=sector_type)


async def collect_dragon_list(
    start_date: str | None = None,
    end_date: str | None = None,
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """龙虎榜采集任务入口。"""
    resolved = await _resolve_task_channel("dragon-list", preferred_source)
    if resolved is None:
        return _skipped_result("dragon-list", "unknown", "dragon_list")

    _source, channel_config = resolved
    config: dict[str, Any] = {
        "source": "eastmoney",
        "data_type": "dragon_list",
        **channel_config,
    }
    from collector.spiders.eastmoney_dragon_list import EastMoneyDragonListCollector

    collector = EastMoneyDragonListCollector(config)
    return await collector.run(
        start_date=start_date, end_date=end_date, symbols=symbols
    )


async def collect_research_report(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """个股研报采集任务入口。"""
    resolved = await _resolve_task_channel("research-report", preferred_source)
    if resolved is None:
        return _skipped_result("research-report", "unknown", "research_report")

    _source, channel_config = resolved
    config: dict[str, Any] = {
        "source": "eastmoney",
        "data_type": "research_report",
        **channel_config,
    }
    from collector.spiders.eastmoney_research_report import (
        EastMoneyResearchReportCollector,
    )

    collector = EastMoneyResearchReportCollector(config)
    return await collector.run(symbols=symbols)


async def collect_macro(
    indicators: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """宏观经济指标采集任务入口。"""
    resolved = await _resolve_task_channel("macro", preferred_source)
    if resolved is None:
        return _skipped_result("macro", "unknown", "macro_indicator")

    source, channel_config = resolved
    config: dict[str, Any] = {
        "source": source,
        "data_type": "macro_indicator",
        **channel_config,
    }
    from collector.spiders.sina_macro import SinaMacroCollector

    collector: BaseCollector = SinaMacroCollector(config)
    return await collector.run(indicators=indicators)


TASK_MAP = {
    "kline": collect_kline,
    "auction": collect_auction,
    "fund-flow": collect_fund_flow,
    "news": collect_news,
    "company-profile": collect_company_profile,
    "disclosure": collect_disclosure,
    "sector-fund-flow": collect_sector_fund_flow,
    "dragon-list": collect_dragon_list,
    "research-report": collect_research_report,
    "macro": collect_macro,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Invest Assistant Collector")
    parser.add_argument("task", choices=TASK_MAP.keys(), help="采集任务名称")
    parser.add_argument("--period", default="daily", help="K 线周期")
    parser.add_argument("--preferred-source", default=None, help="优先使用的渠道 source")
    parser.add_argument("--start-date", default=None, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--sector-type", default="industry", help="板块类型")
    parser.add_argument(
        "--indicators",
        default=None,
        help="宏观经济指标，逗号分隔，如 cpi,pmi,gdp",
    )
    args = parser.parse_args()

    async def _run() -> CollectResult:
        if args.task == "kline":
            return await collect_kline(
                period=args.period,
                preferred_source=args.preferred_source,
            )
        if args.task == "auction":
            return await collect_auction(preferred_source=args.preferred_source)
        if args.task == "fund-flow":
            return await collect_fund_flow(preferred_source=args.preferred_source)
        if args.task == "news":
            return await collect_news(preferred_source=args.preferred_source)
        if args.task == "company-profile":
            return await collect_company_profile(preferred_source=args.preferred_source)
        if args.task == "disclosure":
            return await collect_disclosure(
                start_date=args.start_date,
                end_date=args.end_date,
                preferred_source=args.preferred_source,
            )
        if args.task == "sector-fund-flow":
            return await collect_sector_fund_flow(
                sector_type=args.sector_type,
                preferred_source=args.preferred_source,
            )
        if args.task == "dragon-list":
            return await collect_dragon_list(
                start_date=args.start_date,
                end_date=args.end_date,
                preferred_source=args.preferred_source,
            )
        if args.task == "research-report":
            return await collect_research_report(preferred_source=args.preferred_source)
        indicators = args.indicators.split(",") if args.indicators else None
        return await collect_macro(
            indicators=indicators,
            preferred_source=args.preferred_source,
        )

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
