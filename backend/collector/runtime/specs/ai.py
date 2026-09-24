"""internal AI 任务声明：定时复盘/涨停归因/个股分析/链刷新/资讯分级/故事线/热点主题（直调服务层）。"""

from datetime import date

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="market-daily-review",
        label="每日市场复盘",
        description="定时生成每日市场复盘报告，汇总行情并给出策略观点",
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
        description="定时对涨停股做 AI 归因分析，输出上涨驱动逻辑",
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
        description="定时生成个股每日 AI 分析报告，辅助自选股跟踪",
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
        description="定时刷新产业链图谱数据，保持节点与公司映射最新",
        data_type="ai_chain_refresh",
        collectors={
            "internal": "collector.spiders.chain_refresh:ChainRefreshCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="news-score",
        label="资讯AI重要度分级",
        description="AI 对资讯做重要度分级打分，供电报视图分级过滤",
        data_type="ai_news_score",
        collectors={
            "internal": "collector.spiders.news_ai_score:NewsAiScoreCollector",
        },
    ),
    TaskSpec(
        name="news-storyline",
        label="事件故事线建线续接",
        description="AI 建立与续接事件故事线，追踪新闻事件演进",
        data_type="ai_news_storyline",
        collectors={
            "internal": "collector.spiders.news_storyline:NewsStorylineCollector",
        },
    ),
    TaskSpec(
        name="news-topic",
        label="热点主题聚类",
        description="AI 对资讯做热点主题聚类，生成热点聚合视图",
        data_type="ai_news_topic",
        collectors={
            "internal": "collector.spiders.news_topic:NewsTopicCollector",
        },
        run_params=("session_key",),
        defaults={"session_key": None},
    ),
    TaskSpec(
        name="sector-anomaly",
        label="板块异动检测",
        description="定时检测板块量价异动并 AI 归因，驱动板块异动预警",
        data_type="ai_sector_anomaly",
        collectors={
            "internal": "collector.spiders.sector_anomaly:SectorAnomalyCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
        config_params=(
            "price_move_pct",
            "volume_ratio",
            "sync_ratio",
            "baseline_days",
            "attribution_top_n",
        ),
    ),
    TaskSpec(
        name="stock-anomaly",
        label="个股异动检测",
        description="定时检测个股量价异动并 AI 归因，驱动个股异动预警",
        data_type="ai_stock_anomaly",
        collectors={
            "internal": "collector.spiders.stock_anomaly:StockAnomalyCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
        config_params=(
            "screen_change_pct",
            "screen_turnover_pct",
            "screen_candidate_cap",
            "price_move_pct",
            "volume_ratio",
            "turnover_pct",
            "breakout_volume_ratio",
            "attribution_top_n",
        ),
    ),
)
