"""任务注册表：TaskSpec 声明表 + 通用任务入口（含多渠道 fallback）。

新增采集任务只需在 TASK_SPECS 增加一条声明：

- name: 任务名（TASK_MAP 键，与 collector_task.task_type 对应）
- data_type: 写入 collector_log/渠道解析的数据类型；支持 {param} 占位
  （如 kline 的 "kline_{period}"）
- collectors: source -> "module:Class" 懒加载路径（避免引入 akshare 等重依赖）
- config_params: 透传进采集器 config 的任务参数（含未提供时的 None）
- run_params: 透传进 collector.run(**kwargs) 的任务参数
- defaults: 参数默认值（调用方未提供或显式 None 时生效）
- converters: 参数转换器（值非 None 时应用，如 trade_date -> date）

runner 的任务参数白名单同样从 TASK_SPECS 派生，参数只在声明表维护一处。
"""

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import structlog

from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.runtime.resolver import resolve_channels_for_task

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TaskSpec:
    """一个采集任务的声明式配置。"""

    name: str
    data_type: str
    collectors: dict[str, str]
    config_params: tuple[str, ...] = ()
    run_params: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)
    converters: dict[str, Callable[[Any], Any]] = field(default_factory=dict)

    @property
    def param_keys(self) -> tuple[str, ...]:
        """任务级参数全集（runner 据此从请求参数中挑选 kwargs）。"""
        return self.config_params + self.run_params


TASK_SPECS: dict[str, TaskSpec] = {
    spec.name: spec
    for spec in [
        TaskSpec(
            name="kline",
            data_type="kline_{period}",
            collectors={
                "sina": "collector.spiders.sina_kline:SinaKlineCollector",
                "ths": "collector.spiders.ths_kline:ThsKlineCollector",
            },
            config_params=("period",),
            defaults={"period": "daily"},
        ),
        TaskSpec(
            name="index-kline",
            data_type="index_kline",
            collectors={
                "sina": "collector.spiders.sina_index_kline:SinaIndexKlineCollector",
            },
        ),
        TaskSpec(
            name="etf-kline",
            data_type="etf_kline",
            collectors={
                "sina": "collector.spiders.sina_etf_kline:SinaEtfKlineCollector",
            },
        ),
        TaskSpec(
            name="a50-kline",
            data_type="a50_kline",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_a50_kline:EastmoneyA50KlineCollector",
            },
        ),
        TaskSpec(
            name="auction",
            data_type="auction",
            collectors={
                "sina": "collector.spiders.sina_auction:SinaAuctionCollector",
                "ths": "collector.spiders.ths_auction:ThsAuctionCollector",
            },
        ),
        TaskSpec(
            name="fund-flow",
            data_type="fund_flow",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_fund_flow:EastMoneyFundFlowCollector",
            },
        ),
        TaskSpec(
            name="news",
            data_type="news",
            collectors={"sina": "collector.spiders.sina_news:SinaNewsCollector"},
        ),
        TaskSpec(
            name="company-profile",
            data_type="company_profile",
            collectors={
                "cninfo": "collector.spiders.cninfo_profile:CninfoProfileCollector",
            },
        ),
        TaskSpec(
            name="disclosure",
            data_type="disclosure",
            collectors={
                "cninfo": "collector.spiders.cninfo_disclosure:CninfoDisclosureCollector",
            },
            run_params=("start_date", "end_date"),
        ),
        TaskSpec(
            name="sector-fund-flow",
            data_type="sector_fund_flow",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_sector_fund_flow:EastMoneySectorFundFlowCollector",
                "ths": "collector.spiders.ths_sector_fund_flow:ThsSectorFundFlowCollector",
            },
            run_params=("sector_type", "trade_date"),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="dragon-list",
            data_type="dragon_list",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_dragon_list:EastMoneyDragonListCollector",
            },
            run_params=("start_date", "end_date"),
        ),
        TaskSpec(
            name="research-report",
            data_type="research_report",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_research_report:EastMoneyResearchReportCollector",
            },
        ),
        TaskSpec(
            name="financial-report",
            data_type="financial_statement",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_financial_statement:EastmoneyFinancialStatementCollector",
                "cninfo": "collector.spiders.cninfo_financial_report:CninfoFinancialReportCollector",
            },
            config_params=("report_types", "start_date", "end_date"),
        ),
        TaskSpec(
            name="ipo-info",
            data_type="ipo_info",
            collectors={"cninfo": "collector.spiders.cninfo_ipo:CninfoIpoCollector"},
        ),
        TaskSpec(
            name="fund-holdings",
            data_type="fund_holdings",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_fund_holdings:EastMoneyFundHoldingsCollector",
            },
            config_params=("report_date",),
        ),
        TaskSpec(
            name="macro",
            data_type="macro_indicator",
            collectors={"sina": "collector.spiders.sina_macro:SinaMacroCollector"},
            run_params=("indicators",),
        ),
        TaskSpec(
            name="quote",
            data_type="quote",
            collectors={"sina": "collector.spiders.sina_quote:SinaQuoteCollector"},
        ),
        TaskSpec(
            name="stock-list",
            data_type="stock_list",
            collectors={
                "sina": "collector.spiders.sina_stock_list:SinaStockListCollector",
            },
        ),
        TaskSpec(
            name="limit-up-pool",
            data_type="limit_up_pool",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_limit_up_pool:EastMoneyLimitUpPoolCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="market-breadth",
            data_type="market_breadth",
            collectors={
                "sina": "collector.spiders.sina_market_breadth:SinaMarketBreadthCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="index-spot",
            data_type="index_spot",
            collectors={
                "sina": "collector.spiders.sina_index_spot:SinaIndexSpotCollector",
            },
        ),
        TaskSpec(
            name="index-minute",
            data_type="index_minute",
            collectors={
                "sina": "collector.spiders.sina_index_minute:SinaIndexMinuteCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="index-auction",
            data_type="index_auction",
            collectors={
                "tushare": "collector.spiders.tushare_index_auction:TushareIndexAuctionCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="stock-minute",
            data_type="stock_minute",
            collectors={
                "sina": "collector.spiders.sina_stock_minute:SinaStockMinuteCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="market-amount",
            data_type="market_amount",
            collectors={
                "exchange": "collector.spiders.exchange_market_amount:ExchangeMarketAmountCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="broken-pool",
            data_type="broken_pool",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_broken_pool:EastmoneyBrokenPoolCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="limit-down-pool",
            data_type="limit_down_pool",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_limit_down_pool:EastmoneyLimitDownPoolCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
    ]
}


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


def _load_collectors(spec: TaskSpec) -> dict[str, type[BaseCollector]]:
    """按声明的懒加载路径解析采集器类。"""
    collector_map: dict[str, type[BaseCollector]] = {}
    for source, path in spec.collectors.items():
        module_path, _, class_name = path.partition(":")
        module = importlib.import_module(module_path)
        collector_map[source] = getattr(module, class_name)
    return collector_map


def _make_task_entry(
    spec: TaskSpec,
) -> Callable[..., Awaitable[CollectResult]]:
    """由 TaskSpec 生成任务入口函数（签名兼容原手工入口）。"""

    async def entry(
        symbols: list[str] | None = None,
        preferred_source: str | None = None,
        **params: Any,
    ) -> CollectResult:
        resolved = {
            **spec.defaults,
            **{key: value for key, value in params.items() if value is not None},
        }
        data_type = (
            spec.data_type.format(**resolved)
            if "{" in spec.data_type
            else spec.data_type
        )
        extra_config = {key: resolved.get(key) for key in spec.config_params} or None

        run_kwargs: dict[str, Any] = {}
        for key in spec.run_params:
            value = resolved.get(key)
            converter = spec.converters.get(key)
            if converter is not None and value is not None:
                value = converter(value)
            run_kwargs[key] = value

        return await _run_collector_for_task(
            spec.name,
            data_type,
            _load_collectors(spec),
            preferred_source,
            symbols=symbols,
            extra_config=extra_config,
            **run_kwargs,
        )

    entry.__name__ = f"collect_{spec.name.replace('-', '_')}"
    entry.__doc__ = f"{spec.name} 采集任务入口（由 TaskSpec 生成）。"
    return entry


TASK_MAP: dict[str, Callable[..., Awaitable[CollectResult]]] = {
    name: _make_task_entry(spec) for name, spec in TASK_SPECS.items()
}
