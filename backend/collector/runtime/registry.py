"""任务注册表：TASK_MAP 与各采集任务入口（含多渠道 fallback）。"""

from datetime import date
from typing import Any

import structlog

from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.runtime.resolver import resolve_channels_for_task

logger = structlog.get_logger(__name__)


def _skipped_result(source: str, data_type: str) -> CollectResult:
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


async def _resolve_task_channels(
    task_name: str,
    preferred_source: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Resolve ordered channel candidates for ``task_name``.

    Returns ``[(source, channel_config), ...]`` ordered by admin-configured
    priority (``preferred_source`` first when given). Empty list means no
    enabled channel supports the task.
    """
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        channels = await resolve_channels_for_task(
            session, task_name, preferred_source
        )
        resolved: list[tuple[str, dict[str, Any]]] = []
        for channel in channels:
            config: dict[str, Any] = {
                "base_url": channel.base_url,
                "api_key": channel.api_key,
            }
            config.update(channel.extra)
            resolved.append((channel.source, config))
        return resolved


async def _run_collector_for_task(
    task_name: str,
    data_type: str,
    collector_map: dict[str, type[BaseCollector]],
    preferred_source: str | None,
    symbols: list[str] | None = None,
    extra_config: dict[str, Any] | None = None,
    **run_kwargs: Any,
) -> CollectResult:
    """Resolve channel candidates and run collectors with fallback.

    Candidates are tried in priority order: a collector that finishes with
    ``SUCCESS`` or ``PARTIAL`` wins; ``FAILED``/``SKIPPED`` or a source without
    a matching collector falls through to the next candidate. When all
    candidates fail, the last result is returned with the errors of every
    attempt appended.
    """
    candidates = await _resolve_task_channels(task_name, preferred_source)
    if not candidates:
        return _skipped_result("unknown", data_type)

    attempt_errors: list[str] = []
    last_result: CollectResult | None = None
    for source, channel_config in candidates:
        collector_class = collector_map.get(source)
        if collector_class is None:
            attempt_errors.append(
                f"[{source}] 渠道没有任务 {task_name} 对应的采集器"
            )
            continue

        config: dict[str, Any] = {
            "source": source,
            "data_type": data_type,
            **channel_config,
            **(extra_config or {}),
        }
        collector = collector_class(config)
        result = await collector.run(symbols=symbols, **run_kwargs)

        if result.status in (CollectStatus.SUCCESS, CollectStatus.PARTIAL):
            if last_result is not None or attempt_errors:
                result.errors = attempt_errors + result.errors
            return result

        logger.info(
            "collector_fallback",
            task=task_name,
            from_source=source,
            status=result.status.value,
        )
        attempt_errors.extend(f"[{source}] {error}" for error in result.errors)
        last_result = result

    assert last_result is not None
    last_result.status = CollectStatus.FAILED
    last_result.errors = attempt_errors
    return last_result


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
    from collector.spiders.ths_sector_fund_flow import ThsSectorFundFlowCollector

    return await _run_collector_for_task(
        "sector-fund-flow",
        "sector_fund_flow",
        {
            "eastmoney": EastMoneySectorFundFlowCollector,
            "ths": ThsSectorFundFlowCollector,
        },
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


async def collect_stock_list(
    symbols: list[str] | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """全市场股票列表同步任务入口，回写 stock_basic。"""
    from collector.spiders.sina_stock_list import SinaStockListCollector

    return await _run_collector_for_task(
        "stock-list",
        "stock_list",
        {"sina": SinaStockListCollector},
        preferred_source,
        symbols=symbols,
    )


async def collect_limit_up_pool(
    trade_date: str | None = None,
    preferred_source: str | None = None,
) -> CollectResult:
    """涨停股池采集任务入口，写入 limit_up_pool。"""
    from collector.spiders.eastmoney_limit_up_pool import (
        EastMoneyLimitUpPoolCollector,
    )

    parsed_date = date.fromisoformat(trade_date) if trade_date else None
    return await _run_collector_for_task(
        "limit-up-pool",
        "limit_up_pool",
        {"eastmoney": EastMoneyLimitUpPoolCollector},
        preferred_source,
        trade_date=parsed_date,
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
    "stock-list": collect_stock_list,
    "limit-up-pool": collect_limit_up_pool,
}
