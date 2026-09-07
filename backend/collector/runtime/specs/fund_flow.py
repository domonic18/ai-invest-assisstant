"""资金流任务声明：个股资金流与板块资金流。"""

from datetime import date

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="fund-flow",
        label="资金流向",
        data_type="fund_flow",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_fund_flow:EastMoneyFundFlowCollector",
        },
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
)
