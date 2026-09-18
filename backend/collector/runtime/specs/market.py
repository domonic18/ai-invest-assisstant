"""盘中行情与市场统计任务声明：快照/竞价/分钟线/广度/成交额/全球指标/宏观。"""

from datetime import date

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="quote",
        label="行情快照",
        description="盘中采集全市场个股行情快照，为异动检测与复盘提供价量数据",
        data_type="quote",
        collectors={"sina": "collector.spiders.sina_quote:SinaQuoteCollector"},
    ),
    TaskSpec(
        name="auction",
        label="集合竞价",
        description="采集个股集合竞价数据（9:15-9:25），供集合竞价页展示",
        data_type="auction",
        collectors={
            "sina": "collector.spiders.sina_auction:SinaAuctionCollector",
            "ths": "collector.spiders.ths_auction:ThsAuctionCollector",
        },
    ),
    TaskSpec(
        name="index-spot",
        label="指数快照",
        description="采集指数实时行情快照，作为指数行情的当日兜底源",
        data_type="index_spot",
        collectors={
            "sina": "collector.spiders.sina_index_spot:SinaIndexSpotCollector",
        },
    ),
    TaskSpec(
        name="index-minute",
        label="指数分钟线",
        description="采集指数分钟线，用于盘中走势与分时分析",
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
        description="采集指数集合竞价撮合数据（tushare），供竞价页指数口径",
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
        description="采集个股分钟线，用于个股盘中走势分析",
        data_type="stock_minute",
        collectors={
            "sina": "collector.spiders.sina_stock_minute:SinaStockMinuteCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="market-breadth",
        label="涨跌统计",
        description="统计全市场涨跌家数与分布，生成市场宽度指标",
        data_type="market_breadth",
        collectors={
            "sina": "collector.spiders.sina_market_breadth:SinaMarketBreadthCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="market-amount",
        label="市场成交额",
        description="采集沪深两市成交额，跟踪市场热度与量能",
        data_type="market_amount",
        collectors={
            "exchange": "collector.spiders.exchange_market_amount:ExchangeMarketAmountCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="sector-quote",
        label="板块行情快照",
        description="采集东财板块行情快照，供板块监测页涨跌排行",
        data_type="sector_quote",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_sector_quote:EastmoneySectorQuoteCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="global-index",
        label="全球指标行情",
        description="采集全球指数与美债/日债收益率等外盘指标，反映外围环境",
        data_type="global_index",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_global_index:EastmoneyGlobalIndexCollector",
            "tushare": "collector.spiders.tushare_us_yield:TushareUsYieldCollector",
            "yahoo": "collector.spiders.yahoo_global_index:YahooGlobalIndexCollector",
            "mof": "collector.spiders.mof_jpy_yield:MofJpyYieldCollector",
        },
        run_params=("history_days",),
    ),
    TaskSpec(
        name="fed-watch",
        label="FedWatch 加息概率",
        description="采集 CME FedWatch 加息概率，跟踪美联储政策预期",
        data_type="fed_watch",
        collectors={
            "cme": "collector.spiders.cme_fed_watch:CmeFedWatchCollector",
        },
    ),
    TaskSpec(
        name="macro",
        label="宏观经济",
        description="采集宏观经济指标（CPI/PMI 等），供宏观指数页展示",
        data_type="macro_indicator",
        collectors={"sina": "collector.spiders.sina_macro:SinaMacroCollector"},
        run_params=("indicators",),
    ),
)
