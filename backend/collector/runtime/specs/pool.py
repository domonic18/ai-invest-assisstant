"""股池任务声明：涨停/跌停/炸板/龙虎榜。"""

from datetime import date

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="limit-up-pool",
        label="涨停股池",
        description="采集每日涨停股池及封板数据，供热点与涨停分析",
        data_type="pool_limit_up_stock",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_limit_up_pool:EastMoneyLimitUpPoolCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="limit-down-pool",
        label="跌停股池",
        description="采集每日跌停股池，用于风险提示与情绪判断",
        data_type="limit_down_pool",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_limit_down_pool:EastmoneyLimitDownPoolCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="broken-pool",
        label="炸板统计",
        description="采集炸板（涨停开板）统计，衡量打板情绪强弱",
        data_type="broken_pool",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_broken_pool:EastmoneyBrokenPoolCollector",
        },
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="dragon-list",
        label="龙虎榜",
        description="采集龙虎榜上榜个股与席位数据，用于资金动向分析",
        data_type="pool_dragon_tiger_stock",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_dragon_list:EastMoneyDragonListCollector",
        },
        run_params=("start_date", "end_date"),
    ),
)
