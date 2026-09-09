"""股池任务声明：涨停/跌停/炸板/龙虎榜。"""

from datetime import date

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
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
        name="dragon-list",
        label="龙虎榜",
        data_type="pool_dragon_tiger_stock",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_dragon_list:EastMoneyDragonListCollector",
        },
        run_params=("start_date", "end_date"),
    ),
)
