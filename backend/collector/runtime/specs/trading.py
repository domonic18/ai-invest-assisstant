"""交易域任务声明：模拟盘盘后同步与复盘生成（internal 直调服务层）。"""

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
    TaskSpec(
        name="paper-trade-review",
        label="模拟盘 AI 分层复盘",
        description="盘后对 agent 账户交易做日/周/月分层归因复盘（选股/计划/执行 verdict + 经验提取），周期末日历判定加发",
        data_type="paper-trade-review",
        collectors={
            "internal": "collector.spiders.paper_trade_review:PaperTradeReviewCollector",
        },
        queue="heavy",
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
    TaskSpec(
        name="agent-daily-plan",
        label="交易 Agent 每日选股与交易计划",
        description="盘后 19:30（晚于 agent 复盘 19:00）基于复盘解读/涨停归因/异动/持仓生成选股清单与交易计划，同步 agent 自选分组",
        data_type="agent-daily-plan",
        collectors={
            "internal": "collector.spiders.agent_daily_plan:AgentDailyPlanCollector",
        },
        queue="heavy",
        run_params=("trade_date",),
        converters={"trade_date": date.fromisoformat},
    ),
)
