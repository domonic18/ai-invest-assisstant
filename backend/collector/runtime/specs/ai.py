"""internal AI 任务声明：定时复盘/涨停归因/个股分析/链刷新（直调服务层）。"""

from datetime import date

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
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
    TaskSpec(
        name="stock-daily-analysis",
        label="个股每日AI分析",
        data_type="ai_stock_daily_analysis",
        collectors={
            "internal": "collector.spiders.stock_daily_analysis:StockDailyAnalysisCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="chain-refresh",
        label="产业链定时刷新",
        data_type="ai_chain_refresh",
        collectors={
            "internal": "collector.spiders.chain_refresh:ChainRefreshCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
)
