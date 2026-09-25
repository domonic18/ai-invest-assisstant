"""交易域任务声明：模拟盘盘后同步（internal 直调服务层）。"""

from datetime import date

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="paper-trade-sync",
        label="模拟盘委托成交同步",
        description="盘后拉取掘金仿真当日委托/成交/资金快照，幂等落库",
        data_type="paper-trade-sync",
        collectors={
            "internal": "collector.spiders.paper_trade_sync:PaperTradeSyncCollector",
        },
        queue="batch",
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
)
