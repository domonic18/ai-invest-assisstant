"""Collector task routing and CLI entry points."""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
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


def _unsupported_source_result(
    task_name: str,
    source: str,
    data_type: str,
) -> CollectResult:
    """Return a skipped result when a resolved source has no matching collector."""
    now = datetime.now(timezone.utc)
    return CollectResult(
        source=source,
        data_type=data_type,
        status=CollectStatus.SKIPPED,
        items_collected=0,
        items_stored=0,
        errors=[f"渠道 {source} 没有任务 {task_name} 对应的采集器"],
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


async def _run_collector_for_task(
    task_name: str,
    data_type: str,
    collector_map: dict[str, type[BaseCollector]],
    preferred_source: str | None,
    symbols: list[str] | None = None,
    extra_config: dict[str, Any] | None = None,
    **run_kwargs: Any,
) -> CollectResult:
    """Resolve a channel and run the matching collector for ``task_name``.

    The ``collector_map`` maps channel ``source`` values to collector classes. If
    the resolved source is not in the map, a skipped result is returned so the
    channel configuration stays in control of which collectors can be used.
    """
    resolved = await _resolve_task_channel(task_name, preferred_source)
    if resolved is None:
        return _skipped_result(task_name, "unknown", data_type)

    source, channel_config = resolved
    collector_class = collector_map.get(source)
    if collector_class is None:
        return _unsupported_source_result(task_name, source, data_type)

    config: dict[str, Any] = {
        "source": source,
        "data_type": data_type,
        **channel_config,
        **(extra_config or {}),
    }
    collector = collector_class(config)
    return await collector.run(symbols=symbols, **run_kwargs)


async def collect_kline(
    period: str = "daily",
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """K 线采集任务入口。"""
    from collector.spiders.sina_kline import SinaKlineCollector
    from collector.spiders.ths_kline import ThsKlineCollector

    return await _run_collector_for_task(
        "kline",
        f"kline_{period}",
        {"sina": SinaKlineCollector, "ths": ThsKlineCollector},
        preferred_source,
        symbols=symbols,
        extra_config={"period": period},
    )


async def collect_auction(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """集合竞价采集任务入口。"""
    from collector.spiders.sina_auction import SinaAuctionCollector
    from collector.spiders.ths_auction import ThsAuctionCollector

    return await _run_collector_for_task(
        "auction",
        "auction",
        {"sina": SinaAuctionCollector, "ths": ThsAuctionCollector},
        preferred_source,
        symbols=symbols,
    )


async def collect_fund_flow(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """资金流向采集任务入口。"""
    from collector.spiders.eastmoney_fund_flow import EastMoneyFundFlowCollector

    return await _run_collector_for_task(
        "fund-flow",
        "fund_flow",
        {"eastmoney": EastMoneyFundFlowCollector},
        preferred_source,
        symbols=symbols,
    )


async def collect_news(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """新闻采集任务入口。"""
    from collector.spiders.sina_news import SinaNewsCollector

    return await _run_collector_for_task(
        "news",
        "news",
        {"sina": SinaNewsCollector},
        preferred_source,
        symbols=symbols,
    )


async def collect_company_profile(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """公司概况采集任务入口。"""
    from collector.spiders.cninfo_profile import CninfoProfileCollector

    return await _run_collector_for_task(
        "company-profile",
        "company_profile",
        {"cninfo": CninfoProfileCollector},
        preferred_source,
        symbols=symbols,
    )


async def collect_disclosure(
    symbols: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """公告披露采集任务入口。"""
    from collector.spiders.cninfo_disclosure import CninfoDisclosureCollector

    return await _run_collector_for_task(
        "disclosure",
        "disclosure",
        {"cninfo": CninfoDisclosureCollector},
        preferred_source,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
    )


async def collect_sector_fund_flow(
    sector_type: str = "industry",
    preferred_source: str | None = None,
) -> CollectResult:
    """板块资金流向采集任务入口。"""
    from collector.spiders.eastmoney_sector_fund_flow import (
        EastMoneySectorFundFlowCollector,
    )

    return await _run_collector_for_task(
        "sector-fund-flow",
        "sector_fund_flow",
        {"eastmoney": EastMoneySectorFundFlowCollector},
        preferred_source,
        sector_type=sector_type,
    )


async def collect_dragon_list(
    start_date: str | None = None,
    end_date: str | None = None,
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """龙虎榜采集任务入口。"""
    from collector.spiders.eastmoney_dragon_list import EastMoneyDragonListCollector

    return await _run_collector_for_task(
        "dragon-list",
        "dragon_list",
        {"eastmoney": EastMoneyDragonListCollector},
        preferred_source,
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
    )


async def collect_research_report(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """个股研报采集任务入口。"""
    from collector.spiders.eastmoney_research_report import (
        EastMoneyResearchReportCollector,
    )

    return await _run_collector_for_task(
        "research-report",
        "research_report",
        {"eastmoney": EastMoneyResearchReportCollector},
        preferred_source,
        symbols=symbols,
    )


async def collect_financial_report(
    symbols: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    report_types: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """个股财报采集任务入口（结构化数据或 PDF 文件）。"""
    from collector.spiders.cninfo_financial_report import (
        CninfoFinancialReportCollector,
    )
    from collector.spiders.eastmoney_financial_statement import (
        EastmoneyFinancialStatementCollector,
    )

    return await _run_collector_for_task(
        "financial-report",
        "financial_statement",
        {
            "eastmoney": EastmoneyFinancialStatementCollector,
            "cninfo": CninfoFinancialReportCollector,
        },
        preferred_source,
        symbols=symbols,
        extra_config={
            "report_types": report_types,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


async def collect_ipo_info(
    preferred_source: str | None = None,
) -> CollectResult:
    """巨潮资讯 IPO 信息采集任务入口。"""
    from collector.spiders.cninfo_ipo import CninfoIpoCollector

    return await _run_collector_for_task(
        "ipo-info",
        "ipo_info",
        {"cninfo": CninfoIpoCollector},
        preferred_source,
    )


async def collect_fund_holdings(
    report_date: str | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """东方财富个股基金持仓采集任务入口。"""
    from collector.spiders.eastmoney_fund_holdings import (
        EastMoneyFundHoldingsCollector,
    )

    return await _run_collector_for_task(
        "fund-holdings",
        "fund_holdings",
        {"eastmoney": EastMoneyFundHoldingsCollector},
        preferred_source,
        extra_config={"report_date": report_date},
    )


async def collect_macro(
    indicators: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """宏观经济指标采集任务入口。"""
    from collector.spiders.sina_macro import SinaMacroCollector

    return await _run_collector_for_task(
        "macro",
        "macro_indicator",
        {"sina": SinaMacroCollector},
        preferred_source,
        indicators=indicators,
    )


async def collect_quote(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """A 股实时行情采集任务入口。"""
    from collector.spiders.sina_quote import SinaQuoteCollector

    return await _run_collector_for_task(
        "quote",
        "quote",
        {"sina": SinaQuoteCollector},
        preferred_source,
        symbols=symbols,
    )


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
    "financial-report": collect_financial_report,
    "ipo-info": collect_ipo_info,
    "fund-holdings": collect_fund_holdings,
    "macro": collect_macro,
    "quote": collect_quote,
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
        "--report-date",
        default=None,
        help="财报发布日期 (YYYYMMDD)，用于基金持仓任务",
    )
    parser.add_argument(
        "--report-types",
        default=None,
        help="财报类型，逗号分隔，如 年报,半年报,一季报,三季报",
    )
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
        if args.task == "financial-report":
            report_types = args.report_types.split(",") if args.report_types else None
            return await collect_financial_report(
                start_date=args.start_date,
                end_date=args.end_date,
                report_types=report_types,
                preferred_source=args.preferred_source,
            )
        if args.task == "ipo-info":
            return await collect_ipo_info(preferred_source=args.preferred_source)
        if args.task == "fund-holdings":
            return await collect_fund_holdings(
                report_date=args.report_date,
                preferred_source=args.preferred_source,
            )
        if args.task == "quote":
            return await collect_quote(preferred_source=args.preferred_source)
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
