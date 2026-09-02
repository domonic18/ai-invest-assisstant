"""任务注册表：TaskSpec 声明表 + 通用任务入口（含多渠道 fallback）。

新增采集任务只需在 TASK_SPECS 增加一条声明：

- name: 任务名（TASK_MAP 键，与 collector_task.task_type 对应）
- label: 中文展示名（任务目录 API / 管理端 UI 的唯一来源，禁止在前端另行硬编码）
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
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

import structlog

from collector.core.base import BaseCollector, CollectResult, CollectStatus
from collector.runtime.resolver import resolve_channels_for_task

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TaskSpec:
    """一个采集任务的声明式配置。"""

    name: str
    label: str
    data_type: str
    collectors: dict[str, str]
    queue: Literal["realtime", "batch", "heavy"] | None = None
    soft_time_limit: int | None = None
    max_retries: int | None = None
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
            label="K 线",
            data_type="kline_{period}",
            # 仅 sina：ths_kline 实际走东财 push2his /kline/get（已被 WAF
            # 路径级封死），保留只会让 fallback 每次多一次注定失败的尝试。
            collectors={
                "sina": "collector.spiders.sina_kline:SinaKlineCollector",
            },
            config_params=("period",),
            defaults={"period": "daily"},
        ),
        TaskSpec(
            name="index-kline",
            label="指数 K 线",
            data_type="index_kline",
            collectors={
                "sina": "collector.spiders.sina_index_kline:SinaIndexKlineCollector",
            },
        ),
        TaskSpec(
            name="etf-kline",
            label="ETF 日 K",
            data_type="etf_kline",
            collectors={
                "sina": "collector.spiders.sina_etf_kline:SinaEtfKlineCollector",
            },
        ),
        TaskSpec(
            name="a50-kline",
            label="富时 A50 日 K",
            data_type="a50_kline",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_a50_kline:EastmoneyA50KlineCollector",
            },
        ),
        TaskSpec(
            name="global-index",
            label="全球指标行情",
            data_type="global_index",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_global_index:EastmoneyGlobalIndexCollector",
                "tushare": "collector.spiders.tushare_us_yield:TushareUsYieldCollector",
            },
            run_params=("history_days",),
        ),
        TaskSpec(
            name="auction",
            label="集合竞价",
            data_type="auction",
            collectors={
                "sina": "collector.spiders.sina_auction:SinaAuctionCollector",
                "ths": "collector.spiders.ths_auction:ThsAuctionCollector",
            },
        ),
        TaskSpec(
            name="fund-flow",
            label="资金流向",
            data_type="fund_flow",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_fund_flow:EastMoneyFundFlowCollector",
            },
        ),
        TaskSpec(
            name="news",
            label="新闻",
            data_type="news",
            collectors={"sina": "collector.spiders.sina_news:SinaNewsCollector"},
        ),
        TaskSpec(
            name="cls-telegraph-backfill",
            label="财联社电报回补",
            data_type="news_telegraph",
            queue="realtime",
            collectors={
                "cls": "collector.spiders.cls_telegraph:ClsTelegraphCollector",
            },
            run_params=("rn",),
            defaults={"rn": 20},
        ),
        TaskSpec(
            name="company-profile",
            label="公司概况",
            data_type="company_profile",
            collectors={
                "cninfo": "collector.spiders.cninfo_profile:CninfoProfileCollector",
            },
        ),
        TaskSpec(
            name="disclosure",
            label="公告披露",
            data_type="disclosure",
            collectors={
                "cninfo": "collector.spiders.cninfo_disclosure:CninfoDisclosureCollector",
            },
            run_params=("start_date", "end_date"),
        ),
        TaskSpec(
            name="sector-fund-flow",
            label="板块资金流向",
            data_type="capital_fund_flow_sector",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_sector_fund_flow:EastMoneySectorFundFlowCollector",
                "ths": "collector.spiders.ths_sector_fund_flow:ThsSectorFundFlowCollector",
            },
            run_params=("sector_type", "trade_date"),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="dragon-list",
            label="龙虎榜",
            data_type="pool_dragon_tiger_stock",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_dragon_list:EastMoneyDragonListCollector",
            },
            run_params=("start_date", "end_date"),
        ),
        TaskSpec(
            name="research-report",
            label="个股研报",
            data_type="research_report",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_research_report:EastMoneyResearchReportCollector",
            },
            run_params=("start_date", "end_date"),
        ),
        TaskSpec(
            name="concept-constituents",
            label="概念成分股",
            data_type="mapping_stock_concept",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_concept_constituents:EastmoneyConceptConstituentCollector",
            },
        ),
        TaskSpec(
            name="financial-report",
            label="财报",
            data_type="financial_statement",
            collectors={
                "cninfo": "collector.spiders.cninfo_financial_report:CninfoFinancialReportCollector",
            },
            config_params=("report_types", "start_date", "end_date"),
        ),
        TaskSpec(
            name="ipo-info",
            label="IPO 信息",
            data_type="ipo_info",
            collectors={"cninfo": "collector.spiders.cninfo_ipo:CninfoIpoCollector"},
        ),
        TaskSpec(
            name="fund-holdings",
            label="基金持仓",
            data_type="fund_holding",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_fund_holdings:EastMoneyFundHoldingsCollector",
            },
            config_params=("report_date",),
        ),
        TaskSpec(
            name="macro",
            label="宏观经济",
            data_type="macro_indicator",
            collectors={"sina": "collector.spiders.sina_macro:SinaMacroCollector"},
            run_params=("indicators",),
        ),
        TaskSpec(
            name="quote",
            label="行情快照",
            data_type="quote",
            collectors={"sina": "collector.spiders.sina_quote:SinaQuoteCollector"},
        ),
        TaskSpec(
            name="stock-list",
            label="股票列表",
            data_type="stock_list",
            collectors={
                "sina": "collector.spiders.sina_stock_list:SinaStockListCollector",
            },
            queue="heavy",
            soft_time_limit=1800,
        ),
        TaskSpec(
            name="limit-up-pool",
            label="涨停股池",
            data_type="pool_limit_up_stock",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_limit_up_pool:EastMoneyLimitUpPoolCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="market-breadth",
            label="涨跌统计",
            data_type="market_breadth",
            collectors={
                "sina": "collector.spiders.sina_market_breadth:SinaMarketBreadthCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="index-spot",
            label="指数快照",
            data_type="index_spot",
            collectors={
                "sina": "collector.spiders.sina_index_spot:SinaIndexSpotCollector",
            },
        ),
        TaskSpec(
            name="index-minute",
            label="指数分钟线",
            data_type="index_minute",
            collectors={
                "sina": "collector.spiders.sina_index_minute:SinaIndexMinuteCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="index-auction",
            label="指数集合竞价",
            data_type="quote_auction_index",
            collectors={
                "tushare": "collector.spiders.tushare_index_auction:TushareIndexAuctionCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="stock-minute",
            label="个股分钟线",
            data_type="stock_minute",
            collectors={
                "sina": "collector.spiders.sina_stock_minute:SinaStockMinuteCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="market-amount",
            label="市场成交额",
            data_type="market_amount",
            collectors={
                "exchange": "collector.spiders.exchange_market_amount:ExchangeMarketAmountCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="broken-pool",
            label="炸板统计",
            data_type="broken_pool",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_broken_pool:EastmoneyBrokenPoolCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="limit-down-pool",
            label="跌停股池",
            data_type="limit_down_pool",
            collectors={
                "eastmoney": "collector.spiders.eastmoney_limit_down_pool:EastmoneyLimitDownPoolCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="market-daily-review",
            label="每日市场复盘",
            data_type="ai_market_daily_review",
            collectors={
                "internal": "collector.spiders.market_daily_review:MarketDailyReviewCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
        TaskSpec(
            name="limit-up-ai-review",
            label="涨停AI归因",
            data_type="ai_limit_up_review",
            collectors={
                "internal": "collector.spiders.limit_up_ai_review:LimitUpAiReviewCollector",
            },
            run_params=("trade_date",),
            converters={"trade_date": date.fromisoformat},
        ),
    ]
}

# 默认队列分配。保持此映射数据驱动，新增任务无需改框架代码；
# 也可通过 TaskSpec.queue 覆盖。
_QUEUE_OVERRIDES: dict[str, Literal["realtime", "batch", "heavy"]] = {
    # 概念成分股需对 500+ 概念逐个分页拉取（限流+网络延迟下实测约 22 分钟），
    # 超出 batch 队列 600s 硬超时，归入 heavy。
    "concept-constituents": "heavy",
    "auction": "realtime",
    "global-index": "realtime",
    "index-spot": "realtime",
    "index-minute": "realtime",
    "stock-minute": "realtime",
    "market-breadth": "realtime",
    "news": "realtime",
    "quote": "realtime",
    "company-profile": "heavy",
    "disclosure": "heavy",
    "financial-report": "heavy",
    "ipo-info": "heavy",
    "market-daily-review": "heavy",
    "limit-up-ai-review": "heavy",
    "research-report": "heavy",
}

TASK_SPECS = {
    name: replace(spec, queue=_QUEUE_OVERRIDES.get(name, spec.queue))
    for name, spec in TASK_SPECS.items()
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
    """解析 ``task_name`` 的有序渠道候选列表。

    返回 ``[(source, channel_config), ...]``，按管理端配置的优先级排序
    （指定 ``preferred_source`` 时置首）。返回空列表表示没有已启用的渠道
    支持该任务。
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
    """解析渠道候选并带 fallback 地运行采集器。

    按优先级顺序尝试各候选：以 ``SUCCESS``/``PARTIAL``/``SKIPPED`` 结束的
    采集器胜出；``FAILED`` 或没有对应采集器的 source 则落入下一个候选。
    全部失败时返回最后一个结果，并附上每一次尝试的错误。

    ``SKIPPED`` 是采集器的主动判定（如非交易日、AI 内容已生成），视为终态
    而非渠道故障——否则单渠道任务（如 market-daily-review）的良性跳过会被
    强制改写为 FAILED 且丢失错误上下文。
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

        if result.status != CollectStatus.FAILED:
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
