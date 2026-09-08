"""盘中行情与市场统计任务声明：快照/竞价/分钟线/广度/成交额/全球指标/宏观。"""

from datetime import date

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="quote",
        label="行情快照",
        data_type="quote",
        collectors={"sina": "collector.spiders.sina_quote:SinaQuoteCollector"},
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
        name="global-index",
        label="全球指标行情",
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
        name="macro",
        label="宏观经济",
        data_type="macro_indicator",
        collectors={"sina": "collector.spiders.sina_macro:SinaMacroCollector"},
        run_params=("indicators",),
    ),
)
